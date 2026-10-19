# web-player

`web-player` plays slither.io from Python. It drives a real Chromium tab through
Playwright and exposes the game as one class, `Game`, plus a handful of frozen
dataclasses. This page describes the package as it behaves today.

## Running it

### CLI

```bash
uv run web-player play --headed            # watch the bot play one round in a browser window
uv run web-player play                     # same round, headless (no window)
uv run web-player play --human             # you play the round (opens a window)
uv run web-player play --nickname eli      # set the in-game name (default: slitherbot)
```

`play` joins one round. By default the bot steers with a random walk on
heading. With `--human` the bot sends no input at all, so you play with the
game's own controls:

| Control | Effect |
| --- | --- |
| Mouse position | Steer toward the pointer |
| Left / right arrow | Turn |
| Hold mouse button, Space, or up arrow | Boost |

Click into the browser window first so it has keyboard focus. In both modes
the terminal prints a status line about once a second:

```
t=  14.1s  len=   23  pos=(  24709,  32484)  snakes=  2  food= 361
```

`t` counts from launch, so the first line appears only after the browser has
started and the game has loaded (about 10 s headed, less headless).

A run ends in one of three ways. Each prints a final line, closes the browser,
and exits with status 0:

| What happened | Final line |
| --- | --- |
| The snake died | `snake died after 17.3s` |
| You closed the browser window | `browser closed after 17.0s` |
| You pressed Ctrl+C | `interrupted after 9.8s` |

When launched through `uv run`, the shell may report exit status 130 after
Ctrl+C. That status comes from `uv`, not from `web-player`.

### From Python

```python
import math, random
from web_player import Action, Game, GameClosed

try:
    with Game(headless=False) as game:      # leaving the block closes the browser
        obs = game.start_round("eli")
        angle = 0.0
        while obs.alive:
            angle = (angle + random.uniform(-0.25, 0.25)) % math.tau
            game.act(Action(angle))
            obs = game.observe()
except GameClosed:
    print("browser was closed")
```

Run scripts with `uv run python my_script.py` so they use the workspace
environment.

## The API

Everything public is importable from `web_player`:

| Name | Kind | Purpose |
| --- | --- | --- |
| `Game` | class | One browser tab playing the game |
| `GameError` | exception | The game could not be loaded, started, or talked to |
| `GameClosed` | exception | Subclass of `GameError`: the browser or tab went away |
| `Observation`, `Snake`, `Food`, `Prey`, `Point` | frozen dataclasses | What the bot sees |
| `Action` | frozen dataclass | What the bot does |

### `Game`

```python
Game(*, headless=True, viewport=(1280, 800), url="http://slither.io", timeout=30.0)
```

| Method | Behavior |
| --- | --- |
| `Game(...)` | Launches Chromium, loads the game, and returns once a round can be started. Raises `GameError` if loading fails. |
| `start_round(nickname="")` | Joins a round and blocks until the snake is alive, then returns the first `Observation`. If a round is already in progress, it returns the current observation instead. After a death it waits out the game-over fade. |
| `observe()` | Returns an `Observation` of the game right now. Cheap enough to call every tick. |
| `act(action)` | Steers toward `action.angle` and sets boost. The action holds until the next `act()`. While the snake is dead this does nothing. |
| `close()` | Shuts the browser down. Safe to call twice. Never raises. |

`Game` is a context manager; leaving the `with` block calls `close()`.

Design rules the API follows:

- **Callers never import Playwright.** Every Playwright failure is re-raised as
  `GameError`, or as `GameClosed` when the page or browser is gone.
- **Edge cases are not errors.** Acting while dead, starting a round that is
  already running, and closing twice all quietly do the right thing, so play
  loops need no guard code.
- **The game runs on its own.** The browser keeps simulating between calls.
  Your loop decides how often to observe and act. The bundled CLI uses a
  50 ms tick, which already matches the game's own input rate (below).
- **One thread.** `Game` uses Playwright's sync API and must stay on the thread
  that created it.

### Observation types

Conventions for every type:

- Positions are world units. **The y axis points down**, as on screen.
- Angles are radians: `0` points along +x and `π/2` along +y (screen-down).

`Observation`

