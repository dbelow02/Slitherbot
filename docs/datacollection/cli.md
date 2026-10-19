# `cli.py`

**Job:** turn command-line options into a [`CollectConfig`](config.md) and run either
collection or the summary.

## Commands

### `datacollection collect`

| Option | Default | Meaning |
| --- | --- | --- |
| `--policy` | `random` | `random`, `heuristic`, `eps-heuristic`, `human`, or `mixed` |
| `--mix` | `random=0.4,heuristic=0.3,eps-heuristic=0.3` | Weights for `mixed` (bot policies only) |
| `--episodes` | none | Stop after this many episodes |
| `--minutes` | none | Stop after this many minutes |
| `--max-steps` | 30000 | Cut an episode off after this many steps |
| `--delta-ms` | 200 | Δ, time between state reads |
| `--max-hold-ms` | Δ − 10 | Longest key hold a policy may ask for |
| `--epsilon` | 0.2 | Random-action rate for `eps-heuristic` |
| `--headed` | off | Show the browser (required for `human`) |
| `--channel` | `chrome` | `chrome` = installed Google Chrome; `chromium` = Playwright's build |
| `--viewport` | `1280x800` | Browser size; affects how far the client sees |
| `--nickname` | empty | Name shown in game |
| `--seed` | drawn | Session seed; saved in `session.json` either way |
| `--frame-width` | 640 | Width in px of the game image saved with every step (0 = none) |
| `--frame-quality` | 0.7 | JPEG quality of those images, 0–1 |
| `--screenshot-every` | 1.0 | Seconds between debug screenshots kept in memory (0 = off) |
| `--keep-screenshot-every` | 10.0 | Seconds between screenshots saved to disk |
| `--out` | `Slitherbot/data/raw` | Output folder |

With neither `--episodes` nor `--minutes`, it runs until Ctrl+C.

### `datacollection summarize [PATH] [--check-turns]`

Prints statistics for every episode under `PATH` (default `Slitherbot/data/raw`). See
[summarize.md](summarize.md).

## Functions

| Function | What it does |
| --- | --- |
| `parse_mix("random=0.5,heuristic=0.5")` | → `{"random": 0.5, "heuristic": 0.5}`. Rejects unknown names and `human` |
| `parse_viewport("1280x800")` | → `(1280, 800)` |
| `build_parser()` | The argparse parser. Defaults are read from `CollectConfig`, so they're defined in one place |
| `main(argv=None)` | Parses options, builds the config, runs `Collector.run()` with `asyncio.run`. Ctrl+C stops it; the current episode is still saved |
