"""The collection loop: read the game state every Δ, act, and save each episode.

One step ``k``:

1. wait until ``t0 + k·Δ`` and read the state and the frame (an image of the game). Both come
   from the same game frame; ``state["t"]`` is that moment on the page's clock
2. complete the previous step's record with what happened since its read, and save it
3. stop if our snake is dead (saving one ``terminal`` record)
4. choose an action and start the key press (it runs in the page; we don't wait for it)
5. build this step's record; it is saved at the next read

Records are saved one step late because an action's real key timing, and a human's key
presses, are only known at the next read.
"""

from __future__ import annotations

import asyncio
import platform
import random
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from datacollection.browser import SlitherBrowser
from datacollection.config import CollectConfig
from datacollection.policies import Action, HumanKeyTracker, Policy, make_policy
from datacollection.storage import SCHEMA_VERSION, EpisodeWriter, parse_final_length, write_json

# Fields the page reports about the interval *before* a read. They belong to the previous step.
INTERVAL_FIELDS = ("act", "key_events", "mouse_moves")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_alive(state: dict[str, Any]) -> bool:
    """Our snake is alive. The game marks it dead (``self.dead``, ``dead_mtm``) a few seconds
    before ``playing`` turns false, so ``playing`` alone is not enough."""
    me = state["self"]
    return bool(state["playing"] and me and not me["dead"] and state["dead_mtm"] == -1)


def step_flags(state: dict[str, Any], late_ms: float, cfg: CollectConfig) -> list[str]:
    flags = []
    if state["sync"] != "raf":
        flags.append("not_frame_synced")
    if cfg.frame_width > 0 and state.get("frame_error"):
        flags.append("no_frame")
    if late_ms > cfg.late_fraction * cfg.delta_ms:
        flags.append("late")
    if state["lagging"] or (state["lag_mult"] or 1) < 1:
        flags.append("lag")
    if not state["connected"]:
        flags.append("disconnected")
    return flags


def complete_record(record: dict[str, Any], interval: dict[str, Any], next_t: float,
                    human: HumanKeyTracker | None) -> None:
    """Add what happened between ``record``'s read and the next read (at page time ``next_t``).

    Key times are stored in ms after this step's frame, so it's explicit what was pressed between
    frame k and frame k+1.
    """
    t_frame = record["state"]["t"]
    events = interval.get("key_events", [])
    mouse_moves = interval.get("mouse_moves", 0)
    record["key_events"] = [[round(t - t_frame, 1), down, name] for t, down, name in events]
    record["mouse_moves"] = mouse_moves
    record["dt_next_ms"] = round(next_t - record["state"]["t"], 1)
    if mouse_moves:
        record["flags"].append("mouse_moved")
    if human is not None:
        action, extra = human.action_for(events, t_frame, next_t)
        record["action"] = {**action.to_json(), **extra}
        if extra["both_keys"]:
            record["flags"].append("both_keys")
    else:
        timing = interval.get("act")
        record["act_timing"] = timing
        if timing and timing["t_down"] is not None:
            record["action"]["start_ms"] = round(timing["t_down"] - t_frame, 1)
            record["action"]["end_ms"] = round(timing["t_up"] - t_frame, 1) if timing["t_up"] else None
        if timing and timing["forced"]:
            record["flags"].append("forced_release")
        if events:
            record["flags"].append("human_interference")


class Screenshots:
    """Debug screenshots, taken in the background so they never delay a step.

    One is taken every ``screenshot_every_s`` and held in memory; one every
    ``keep_screenshot_every_s`` is also saved. On death the latest one is saved as the
    "death" shot (taken up to ``screenshot_every_s`` before death was detected).
    """

    def __init__(self, browser: SlitherBrowser, writer: EpisodeWriter, cfg: CollectConfig) -> None:
        self.browser = browser
        self.writer = writer
        self.cfg = cfg
        self.task: asyncio.Task[bytes] | None = None
        self.task_step = 0
        self.task_keep = False
        self.latest: tuple[int, bytes] | None = None
        self.next_shot_s = 0.0
        self.next_keep_s = 0.0

    @property
    def enabled(self) -> bool:
        return self.cfg.screenshot_every_s > 0

    async def warm_up(self) -> None:
        if self.enabled:
            await self.browser.screenshot_jpeg(self.cfg.screenshot_quality)  # the first one is slow

    def update(self, step: int, elapsed_s: float) -> None:
        if self.task is not None and self.task.done():
            if not self.task.cancelled() and self.task.exception() is None:
                self.latest = (self.task_step, self.task.result())
                if self.task_keep:
                    self.writer.save_image(f"step_{self.task_step:06d}.jpg", self.latest[1])
            self.task = None
        if self.enabled and self.task is None and elapsed_s >= self.next_shot_s:
            self.next_shot_s = elapsed_s + self.cfg.screenshot_every_s
            self.task_keep = self.cfg.keep_screenshot_every_s > 0 and elapsed_s >= self.next_keep_s
            if self.task_keep:
                self.next_keep_s = elapsed_s + self.cfg.keep_screenshot_every_s
            self.task_step = step
            self.task = asyncio.create_task(self.browser.screenshot_jpeg(self.cfg.screenshot_quality))

    async def finish(self, died: bool) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except BaseException:
                pass
        if died and self.latest is not None:
            self.writer.save_image(f"death_step_{self.latest[0]:06d}.jpg", self.latest[1])


