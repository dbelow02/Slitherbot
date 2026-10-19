# Workflow

The project is building toward this loop:

```
  ┌─────────────┐     session files     ┌──────────────┐
  │ web-player  │ ────────────────────▶ │  notebooks + │
  │  (collect)  │        data/          │   analysis   │
  └─────────────┘                       └──────┬───────┘
         ▲                                     │ rules & strategy ideas
         │                                     ▼
  ┌─────────────┐   new Strategy class  ┌──────────────┐
  │ web-player  │ ◀──────────────────── │   backtest   │
  │   (play)    │                       │   (replay)   │
  └─────────────┘                       └──────────────┘
```

| Step | What happens | Available today? |
| --- | --- | --- |
| 1. Collect | Run the bot in collect mode to record sessions to `data/`. | No. `collect` is the next feature. |
| 2. Explore | Load sessions in a notebook with `analysis.load` and work out the rules: movement, collisions, scoring, and so on. | No. Needs recorded data and the `analysis` package. |
| 3. Strategize | Write a candidate `Strategy` against the `slither-core` interface. | No. Needs the `Strategy` interface. |
| 4. Backtest | Use `analysis.replay` to run the strategy over recorded frames and check its decisions offline. | No. |
| 5. Play | Run the bot in play mode with the new strategy. Play sessions are recorded too, so they feed the next round of analysis. | Partly. `web-player play` plays one round with a random walk, or lets you play with `--human`. |

## Notebook hygiene

- Notebooks are for exploration. Once a function is used in a second notebook,
  move it into the `analysis` package.
- Notebooks read from `data/` and never write raw session files.
