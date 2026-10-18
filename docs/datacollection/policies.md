# `policies.py`

**Job:** choose an action from the raw state. An action is `Action(key, ms, source)`: hold
`key` (`"left"`, `"right"`, or `None`) for `ms` milliseconds. Left lowers the heading `ang`,
Right raises it.

Several policies exist to make the data varied: random play covers all actions, the heuristic
reaches larger snakes and crowded scenes, and human play adds skilled behavior.

## Constants (from the game's code)

| Name | Value | Meaning |
| --- | --- | --- |
| `TURN_RAD_PER_S` | `0.033 × 125 = 4.125` | Turn per second of a held key, before size and speed factors |
| `SPANG_DIVISOR` | 4.8 | `spang = min(1, sp / 4.8)` |
| `UNITS_PER_S_PER_SP` | 31.25 | Distance per second = `sp × 31.25` world units |

`turn_rate(snake)` = `4.125 × scang × min(1, sp/4.8)` rad/s: about 4.1 for a new snake, down to
~0.5 for the largest. Measured on a new snake: ~4 rad/s.

`wrap_angle(a)` maps an angle to (−π, π].

## Policies

All take their random generator as an argument (`random.Random(seed)`), so the same seed and the
same states give the same actions. `params()` returns the settings saved in `episode.json`.

### `RandomPolicy` (`random`)

Sticky random presses. With probability `p_repeat` (0.6) it repeats the previous key; otherwise
it picks no key with probability `p_none` (0.2), else Left or Right. The hold is uniform in
[0, `max_ms`]. Repeating keys gives longer turns, so the data isn't just jitter.

### `HeuristicPolicy` (`heuristic`)

A simple scripted player: a data source and the baseline to beat, not a strong player.

1. **Food pull:** each food pellet within `food_radius` (700) pulls with weight
   `sz × (1.5 + ahead) / (d + 30)^1.5`, where `ahead` ∈ [−1, 1] favors food in front.
2. **Danger push:** every other snake's body points, its head (weight 2), and where its head
   will be in `head_lookahead_s` (0.5 s; weight 3) push away when within `danger_radius` (450)
   of our head, with weight `(1.2 + ahead) × (450 / d)²` (`d` minus the body's half-width). The
   projected head is capped at half the current distance, so a head coming straight at us is
   never projected behind us (a bug the tests caught).
3. **Border push:** within `border_margin` (900) of the arena edge, push toward the center.
4. **Blend:** goal = food direction, or the arena center if there's no food nearby. The final
   direction mixes goal and danger directions with `alpha = min(1, danger / danger_scale)`
   (`danger_scale` 30), so close danger overrides food.
5. **To an action:** angle error `err` to that direction. Under 0.05 rad: no key. Otherwise
   Left if `err < 0`, else Right, held for `|err| / turn_rate × 1000` ms (capped at `max_ms`).

### `EpsilonHeuristicPolicy` (`eps-heuristic`)

Heuristic, but with probability `epsilon` (0.2) a random action instead. Covers states near
the heuristic's mistakes. `source` records which one acted (`eps-heuristic/random` or
`eps-heuristic/heuristic`).

### `make_policy(name, rng, max_ms, epsilon)`

Builds a policy by name. `"human"` returns `None`: the person at the keyboard acts.
`check_policy_names(names)` raises on unknown names.

## `HumanKeyTracker`

Turns logged human key events into one action per step. `action_for(events, t_start, t_end)`:

- Adds up how long Left, Right and boost were held inside `[t_start, t_end]`. A key held across
  steps counts in each step for the part inside it.
- Action = the arrow held longer, for that long (ties go to Left), or no key.
- Also returns `left_ms`, `right_ms`, `boost_ms`, and `both_keys` (both arrows pressed in the
  step), which the recorder saves.

Unlike bot actions, a human can press at any moment inside the step, not only at its start. The
exact key events are saved in each record (`key_events`) for anyone who needs them.
