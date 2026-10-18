"""Command line: ``datacollection collect ...`` and ``datacollection summarize ...``."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from datacollection.config import CollectConfig, default_out_dir
from datacollection.policies import POLICY_NAMES, check_policy_names
from datacollection.recorder import Collector
from datacollection.summarize import summarize


def parse_mix(text: str) -> dict[str, float]:
    """``"random=0.5,heuristic=0.5"`` -> ``{"random": 0.5, "heuristic": 0.5}``."""
    mix = {}
    for part in text.split(","):
        name, _, weight = part.partition("=")
        mix[name.strip()] = float(weight)
    check_policy_names(list(mix))
    if "human" in mix:
        raise argparse.ArgumentTypeError("human can't be part of a mix; run --policy human on its own")
    return mix


def parse_viewport(text: str) -> tuple[int, int]:
    """``"1280x800"`` -> ``(1280, 800)``."""
    width, height = text.lower().split("x")
    return int(width), int(height)


def build_parser() -> argparse.ArgumentParser:
    defaults = CollectConfig(out_dir=Path())
    p = argparse.ArgumentParser(prog="datacollection", description="Collect slither.io game state.")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="play and record episodes")
    c.add_argument("--policy", choices=[*POLICY_NAMES, "mixed"], default=defaults.policy,
                   help="who plays; 'mixed' picks a bot policy per episode using --mix")
    c.add_argument("--mix", type=parse_mix, default=dict(defaults.mix),
                   help="weights for --policy mixed, e.g. random=0.5,heuristic=0.5")
    c.add_argument("--episodes", type=int, help="stop after this many episodes")
    c.add_argument("--minutes", type=float, help="stop after this many minutes")
    c.add_argument("--max-steps", type=int, default=defaults.max_steps, help="cut an episode off after this many steps")
    c.add_argument("--delta-ms", type=float, default=defaults.delta_ms, help="time between state reads")
    c.add_argument("--max-hold-ms", type=float, help="longest key hold (default: delta minus 10 ms)")
    c.add_argument("--epsilon", type=float, default=defaults.epsilon, help="random-action rate for eps-heuristic")
    c.add_argument("--headed", action="store_true", help="show the browser window (required for human)")
    c.add_argument("--channel", default="chrome",
                   help="browser: 'chrome' (installed Google Chrome) or 'chromium' (Playwright's build)")
    c.add_argument("--viewport", type=parse_viewport, default=defaults.viewport, help="browser viewport, WxH")
    c.add_argument("--nickname", default=defaults.nickname, help="name shown in game")
    c.add_argument("--seed", type=int, help="random seed (default: drawn and saved in session.json)")
    c.add_argument("--screenshot-every", type=float, default=defaults.screenshot_every_s,
                   help="seconds between debug screenshots held in memory (0 = none)")
    c.add_argument("--keep-screenshot-every", type=float, default=defaults.keep_screenshot_every_s,
                   help="seconds between debug screenshots saved to disk")
    c.add_argument("--out", type=Path, help="output folder (default: Slitherbot/data/raw)")

    s = sub.add_parser("summarize", help="print dataset statistics")
    s.add_argument("path", type=Path, nargs="?", help="data folder (default: Slitherbot/data/raw)")
    s.add_argument("--check-turns", action="store_true",
                   help="check that heading changes match the recorded actions")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "summarize":
        summarize(args.path or default_out_dir(), check_turns=args.check_turns)
        return

    cfg = CollectConfig(
        out_dir=args.out or default_out_dir(),
        policy=args.policy,
        mix=args.mix,
        episodes=args.episodes,
        minutes=args.minutes,
        max_steps=args.max_steps,
        delta_ms=args.delta_ms,
        max_hold_ms=args.max_hold_ms,
        epsilon=args.epsilon,
        headless=not args.headed,
        channel=None if args.channel == "chromium" else args.channel,
        viewport=args.viewport,
        nickname=args.nickname,
        seed=args.seed,
        screenshot_every_s=args.screenshot_every,
        keep_screenshot_every_s=args.keep_screenshot_every,
    )
    collector = Collector(cfg)
    print(f"Recording to {collector.session_dir} (seed {cfg.seed})", flush=True)
    try:
        asyncio.run(collector.run())
    except KeyboardInterrupt:
        print("\nStopped. The current episode was saved.", flush=True)
    print(f"Session: {collector.session_dir}", flush=True)
