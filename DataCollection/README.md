# DataCollection

Plays slither.io on the public servers through Playwright and records the raw game state every
Δ (default 200 ms), a 640-px image of the game from the same moment, and the arrow-key action
taken after each read. Phase 2 of the
[roadmap](../docs/roadmap.md).

Run **one instance at a time**: the bot plays alongside real people.

Documentation: [docs/](../docs/README.md). Data format: [docs/data-format.md](../docs/data-format.md).
Each Python file: [docs/datacollection/](../docs/datacollection/overview.md).

## Setup

This package is part of the Slitherbot uv workspace: one `.venv` and one `uv.lock` at the top
level ([details](../docs/README.md#environment-one-uv-workspace)). From the `Slitherbot/` folder:

```bash
uv sync --frozen
```

`--frozen` installs the exact versions in `uv.lock`. The `datacollection` commands below work
from any folder in the repo. The browser is your installed Google Chrome by default. To use Playwright's own Chromium instead, install it once and pass `--channel chromium`:

```bash
uv run playwright install chromium
```

## Collect

```bash
# Random arrow-key presses, headless, for 30 minutes
uv run datacollection collect --policy random --minutes 30

# Scripted bot: steers toward food, away from snakes and the border
uv run datacollection collect --policy heuristic --episodes 20

# Scripted bot with 20% random actions
uv run datacollection collect --policy eps-heuristic --epsilon 0.2 --minutes 60

# A different bot policy each episode, by weight (good for long unattended runs)
uv run datacollection collect --policy mixed --mix random=0.4,heuristic=0.3,eps-heuristic=0.3 --minutes 480

# You play with the arrow keys in a visible window
uv run datacollection collect --policy human --headed --episodes 5
```

**Human play:** click the game window once so it has keyboard focus, then move the mouse
**outside** the window. Mouse movement steers the snake and would override your arrow keys.

Frames: `--frame-width 320` for smaller images, `--frame-width 0` for none (~430 MB per hour at
the default 640).

Stop any run with Ctrl+C; the current episode is saved. Data goes to `Slitherbot/data/raw`
unless you pass `--out` (a relative `--out` is relative to the folder you run from). Run `uv run datacollection collect --help` for every option.

## Check the data

```bash
uv run datacollection summarize                # episodes, hours, lengths, bad-step rate, size
uv run datacollection summarize --check-turns   # do heading changes match the recorded actions?
```

## Tests

```bash
uv run pytest
```

From `Slitherbot/` this runs every package's tests (listed in the top-level `pyproject.toml`);
from `DataCollection/` only this package's. The tests need no browser or network.
