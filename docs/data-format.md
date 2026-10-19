# Data format

What `datacollection collect` writes. Schema version 1. Why the data looks like this is in
[input-data-decisions.md](input-data-decisions.md).

## Folders

```
data/raw/session_<YYYYmmdd-HHMMSS>_<policy>/
├── session.json             run settings, seed, versions, git commit
└── ep_000001/
    ├── steps.jsonl.gz        one JSON record per line
    ├── frames.tar            one JPEG of the game per record: frame_000000.jpg, frame_000001.jpg, ...
    ├── episode.json          episode summary (written last)
    └── shots/
        ├── step_000050.jpg   debug screenshot, about every 10 s
        └── death_step_*.jpg  last screenshot before death (up to ~1 s before)
```

An episode folder without `episode.json` was interrupted before it closed. Its records are in
`steps.jsonl` (not yet compressed) and readable up to the last full line.

Read with the helpers in `datacollection.storage`:

```python
from datacollection.storage import episode_dirs, load_frames, load_steps, read_json

for ep in episode_dirs(Path("data/raw")):
    summary = read_json(ep / "episode.json")
    frames = dict(load_frames(ep))           # {"frame_000000.jpg": jpeg_bytes, ...}
    for record in load_steps(ep):
        image = frames.get(record["frame"])  # this step's image, or None
        ...
```

## Frames and synchronization

Every record (including the terminal one) has a **frame**: a JPEG of the game canvas,
`--frame-width` px wide (default 640; 640×400 at the default viewport), quality 0.7. Frames hold
only the game; the leaderboard and score text are HTML on top and aren't in them. Measured:
~24 KB per frame, ~8 ms to encode, about 430 MB per hour of play.

**The frame and the state come from the same game frame.** The game's loop updates the world,
redraws the canvas, and schedules itself with `requestAnimationFrame`. The reader schedules its
own callback the same way, so it runs right after the game's update and redraw in that frame. It
reads the state and copies the canvas in one go, with nothing able to change in between.
`state["sync"]` is `"raf"` when this worked. (If animation frames are paused, for example in a
minimized window, it falls back after 100 ms with `"timeout"` and the step is flagged.)

**Actions are timed against frames.** All times are on the page clock, and `state["t"]` is the
moment of the frame. For step `k`:

```
frame k (t = 0)        key down (start_ms)     key up (end_ms)         frame k+1 (dt_next_ms)
     │──────────────────────│─────────────────────│─────────────────────────│
```

- Bot steps: `action.start_ms` / `action.end_ms` = key down / up, in ms after frame `k`.
- Human steps: `key_events` = every real key down / up, in ms after frame `k`.
- The key is always up before frame `k+1`, so everything between two frames is in one record.

Checked live by drawing a record's saved positions onto its saved frame: heads, live body points
and food land on the drawn objects.

## `session.json`

| Field | Meaning |
| --- | --- |
| `schema_version` | 1 |
| `started` | UTC start time |
| `config` | Every setting of the run (`CollectConfig`), including the `seed` actually used |
| `client` | Game script URL (it changes when the game updates), protocol version, user agent, viewport, browser version |
| `versions` | Python, `datacollection`, Playwright |
| `git` | Commit of the code and whether it had uncommitted changes (`dirty`) |

## `episode.json`

| Field | Meaning |
| --- | --- |
| `episode`, `policy` | Episode number and who played (`random`, `heuristic`, `eps-heuristic`, `human`) |
| `seed` | Seed of this episode's policy random generator |
| `policy_params` | The policy's settings |
| `delta_ms` | Δ |
| `started`, `ended`, `duration_s` | Timing |
| `end_reason` | `death`, `max_steps`, `stopped` (time limit or Ctrl+C), or `error` (then `error` holds the message) |
| `final_length` | Death screen value on death, otherwise the last length |
| `last_score_text`, `death_length` | Death screen text, and the length in the terminal state |
| `max_length` | Largest length during the episode |
| `bad_steps` | Records with at least one flag (not counting `terminal` / `no_next_read`) |
| `n_steps`, `raw_bytes`, `gz_bytes` | Records written and sizes |
| `n_frames`, `frame_bytes` | Frames written and their total size |

## Step record

A record holds the state read at step `k` and the action taken right after it. It is written
once the next state has been read, because the action's real key timing (and a human's key
presses) are only known then.

