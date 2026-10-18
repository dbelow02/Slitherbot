# Slitherbot docs

A bot that learns to play slither.io: game state → JEPA embedding → reinforcement-learning
policy → arrow-key actions, driven through Playwright.

## Project

| Doc | Contents |
| --- | --- |
| [roadmap.md](roadmap.md) | Phases 0–6, from recon to the live agent, with exit criteria |
| [input-data-decisions.md](input-data-decisions.md) | What data is collected and why; game mechanics; model-input options |
| [data-format.md](data-format.md) | Files, fields and flags written by the collector |

## Code: `DataCollection/` (Phase 2)

| Doc | File |
| --- | --- |
| [overview.md](datacollection/overview.md) | How the package fits together; reproducing a run |
| [\_\_init\_\_.md](datacollection/__init__.md) | `__init__.py`: command entry point |
| [cli.md](datacollection/cli.md) | `cli.py`: command-line options |
| [config.md](datacollection/config.md) | `config.py`: run settings |
| [recorder.md](datacollection/recorder.md) | `recorder.py`: the step loop, death, restarts |
| [browser.md](datacollection/browser.md) | `browser.py`: Playwright control |
| [game_js.md](datacollection/game_js.md) | `game_js.py`: JavaScript in the game page |
| [policies.md](datacollection/policies.md) | `policies.py`: random, heuristic, eps-heuristic, human |
| [storage.md](datacollection/storage.md) | `storage.py`: writing and reading episodes |
| [summarize.md](datacollection/summarize.md) | `summarize.py`: statistics and the turn check |
| [tests.md](datacollection/tests.md) | `tests/test_offline.py` |

## Quick start

```bash
cd DataCollection
uv sync --frozen
uv run pytest
uv run datacollection collect --policy mixed --minutes 30
uv run datacollection summarize --check-turns
```