class Collector:
    def __init__(self, cfg: CollectConfig) -> None:
        if cfg.policy == "human" and cfg.headless:
            raise ValueError("human play needs a visible browser: use --headed")
        if cfg.seed is None:
            cfg.seed = random.SystemRandom().randrange(2**31)  # saved, so the run can be replayed
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)  # picks policies (mixed) and per-episode seeds
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_dir = cfg.out_dir / f"session_{stamp}_{cfg.policy}"

    def choose_policy_name(self) -> str:
        if self.cfg.policy != "mixed":
            return self.cfg.policy
        names = list(self.cfg.mix)
        return self.rng.choices(names, weights=[self.cfg.mix[n] for n in names])[0]

    async def run(self) -> Path:
        cfg = self.cfg
        self.session_dir.mkdir(parents=True, exist_ok=False)
        deadline = time.monotonic() + cfg.minutes * 60 if cfg.minutes else None
        episode = 0
        failures = 0
        async with SlitherBrowser(headless=cfg.headless, channel=cfg.channel, viewport=cfg.viewport) as browser:
            write_json(self.session_dir / "session.json", self.session_info(await browser.client_info()))
            while cfg.episodes is None or episode < cfg.episodes:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                name = self.choose_policy_name()
                seed = self.rng.randrange(2**31)
                if name == "human":
                    print("\nHuman round: click the game window once, then move the mouse OUTSIDE the window "
                          "(mouse movement steers the snake). Play with the arrow keys.", flush=True)
                try:
                    await browser.start_round(cfg.nickname)
                except Exception as e:  # page broke or server unreachable: wait, reload, try again
                    failures += 1
                    wait_s = min(60, 2**failures)
                    print(f"could not start a round ({e!r}); reloading in {wait_s}s", flush=True)
                    await asyncio.sleep(wait_s)
                    await self.reload(browser)
                    continue
                failures = 0
                episode += 1
                summary = await self.run_episode(browser, episode, name, seed, deadline)
                print(f"[ep {episode}] {name:13s} steps={summary['n_steps']:5d} "
                      f"final_length={summary['final_length']} end={summary['end_reason']} "
                      f"bad={summary['bad_steps']}", flush=True)
                if summary["end_reason"] == "error":
                    await self.reload(browser)
                if summary["end_reason"] == "stopped":
                    break
        return self.session_dir

    @staticmethod
    async def reload(browser: SlitherBrowser) -> None:
        try:
            await browser.open_page()
        except Exception as e:
            print(f"reload failed ({e!r})", flush=True)

    def session_info(self, client: dict[str, Any]) -> dict[str, Any]:
        cfg = asdict(self.cfg)
        cfg["out_dir"] = str(self.cfg.out_dir)
        return {
            "schema_version": SCHEMA_VERSION,
            "started": now_iso(),
            "config": cfg,
            "client": client,
            "versions": {
                "python": platform.python_version(),
                "datacollection": version("datacollection"),
                "playwright": version("playwright"),
            },
            "git": git_info(),
        }

    async def run_episode(self, browser: SlitherBrowser, index: int, policy_name: str, seed: int,
                          deadline: float | None) -> dict[str, Any]:
        cfg = self.cfg
        policy: Policy | None = make_policy(policy_name, random.Random(seed), cfg.hold_ms, cfg.epsilon)
        human = HumanKeyTracker() if policy is None else None
        writer = EpisodeWriter(self.session_dir / f"ep_{index:06d}")
        shots = Screenshots(browser, writer, cfg)
        delta_s = cfg.delta_ms / 1000.0
        summary: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION, "episode": index, "policy": policy_name, "seed": seed,
            "policy_params": policy.params() if policy else {}, "delta_ms": cfg.delta_ms,
            "started": now_iso(),
        }
        bad_steps = 0
        max_length = 0
        last_length = None
        end_reason = "death"
        pending: dict[str, Any] | None = None  # previous step's record, saved at the next read

        await shots.warm_up()
        t0 = time.monotonic()
        k = 0
        try:
            while True:
                # 1. Wait for this step's slot, then read.
                slot = t0 + k * delta_s
                if slot > time.monotonic():
                    await asyncio.sleep(slot - time.monotonic())
                late_ms = (time.monotonic() - slot) * 1000.0
                state = await browser.read_state(cfg.frame_width, cfg.frame_quality)
                frame = state.pop("frame", None)
                interval = {f: state.pop(f) for f in INTERVAL_FIELDS}

                # 2. Complete and save the previous step.
                if pending is not None:
                    complete_record(pending, interval, state["t"], human)
                    writer.write(pending)
                    bad_steps += bool(pending["flags"])
                    pending = None

                # 3. Dead: save the first dead state (it shows what killed us) and stop.
                if not is_alive(state):
                    if state["self"]:
                        writer.write({"step": k, "t_sched_ms": round(k * cfg.delta_ms, 1),
                                      "late_ms": round(late_ms, 1), "flags": ["terminal"],
                                      "action": None, "frame": writer.add_frame(k, frame) if frame else None,
                                      "state": state})
                        summary["death_length"] = state["self"]["length"]
                    break
                last_length = state["self"]["length"]
                max_length = max(max_length, last_length or 0)

                # 4. Choose and start the action. The key must be up before the next read, so the
                #    hold is clamped to the time left in this step.
                decide_ms = 0.0
                if policy is not None:
                    t_decide = time.monotonic()
                    action = policy.act(state)
                    decide_ms = (time.monotonic() - t_decide) * 1000.0
                    left_ms = (t0 + (k + 1) * delta_s - time.monotonic()) * 1000.0 - cfg.release_margin_ms
                    requested_ms = action.ms
                    if action.key and action.ms > left_ms:
                        action = Action(action.key if left_ms > 0 else None, max(0.0, left_ms), action.source)
                    await browser.act(action.key, action.ms)
                else:
                    action = Action(None, 0.0, "human")  # replaced by the real key presses at the next read
                    requested_ms = 0.0

                # 5. This step's record.
                pending = {
                    "step": k,
                    "t_sched_ms": round(k * cfg.delta_ms, 1),
                    "late_ms": round(late_ms, 1),
                    "flags": step_flags(state, late_ms, cfg),
                    "action": action.to_json(),
                    "decide_ms": round(decide_ms, 2),
                    "frame": writer.add_frame(k, frame) if frame else None,
                    "state": state,
                }
                if action.ms < requested_ms:
                    pending["action"]["requested_ms"] = round(requested_ms, 1)

                shots.update(k, time.monotonic() - t0)

                if k + 1 >= cfg.max_steps:
                    end_reason = "max_steps"
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    end_reason = "stopped"
                    break

                # Next slot. If we fell more than a step behind, skip the missed slots.
                k += 1
                behind = int((time.monotonic() - t0) / delta_s)
                if behind > k:
                    pending["flags"].append("skipped_slots")
                    k = behind
        except asyncio.CancelledError:  # Ctrl+C
            end_reason = "stopped"
            raise
        except Exception as e:
            end_reason = "error"
            summary["error"] = repr(e)
        finally:
            if pending is not None:  # cut off before the next read: action timing unknown
                pending["flags"].append("no_next_read")
                writer.write(pending)
                try:
                    await browser.release()
                except Exception:
                    pass
            await shots.finish(died=end_reason == "death")
            if end_reason == "death":
                try:
                    text = await browser.last_score()
                except Exception:
                    text = None
                summary["last_score_text"] = text
                summary["final_length"] = parse_final_length(text) or summary.get("death_length")
            else:
                summary["final_length"] = last_length
            summary.update(end_reason=end_reason, max_length=max_length, bad_steps=bad_steps,
                           ended=now_iso(), duration_s=round(time.monotonic() - t0, 2))
            writer.close(summary)
        return summary


def git_info() -> dict[str, Any]:
    """Commit of this code and whether it had uncommitted changes, so a run can be traced to code."""
    here = Path(__file__).resolve().parent
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True,
                                check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=here, capture_output=True, text=True,
                               check=True).stdout.strip() != ""
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
