# `summarize.py`

**Job:** report what has been collected, and check that recorded actions line up with recorded
states.

## `summarize(root, check_turns=False)`

Reads every `episode.json` under `root` and prints, per policy:

| Column | Meaning |
| --- | --- |
| `episodes`, `steps`, `hours` | How much data |
| `median_final_length`, `p90_final_length`, `max_length` | How well the policy played |
| `bad_steps`, `bad_step_rate` | Flagged records ([flags](../data-format.md#flags)) |
| `gz_mb`, `kb_per_step_gz` | Disk use |

Then totals and a count of end reasons (`death`, `max_steps`, `stopped`, `error`).

`episodes_table(root)` returns the per-episode table as a pandas DataFrame, for your own
analysis.

## `turn_check(ep_dir)`: the turn check

If actions and states were misaligned by even one step, every model trained on the data would
learn the wrong thing, quietly. This check catches it.

For each clean step (no flags) whose action should turn at least 0.2 rad:

- expected turn = `ms / 1000 × turn_rate(snake)`, negative for Left
- actual turn = change in `ang` between this read and the next

It reports:

| Value | Healthy | Meaning |
| --- | --- | --- |
| `checked_steps` | — | Steps used |
| `sign_agreement` | above ~0.9 | Share of steps that turned the expected way |
| `median_actual_over_expected` | ~0.8–1.0 | How much of the expected turn happened |

In testing: sign agreement 0.89–0.97, ratio 0.81–0.97. Why the ratio sits a little under 1
hasn't been pinned down. Agreement near 0.5 would mean the actions are paired with the wrong
states.

Run with `datacollection summarize --check-turns`.
