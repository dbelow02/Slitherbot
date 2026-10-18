# Data format

What `datacollection collect` writes. Schema version 1. Why the data looks like this is in
[input-data-decisions.md](input-data-decisions.md).

## Folders

```
data/raw/session_<YYYYmmdd-HHMMSS>_<policy>/
├── session.json             run settings, seed, versions, git commit
└── ep_000001/
    ├── steps.jsonl.gz        one JSON record per line
    ├── episode.json          episode summary (written last)
    └── shots/
        ├── step_000050.jpg   debug screenshot, about every 10 s
        └── death_step_*.jpg  last screenshot before death (up to ~1 s before)
```

An episode folder without `episode.json` was interrupted before it closed. Its records are in
`steps.jsonl` (not yet compressed) and readable up to the last full line.

Read with the helpers in `datacollection.storage`:

```python
from datacollection.storage import episode_dirs, load_steps, read_json

for ep in episode_dirs(Path("data/raw")):
    summary = read_json(ep / "episode.json")
    for record in load_steps(ep):
        ...
```

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

## Step record

A record holds the state read at step `k` and the action taken right after it. It is written
once the next state has been read, because the action's real key timing (and a human's key
presses) are only known then.

| Field | Meaning |
| --- | --- |
| `step` | Step index `k`. Gaps mean slots were skipped after falling behind |
| `t_sched_ms`, `late_ms` | Scheduled time (`k × Δ` from episode start) and how late the read was |
| `flags` | Problems with this step (see [Flags](#flags)). Empty = clean |
| `action` | `key` (`"left"`, `"right"`, `null`), `ms` held, `source` (policy). `requested_ms` if the hold was shortened to fit the step. Human steps also have `left_ms`, `right_ms`, `boost_ms`, `both_keys`. `null` in the terminal record |
| `act_timing` | Bot only: in-page `t_call`, `t_down`, `t_up` (ms, page clock) and `forced` |
| `decide_ms` | Time the policy took to choose |
| `dt_next_ms` | Page-clock time from this read to the next |
| `key_events` | Real key events between this read and the next: `[t, down (1/0), "left" / "right" / "boost"]` |
| `mouse_moves` | Real mouse movements between this read and the next |
| `state` | Raw game state at the read (below) |

### `state`

| Field | Meaning |
| --- | --- |
| `t`, `wall` | Page clock (`performance.now()`, ms) and wall clock (Unix ms) |
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
as drawn (`xx + fx`, `yy + fy`).

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

Drop or mask flagged records when training. `terminal` records are the end of an episode, not
an error.
