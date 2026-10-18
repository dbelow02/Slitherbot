# `tests/test_offline.py`

**Job:** check the collector's logic without a browser or network. Run from `DataCollection/`:

```bash
uv run pytest
```

| Test | Checks |
| --- | --- |
| `test_same_seed_gives_same_actions` | Each bot policy, given the same seed and states, makes the same 50 choices (reproducibility) |
| `test_heuristic_turns_toward_food_and_away_from_enemy` | The heuristic turns toward food, and turns away from an enemy head straight ahead |
| `test_turn_rate_matches_measured_small_snake` | `turn_rate` gives 4.125 rad/s for a new snake (~4 measured in the game) |
| `test_human_key_tracker_splits_holds_across_steps` | Key holds that cross step boundaries are split correctly; both-keys steps are flagged |
| `test_is_alive_uses_dead_flag_not_just_playing` | A dead snake counts as dead even while `playing` is true |
| `test_step_flags` | `late`, `lag`, `disconnected` flags |
| `test_complete_record_flags_forced_release_and_interference` | Records get `forced_release`, `human_interference`, and `dt_next_ms` |
| `test_parse_final_length` | Death-screen text parsing, including thousands separators |
| `test_episode_writer_round_trip` | Records written and gzipped are read back the same; `episode.json` has `n_steps` |

The helpers `snake(...)` and `game_state(...)` build minimal fake states with the same fields as
the real ones.

What these tests can't cover (the live game: page loading, key presses reaching the server,
death detection timing) was checked with live runs, and is checked on every real dataset by
`datacollection summarize --check-turns`.
