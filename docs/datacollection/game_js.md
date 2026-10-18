# `game_js.py`

**Job:** the JavaScript that runs inside the slither.io page. It defines `window.__dc`, which
reads the game's variables, presses arrow keys for the bot, and logs a human's key presses.
**Every slither.io variable name the project uses is in this file**, so when the game renames
something (it has already renamed `snake` → `slither`), this is the one place to fix.

The script is one Python string, `INIT_SCRIPT`. [`browser.py`](browser.md) adds it with
`add_init_script`, so it runs before the game's own code on every page load. It only reads the
game's variables when called, so it doesn't matter that they don't exist yet.

## `window.__dc`

| Function | What it does |
| --- | --- |
| `read()` | Returns the raw state (see [data-format.md](../data-format.md#state)). First releases any key the bot still holds (marking that action `forced`). Also returns, and clears: the timing of the bot's last action (`act`), real key events since the last read (`key_events`), and real mouse moves (`mouse_moves`) |
| `act(key, ms)` | Releases any held key, sends `keydown` for `ArrowLeft` / `ArrowRight`, and sets a timer to send `keyup` after `ms`. Records `t_call`, `t_down`, `t_up` with `performance.now()`. `key = null` or `ms ≤ 0` presses nothing |
| `release()` | Sends `keyup` for a held key now and marks the action `forced` |
| `ready()` | The Play button and nickname box exist |
| `start(nickname)` | Sets the nickname and calls the game's Play handler. Returns `busy` while a round or its death animation runs |
| `inRound()` | A live round: `playing`, our snake exists and isn't dead, `dead_mtm == −1`, and the length tables are loaded |
| `lastScore()` | Death-screen text, or `null` while `playing` is still true |
| `clientInfo()` | Game script URL, protocol version, user agent, viewport |

## How it reads the game

| Saved | Game variable(s) |
| --- | --- |
| Our snake | `window.slither` |
| Other snakes | `window.slithers` (minus ours) |
| Food | `window.foods` up to `window.foods_c` (skips `null`s) |
| Prey | `window.preys` |
| Body points | `pts[i].xx + pts[i].fx`, `pts[i].yy + pts[i].fy`, `pts[i].dying` (what the game draws) |
| Head | `xx + fx`, `yy + fy` |
| Length | `floor(15 × (fpsls[sct + rsc] + fam / fmlts[sct + rsc] − 1) − 5)`, the same formula as the game's death screen |
| Everything else | Globals of the same name: `playing`, `connected`, `dead_mtm`, `grd`, `view_xx`, `gsc`, `rank`, `lag_mult`, `kd_l`, … |

Numbers are rounded in the page (positions to 0.1, angles to 0.001) so less data crosses into
Python. `null` is saved for any value that isn't a finite number.

## How keys are pressed

The game listens with `document.onkeydown` / `onkeyup` and checks `keyCode` (37 Left, 39 Right,
38 Up, 32 Space). `act` dispatches `KeyboardEvent`s with those codes on `document`. The game then
counts the frames the key is down and sends turn messages to the server, exactly as for a real
key press.

## How human keys are logged

Listeners on `window` (capture phase, so they run before the game's handlers) record **trusted**
key events only, meaning real presses, not the bot's synthetic ones. Left, Right, and Up/Space
(as `boost`) are kept; auto-repeat `keydown`s are ignored. Real mouse moves are counted.
[`HumanKeyTracker`](policies.md#humankeytracker) turns the events into per-step actions. During
bot play, real key presses flag the step `human_interference`.