| Field | Meaning |
| --- | --- |
| `time_ms` | The page's monotonic clock (`performance.now()`) at capture time |
| `alive` | True from the moment the round starts until the moment of death |
| `me` | The player's `Snake`, or `None` when not alive |
| `others` | Other living snakes the client knows about (excludes `me`) |
| `foods` | Uneaten food pellets the client knows about |
| `preys` | Moving pellets that flee from snakes |
| `world_radius` | The game's `grd` value, which sets the size of the circular arena |
| `rank` | Leaderboard rank, or 0 until the server reports it |
| `player_count` | Players on the server, or 0 until the server reports it |

When `alive` is false, `me` is `None` and `others`, `foods`, and `preys` are
empty. The other fields are always populated.

`Snake`: `id`, `name`, `head: Point`, `angle` (current heading), `speed`,
`scale` (body thickness multiplier), `length` (the score the game shows), and
`body: tuple[Point, ...]`, **ordered tail first, head last**.

`Food`: `position`, `size`. `Prey`: `position`, `size`, `angle`, `speed`.

`Action(angle, boost=False)`: `angle` is the **absolute** heading to steer
toward. The game turns the snake toward it at its own limited turn rate.
`boost` trades length for speed while it is held.

## How it works

```
 your loop ──▶ Game (game.py) ──page.evaluate──▶ bridge.js ──▶ slither.io globals
               parse_observation (observation.py) ◀── plain JSON ◀──┘
```

- **`game.py`** owns the browser lifecycle and error translation.
- **`bridge.js`** is injected with `add_init_script` before the game script
  loads. It defines `window.__slitherbot` with `observe`, `act`, `isAlive`,
  `canStart`, and `start`. These read the game's globals at call time. It is
  the **only** code that knows slither.io's internals, so if a game update
  breaks the bot, the fix belongs here.
- **`observation.py`** holds the dataclasses and `parse_observation`, the only
  Python code that knows the bridge's JSON format. It has no browser
  dependency, so it can move into `slither-core` unchanged.
- **`cli.py`** is the `web-player` command. `--human` is implemented there by
  skipping `act()`. `Game` needs no special mode for it.

### What the bridge relies on

We confirmed each of these against the live game script and a running round.
They are the first things to recheck if the bot stops working after a game
update.

| Need | How the game does it |
| --- | --- |
| Player's snake | Global `slither` (older bots used `snake`, which no longer exists). It also appears in `slithers`, so the bridge excludes it from `others`. |
| Other snakes | Global `slithers`. Each has `xx`/`yy`, `ang`, `sp`, `sc`, `nk` (name), and `pts` (body points, tail first, with `dying` set on points being removed). |
| Food | Global `foods` is a sparse buffer with `foods_c` live slots. Empty and `eaten` slots are skipped. |
| Alive | `playing && slither != null && dead_mtm === -1`. On death the game stamps `dead_mtm` at once but leaves `playing` true through a ~2 s fade, so `playing` alone would report a dead snake as alive. |
| Ready to start | `play_btn` exists and is enabled, `want_play` is false, `playing` is false, and `dead_mtm === -1`. |
| Start a round | Set `#nick`'s value, then call `play_btn.elem.onclick()`. Play begins about 1 s later. |
| Steering | Set globals `xm`/`ym`, the virtual mouse offset from screen centre, to a point 300 px away along the angle. Offsets under 16 px are ignored. The game sends a heading at most every ~33 ms, quantized to 251 directions. |
| Boost | `setAcceleration(1)` / `setAcceleration(0)`. The game sends changes at most every 50 ms. Measured speed is about 5.8 cruising and 13.7 boosting. |
| Length | The bridge reuses the game's own "final length" formula: `floor((fpsls[sct] + fam / fmlts[sct] - 1) * 15 - 5)` with `sct = sct + rsc`. |

## Known gaps

- **Arena geometry is unconfirmed.** `world_radius` is the raw `grd` value
  (about 32550 in testing). The arena is probably a circle centred at
  `(grd, grd)`, but no test has reached the wall yet.
- **`rank` and `player_count`** read 0 early in a round, before the server
  sends a leaderboard update.
- **No recording yet.** Observations are not saved anywhere; `collect` mode is
  the next planned feature.
- **One bot strategy.** The bot only does a random walk; the alternative is
  `--human`. A `Strategy` interface and `--strategy` option are planned.
- **Bot input competes with the mouse.** In headed bot mode the bot rewrites
  the steering every 50 ms. Moving your mouse over the window nudges the snake
  until the next tick, so keep the pointer out of the window while watching.

## Tests

```bash
uv run --package web-player pytest packages/web-player
```

Unit tests cover `parse_observation` and never touch the live site. Running
`web-player play` is the end-to-end check against the real game.
