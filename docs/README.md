# Slitherbot Docs

Slitherbot is a Python bot that plays [slither.io](http://slither.io) through
Playwright. The goal is to collect gameplay data, work out the game's rules
from that data, and feed better strategies back into the bot.

## Quickstart

After the one-time setup in [development.md](development.md):

```bash
uv sync --all-packages
uv run web-player play --headed     # watch the bot play one round
uv run web-player play --human      # play a round yourself
```

## Status

| Piece | State |
| --- | --- |
| uv workspace | Built |
| `web-player`: launch, join a round, observe, steer, boost, and detect death or a closed window | Built and tested against the live game |
| `web-player play`: one round, either the bot (random walk) or you (`--human`) | Built |
| `web-player collect`: record observations to `data/` | Planned, next |
| `Strategy` interface and `play --strategy` | Planned |
| `slither-core` package (shared types, data I/O) | Planned |
| `analysis` package and notebooks | Planned |

## Docs

| Doc | What it covers |
| --- | --- |
| [web-player.md](web-player.md) | Running the bot, the `Game` API, observation types, how the bridge to the game works, known gaps |
| [architecture.md](architecture.md) | Goals, the planned three-package workspace, dependency rules, repo layout |
| [workflow.md](workflow.md) | The collect → analyze → strategize → play loop the project is building toward |
| [development.md](development.md) | One-time setup (including WSL), everyday commands, troubleshooting |
