# `config.py`

**Job:** hold every setting of a collection run in one dataclass, `CollectConfig`. The whole
object is saved in `session.json`, so a run's settings are always known.

## `CollectConfig`

| Field | Default | Meaning |
| --- | --- | --- |
| `out_dir` | required | Where sessions are written |
| `policy` | `"random"` | `random`, `heuristic`, `eps-heuristic`, `human`, `mixed` |
| `mix` | `random 0.4, heuristic 0.3, eps-heuristic 0.3` | Policy weights for `mixed` |
| `episodes` | `None` | Stop after this many episodes |
| `minutes` | `None` | Stop after this many minutes |
| `max_steps` | 30000 | Cut an episode off after this many steps (~100 min at 200 ms) |
| `delta_ms` | 200 | Δ: time between state reads |
| `max_hold_ms` | `None` | Longest hold a policy may ask for |
| `release_margin_ms` | 10 | Keys are released at least this long before the next read |
| `epsilon` | 0.2 | Random-action rate for `eps-heuristic` |
| `headless` | `True` | No visible window |
| `channel` | `"chrome"` | Browser; `None` = Playwright's Chromium |
| `viewport` | `(1280, 800)` | Browser size |
| `nickname` | `""` | In-game name |
| `seed` | `None` | Session seed. `None` → [`Collector`](recorder.md) draws one and saves it |
| `screenshot_every_s` | 1.0 | Debug screenshot cadence (in memory); 0 = off |
| `keep_screenshot_every_s` | 10.0 | How often one is saved to disk |
| `screenshot_quality` | 60 | JPEG quality |
| `late_fraction` | 0.2 | A read later than this × Δ is flagged `late` |

`hold_ms` (property): `max_hold_ms` if set, otherwise `delta_ms − release_margin_ms` (190 ms by
default). Policies never ask for more than this. The [recorder](recorder.md) also clamps each
hold to the time actually left in the step.

## `default_out_dir()`

`Slitherbot/data/raw` when the package runs from this repository (it finds
`DataCollection/pyproject.toml` two folders above the file), otherwise `./data/raw`. `data/` is
in `.gitignore`.
