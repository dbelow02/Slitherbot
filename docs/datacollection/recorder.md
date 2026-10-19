# `recorder.py`

**Job:** the collection loop. Every Δ it reads the game state, chooses an action, starts the key
press, and saves a record. It ends episodes on death and starts new rounds.

## The step

Each step `k`, in `Collector.run_episode`:

1. **Wait and read.** Sleep until `t0 + k·Δ`, then read the state and the frame. The page
   reads both in the next game frame, right after the game redraws, so they show the same moment
   (see [game_js.md](game_js.md#how-state-and-frame-stay-in-sync)). `late_ms` is how far past the
   slot the read was requested. The page's report on the time since the last read (`act`,
   `key_events`, `mouse_moves`) is split off: it belongs to the previous step.
2. **Save the previous step.** `complete_record` adds that report to the previous step's record
   (key timing, human keys, mouse moves, `dt_next_ms`, flags), and it is written.
3. **Stop on death.** If `is_alive(state)` is false, write the state once as a `terminal`
   record and end the episode.
4. **Act.** The policy picks `(key, ms)`. The hold is clamped so the key comes up at least
   `release_margin_ms` before the next slot (the requested value is kept as `requested_ms`).
   `browser.act` starts the press in the page and returns at once.
5. **Build this step's record.** The frame is appended to `frames.tar` and the record points to
   it. The record is held in `pending` and saved at the next read.

Then the next slot. If the loop fell more than a step behind (a slow page or computer), it
jumps to the current slot rather than reading several times in a row, and flags
`skipped_slots`.

Records are saved one step late on purpose: the real key-up time, and what a human pressed, are
only known at the next read.

## Ending an episode

| End | When | Last record |
| --- | --- | --- |
| `death` | First state with `self.dead` true or `dead_mtm` ≠ −1 | `terminal` record of the dead state |
| `max_steps` | `k + 1 ≥ max_steps` | Last step, flagged `no_next_read` |
| `stopped` | `--minutes` deadline or Ctrl+C | Last step, flagged `no_next_read` |
| `error` | Any exception (page crash, disconnect) | Last step, flagged `no_next_read`; the message is saved |

**Why not `playing`:** the game keeps `playing` true for a few seconds of death animation
after the snake is dead. Testing with `playing` alone recorded ~18 dead steps as alive.

On death, the final length is parsed from the death screen ("Your final length was N"); if that
can't be read, the length in the terminal state is used.

## Functions and classes

| Name | What it does |
| --- | --- |
| `is_alive(state)` | `playing` and our snake exists and isn't dead and `dead_mtm == −1` |
| `step_flags(state, late_ms, cfg)` | Flags known at read time: `not_frame_synced`, `no_frame`, `late`, `lag`, `disconnected` |
| `complete_record(record, interval, next_t, human)` | Adds what happened until the next read, with key times in ms after this step's frame. Bot steps: `act_timing`, `action.start_ms` / `end_ms`, `forced_release` if the key was still down, `human_interference` if real keys were pressed. Human steps: the action from [`HumanKeyTracker`](policies.md#humankeytracker), `both_keys`. Both: `mouse_moved`, `dt_next_ms` |
| `Screenshots` | Full-page debug screenshots (separate from the per-step frames) taken in a background task so they never delay a step. One every `screenshot_every_s` is held in memory; one every `keep_screenshot_every_s` is saved. On death the latest is saved as `death_step_*.jpg`. The first screenshot is slow (~0.5 s), so `warm_up()` takes one before the episode clock starts |
| `Collector` | Runs a session: draws a seed if none was given, writes `session.json`, then for each episode picks a policy (`mixed` draws one by weight), draws an episode seed, starts a round, runs the episode, prints a line |
| `Collector.run_episode(...)` | The step loop above. Returns the episode summary |
| `git_info()` | Commit hash and whether there were uncommitted changes, for `session.json` |

## Randomness

`Collector.rng` is seeded with the session seed. It chooses the policy for each `mixed` episode
and draws each episode's seed. Each episode's policy gets its own `random.Random(episode_seed)`,
so one episode's choices don't depend on how many random numbers earlier episodes used.

## Failures

- A round that won't start (server unreachable, page broken): wait 2, 4, 8 … up to 60 s,
  reload the page, try again. Runs unattended without stopping on a network hiccup.
- An error during an episode: the episode is saved with `end_reason: "error"` and the page is
  reloaded.
- The bot's key is always released before an episode closes, so a key never stays held.
