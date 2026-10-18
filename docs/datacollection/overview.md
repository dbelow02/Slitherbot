# `datacollection` package overview

Code: [`DataCollection/src/datacollection/`](../../DataCollection/src/datacollection/).
Records slither.io game state for training (Phase 2 of the [roadmap](../roadmap.md)).

## Files

| File | Job | Doc |
| --- | --- | --- |
| `__init__.py` | Entry point for the `datacollection` command | [\_\_init\_\_.md](__init__.md) |
| `cli.py` | Command-line options → `CollectConfig`; runs `collect` or `summarize` | [cli.md](cli.md) |
| `config.py` | `CollectConfig`: every setting of a run | [config.md](config.md) |
| `recorder.py` | The step loop: read, act, record, detect death, restart | [recorder.md](recorder.md) |
| `browser.py` | Playwright: open the game, start rounds, call into the page | [browser.md](browser.md) |
| `game_js.py` | JavaScript put into the page: reads state, presses keys, logs human keys | [game_js.md](game_js.md) |
| `policies.py` | Who chooses actions: random, heuristic, eps-heuristic; human key conversion | [policies.md](policies.md) |
| `storage.py` | Writing and reading episode files | [storage.md](storage.md) |
| `summarize.py` | Dataset statistics and the turn check | [summarize.md](summarize.md) |
| `tests/test_offline.py` | Tests that need no browser | [tests.md](tests.md) |

## How the pieces fit

```
cli.py ──CollectConfig──▶ recorder.Collector
                              │  per episode: picks a policy (policies.py), opens an EpisodeWriter (storage.py)
                              │  per step:
                              ├─▶ browser.read_state() ──▶ page: __dc.read()      (game_js.py)
                              ├─▶ policy.act(state)
                              ├─▶ browser.act(key, ms) ──▶ page: __dc.act()       (game_js.py)
                              └─▶ EpisodeWriter.write(record)
summarize.py ◀── storage.load_steps / episode_dirs ◀── data/raw/...
```

Python never presses keys itself or waits for a key to be released. It asks the page to hold a
key for `ms`, and the page releases it with a timer. That keeps key timing accurate even when
Python is busy.

## Reproducing a run

The live game can't be replayed, but everything on our side is recorded:

- **Dependencies:** `uv.lock` pins every package version; install with `uv sync --frozen`.
- **Settings:** `session.json` holds the full `CollectConfig`.
- **Randomness:** `session.json` holds the session seed (drawn and saved if you don't pass
  `--seed`). Each `episode.json` holds that episode's own seed and the policy's settings, so a
  policy given the same recorded states makes the same choices (`test_same_seed_gives_same_actions`).
- **Code and game version:** `session.json` holds the git commit (and whether there were
  uncommitted changes), package versions, browser version, and the game script URL, which
  changes when slither.io updates its client.
- **Checks:** `uv run pytest` (offline logic) and `datacollection summarize --check-turns`
  (recorded actions match recorded heading changes).

## Running

See [`DataCollection/README.md`](../../DataCollection/README.md) for commands.
