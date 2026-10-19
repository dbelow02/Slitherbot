# Architecture

## Goals

1. **Data collection and play.** A Playwright-driven bot plays on the real
   website. It runs in one of two modes:
   - **collect**: play and record observations for later analysis.
   - **play**: act according to a chosen strategy.

   Strategies are swappable and all follow the same interface.
2. **Rule exploration.** Scripts and notebooks analyze the collected data to
   work out the game's rules and evaluate candidate strategies. Those results
   feed back into the bot.

## Packages

The repo is one [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
with a single lockfile. It is designed around three member packages. Only
`web-player` exists so far.

```
          slither-core   (shared types, Strategy protocol, data I/O)   [planned]
           ▲         ▲
           │         │
   web-player       analysis                                           [planned]
  (+playwright)    (+polars, jupyter)
    [built]
```

### `web-player` (built)

Everything that touches the real website. Its public API is one class, `Game`,
plus plain data types. See [web-player.md](web-player.md) for the full
reference.

```python
with Game(headless=False) as game:
    obs = game.start_round("bot")       # blocks until alive
    while obs.alive:
        game.act(Action(angle, boost))  # held until the next act()
        obs = game.observe()
```

- `game.py` owns the browser and translates every Playwright failure into
  `GameError` or `GameClosed`.
- `bridge.js` is the only code that knows slither.io's internals.
- `observation.py` holds the data types. They have no browser dependency.
- `cli.py` provides `web-player play`, for bot play or human play (`--human`).

### `slither-core` (planned)

The shared contract between the bot and the analysis code.

- **Models.** The types in `web_player/observation.py` move here unchanged.
  Recorded data carries a `schema_version`.
- **Strategy interface.** A `Strategy` protocol that maps an `Observation` to
  an `Action`. It knows nothing about browsers.
- **Data I/O.** Reading and writing session files (JSONL or Parquet).

### `analysis` (planned)

Reusable code for the notebooks.

- **Loading.** Session files → DataFrames.
- **Replay.** Run any `Strategy` over recorded frames to backtest it offline,
  without a browser.

## Dependency rules

These rules are the reason for splitting the code into packages rather than
folders:

- `slither-core` stays lightweight: stdlib, or pydantic at most. It never
  imports Playwright, polars, or Jupyter.
- `analysis` never depends on `web-player`, so notebooks never pull in
  Playwright.
- `web-player` never depends on `analysis`.
- Strategies depend only on `slither-core` types, so the same strategy object
  runs live in `web-player` and offline in `analysis.replay`.

Until `slither-core` exists, `web_player/observation.py` follows the same rule:
it imports nothing from Playwright or the rest of `web_player`.

## Repo layout

Today:

```
Slitherbot/
├── pyproject.toml            # virtual workspace root: members = ["packages/*"]
├── uv.lock
├── .python-version           # one interpreter for the whole workspace
├── docs/                     # these markdown files
└── packages/
    └── web-player/
        ├── pyproject.toml    # depends on playwright; `web-player` script
        ├── src/web_player/
        │   ├── __init__.py   # the public API
        │   ├── game.py
        │   ├── observation.py
        │   ├── bridge.js
        │   └── cli.py
        └── tests/
```

Planned additions:

```
├── packages/
│   ├── slither-core/src/slither_core/   # models.py, strategy.py, io.py
│   └── analysis/src/analysis/           # load.py, replay.py
├── notebooks/                           # exploration; imports `analysis`
└── data/                                # gitignored raw session files
```

## Data conventions (planned)

These take effect once `collect` mode exists:

- Each bot run writes one session file under `data/`.
- Every file records its `schema_version`. When the schema changes, bump the
  version and keep the loaders able to read older versions.
- `data/` is gitignored; it is already listed in `.gitignore`. Raw sessions
  are inputs, not source.