| Field | Meaning |
| --- | --- |
| `step` | Step index `k`. Gaps mean slots were skipped after falling behind |
| `t_sched_ms`, `late_ms` | Scheduled time (`k × Δ` from episode start) and how late the read was |
| `flags` | Problems with this step (see [Flags](#flags)). Empty = clean |
| `action` | `key` (`"left"`, `"right"`, `null`), `ms` held, `source` (policy). `requested_ms` if the hold was shortened to fit the step. Bot steps: `start_ms`, `end_ms` (key down / up, ms after this step's frame). Human steps: `left_ms`, `right_ms`, `boost_ms`, `both_keys`. `null` in the terminal record |
| `frame` | Name of this step's image in `frames.tar`, or `null` |
| `act_timing` | Bot only: in-page `t_call`, `t_down`, `t_up` (ms, page clock) and `forced` |
| `decide_ms` | Time the policy took to choose |
| `dt_next_ms` | Page-clock time from this read to the next |
| `key_events` | Real key events between this read and the next: `[ms after this step's frame, down (1/0), "left" / "right" / "boost"]` |
| `mouse_moves` | Real mouse movements between this read and the next |
| `state` | Raw game state at the read (below) |

### `state`

| Field | Meaning |
| --- | --- |
| `t`, `wall` | Page clock (`performance.now()`, ms) at the frame, and wall clock (Unix ms) |
| `sync` | `"raf"`: state and frame from the same game frame; `"timeout"`: fallback (flagged) |
| `game_fr` | The game's own frame counter |
| `frame_ms`, `frame_error` | Time to encode the frame; why it's missing, if it is |
| `playing`, `connected`, `dead_mtm` | Round status, connection, death time (−1 while alive) |
| `grd` | Arena radius; the center is `(grd, grd)` |
| `view_x`, `view_y`, `view_dist`, `view_ang` | Camera center; its distance and angle from the arena center (`grd − view_dist` = distance to the border) |
| `gsc`, `mww2`, `mhh2` | Zoom and half-screen size in pixels (visible half-width ≈ `mww2 / gsc` world units) |
| `rank`, `best_rank`, `slither_count` | Rank and total players on the server |
| `fps`, `lag_mult`, `lagging` | Client frame counter (resets each second) and lag state |
| `kd_l`, `kd_r`, `kd_u`, `xm`, `ym` | Keys the game thinks are down; mouse target |
| `self` | Our snake (snake fields below), plus `md` / `wmd` (boost on / wanted), `kill_count`, `length` (as on screen), `length_f` (not rounded down) |
| `snakes` | Every other snake the client holds (snake fields) |
| `foods` | `[x, y, sz, eaten]` for every food pellet the client holds |
| `preys` | `{id, x, y, sz, ang, wang, sp, dir, eaten}` |

**Snake fields:** `id`; head `x`, `y`; `ang` (heading), `wang` (target heading), `eang`;
`sp` (speed); `ssp`, `fsp`, `msp` (normal, boost-threshold, max speed); `sc` (size scale);
`scang`, `spang` (turn-rate factors); `sct`, `rsc`, `fam` (segment count, removed segments,
progress to the next segment); `dead`; `pts` = body points `[x, y, dying]` from tail to head,
as drawn (`xx + fx`, `yy + fy`). **Points with `dying = 1` are old tail positions fading out**
(they linger for a few seconds and are not part of the solid body). A moving snake often has more
dying points than live ones. Leave them out of model inputs.

Positions are world units rounded to 0.1, angles radians rounded to 0.001. Angles follow the
game: `x += cos(ang) × speed`, `y += sin(ang) × speed`; Left lowers `ang`.

## Flags

| Flag | Meaning |
| --- | --- |
| `late` | Read more than 20% of Δ after its scheduled time |
| `skipped_slots` | Fell more than a step behind; the next step index jumps |
| `lag` | The client reported lag (`lagging` or `lag_mult < 1`) |
| `disconnected` | Not connected to the server |
| `forced_release` | The bot's key was still down at the next read and was released then |
| `human_interference` | Real key presses during a bot episode |
| `mouse_moved` | Real mouse movement (it steers the snake) |
| `both_keys` | Human held Left and Right in the same step |
| `no_next_read` | Last record of an episode that ended without a death; its action timing is unknown |
| `terminal` | The first state where our snake is dead. Shows what killed us |
| `not_frame_synced` | State and frame were read on the fallback timer, not in the game's frame |
| `no_frame` | Frames are on but this step has none (`state.frame_error` says why) |

Drop or mask flagged records when training. `terminal` records are the end of an episode, not
an error.
