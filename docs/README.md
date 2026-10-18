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

From the `Slitherbot/` folder:

```bash
uv sync --frozen
uv run pytest
uv run datacollection collect --policy mixed --minutes 30
uv run datacollection summarize --check-turns
```

## Environment: one uv workspace

The repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): every
package (`DataCollection/` now, `DataProcessing/` and others later) shares **one** virtual
environment and **one** lock file, both at the top level.

| File | Role |
| --- | --- |
| `pyproject.toml` (top level) | Lists the member packages, the shared dev tools (pytest), and where the tests are |
| `uv.lock` (top level) | Exact versions of every package, for all members together |
| `.python-version` (top level) | Python 3.12 |
| `.venv/` (top level) | The one environment. Point your editor's interpreter at `Slitherbot/.venv/bin/python` |
| `<Package>/pyproject.toml` | That package's own name, dependencies and commands |

`uv sync` installs every member as an editable package, so code changes apply without
reinstalling. `uv run ...` works from any folder in the repo and always uses the top-level
`.venv`.

**Adding a package** (e.g. `DataProcessing`):

1. Create it: `uv init --package --lib DataProcessing` (uv adds it to `members` for you), or
   make the folder and its `pyproject.toml` by hand and add `"DataProcessing"` to `members` in
   the top-level `pyproject.toml`.
2. In the top-level `pyproject.toml`, add `"dataprocessing"` to `dependencies` and
   `dataprocessing = { workspace = true }` to `[tool.uv.sources]`, so `uv sync` installs it.
3. To use another member, list it in that package's own `dependencies` (e.g. `"datacollection"`)
   and add the same `{ workspace = true }` line under its `[tool.uv.sources]`.
4. Add its tests folder to `testpaths` in the top-level `pyproject.toml`.
5. `uv sync`.

**Adding a dependency** to one package: `uv add --package datacollection <name>`. Shared dev
tools: `uv add --dev <name>` from the top level.
