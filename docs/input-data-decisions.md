# Input data decisions

What data the project collects, why, and how it will be turned into model input. The exact file
format is in [data-format.md](data-format.md). Facts about the game come from reading the live
client's code and testing it (checked 2026-10-18).

## Summary

| Topic | Decision | Status |
| --- | --- | --- |
| Server | Public slither.io servers, through the real game client | Decided |
| Instances | One bot at a time (it plays alongside real people) | Decided |
| Observation source | Game state read from the page's JavaScript every Δ, not screenshots | Decided |
| Screenshots | Debugging only: one saved about every 10 s, plus one just before each death | Decided |
| What is saved | Everything the client holds about snakes, food and prey, unfiltered | Decided |
| Step interval Δ | 200 ms | Starting value; may drop to 100 ms |
| Action | `(key, ms)`: hold Left, Right, or nothing for `ms` ≤ Δ | Decided; boost later |
| Death | Detected from `self.dead` / `dead_mtm`, not `playing` | Decided |
| Bad steps | Flagged per step, never deleted | Decided |
| Model input | Egocentric map + CNN, or entity tokens + transformer | **Open**; the data is the same either way |

## Where the data comes from

### Public server, one instance

The public servers can't be paused, sped up, or run in parallel by us. Data arrives at
real-time speed: one hour of play gives one hour of data, about 18,000 steps at Δ = 200 ms.
Long unattended runs (e.g. overnight with `--policy mixed`) are the way to get volume. Later
phases lean on offline learning for the same reason (see the [roadmap](roadmap.md)).

### Game state, not screenshots

Everything the game draws comes from JavaScript variables the page holds:

- The server sends a snake when it comes near you: id, heading, target heading, speed, size,
  skin, and body points. The client keeps it in `window.slithers`. Later messages move heads,
  add or remove body points, and remove snakes.
- Between server messages the client predicts motion: it moves heads by their speed and turns
  them toward their target heading. It draws each body as a smoothed curve through its points
  (`xx + fx`, `yy + fy`), with thickness from the size value `sc`.
- It draws only what's inside the screen box around the camera (`view_xx ± (mww2/gsc + 84)`).
- **The server only sends nearby things.** During testing the client held 3–5 snakes while the
  leaderboard showed ~465 players. So the state is about what's on screen plus a margin.

Reading that state instead of screenshots:

- loses nothing, because the picture is drawn from it
- is exact (no vision errors) and fast (one call, a few ms, vs. tens of ms for a screenshot)
- lets us draw our own model input at a fixed scale (the game zooms out as you grow)

Screenshots are still taken for **debugging**: checking that our drawing of the state matches
the game, and seeing what happened just before a death.

### Save everything the client holds

Every model input we're considering (maps, entity tokens, direction sensors) can be computed
from the raw state. So the recorder saves **raw state only**, and model inputs are computed
later. Changing the model input never means collecting again. Rules:

- No distance filter. The server already limits the state to nearby things.
- Full body points, not downsampled.
- Keep `id`s (to group body points and track snakes over time), sizes, speeds, target headings,
  death flags.
- Positions rounded to 0.1 world units, angles to 0.001 rad.

Measured sizes: ~15 KB of JSON per step raw, 1.3–5 KB per step compressed (more for big snakes
in crowded areas). That's roughly 25–90 MB per hour of play.

Not saved: cosmetics, skins, names, leaderboard, and the many internal UI variables.

## Timing and actions

### The step

```
t_k                  t_k + ms                        t_k + Δ
 │ read state k       │                                │ read state k+1
 │ keydown ───────────┤ keyup                          │
 └────────────────────┴────────────────────────────────┘
          action k = (key, ms)
```

- Step `k` is read at `t0 + k·Δ`, on a fixed schedule, so delays don't add up. If the loop
  falls more than a step behind, the missed slots are skipped (flagged).
- The key press runs inside the page (a `setTimeout` releases it), so Python doesn't have to
  wake up at exactly the right moment.
- The hold is clamped so the key is up at least 10 ms before the next read. The requested
  length is kept as `requested_ms` when this happens.
- The real key-down and key-up times are recorded with the page's clock (`performance.now()`).

### Why arrow keys

The game turns the snake with the mouse or with Left/Right arrows. Arrow keys give a small,
clean action: which way and for how long. The client counts the frames a key is held and tells
the server to turn by `0.033 × scang × spang` radians per 8 ms frame (Left lowers the heading).
Measured on a new snake: ~4 rad/s, matching the formula below.

The mouse is never moved by the bot, because mouse movement overrides the arrows.

### Human play

A person plays with the arrow keys in a visible window. The page logs real key events, and each
step's action becomes `(key held longest, how long)` within that step, with the exact
`left_ms`, `right_ms` and `boost_ms` saved too. Steps where both arrows were pressed, or the
mouse moved, are flagged.

## Death

The game marks our snake dead (`self.dead = true`, `dead_mtm` set) and plays a death animation
for a few seconds **while `playing` stays true**. Using `playing` alone recorded ~18 steps of a
dead snake as alive in testing. So an episode ends at the first state where `self.dead` is true
or `dead_mtm` isn't −1. That state is saved as a `terminal` record, because it shows what killed
us. The final length is read from the death screen ("Your final length was N"), falling back to
the length in the terminal state.

## Bad steps

Steps are never deleted. Problems are flagged so training can drop or mask them: late reads,
skipped slots, client lag, disconnects, keys still held at the next read, human input during bot
play, mouse movement. The full list is in [data-format.md](data-format.md#flags).

A check (`datacollection summarize --check-turns`) compares each step's heading change with the
turn its action should cause. In testing, the sign matched 90–97% of the time.

## Game mechanics reference

Needed to interpret the data. From the client code unless marked measured.

| Quantity | Formula / value |
| --- | --- |
| Length shown on screen | `floor(15 × (fpsls[sct] + fam / fmlts[sct] − 1) − 5)`; `fmlts[i] = (1 − i/mscps)^2.25`, `fpsls[i] = Σ_{j<i} 1/fmlts[j]`, `mscps` (max segments) = 430 in testing. It measures current mass, which boosting lowers |
| Size scale | `sc = min(6, 1 + (sct − 2)/106)` |
| Turn rate (key held) | `4.125 × scang × spang` rad/s; `scang = 0.13 + 0.87 × ((7 − sc)/6)²` (1.0 small → 0.13 largest); `spang = min(1, sp/4.8)` |
| Normal speed | `ssp = 4.25 + 0.5 × sc`; distance per second ≈ `31.25 × sp` world units (measured ~170 u/s at `sp` 5.79) |
| Boost | Up arrow or Space. The client only *requests* boost; the server decides. Measured on a small snake: speed 5.79 → 14 (~2.4× faster), length drained ~8 per second, and boosting stopped at length ~10 even with the key held. `md` = requested; `sp > fsp` = really boosting |
| Arena | Radius `grd` (32550 in testing), center `(grd, grd)`. Distance to the deadly border = `grd − view_dist` |
| Angles | `x += cos(ang) × speed`, `y += sin(ang) × speed`; y points down the screen |

## Model input (open decision)

The raw state will be turned into model input after collection. All options below use the same
saved data.

### Attributes worth using

Everything is made **egocentric**: positions relative to our head, rotated so our heading points
forward, divided by a fixed radius `R` (about what a player can see). Angles as (cos, sin).

| Group | Attributes |
| --- | --- |
| Self | speed `sp/msp`; boosting (`sp > fsp`); `sc`; log(length); turn-rate factor `scang`; last action |
| Border | distance to edge / `R`; direction to the nearest edge (cos, sin) |
| Enemy heads | relative x, y; distance; relative heading (cos, sin); speed; boosting; log(`sc`); closing speed |
| Enemy bodies | relative x, y; distance; thickness (from `sc`); position along the body (0 = head, 1 = tail); which snake |
| Food | relative x, y; distance; `sz` (big piles come from dead snakes) |
| Prey | relative x, y; `sz`; heading; speed |

Leave out: absolute world position (the border features cover it), our absolute heading, zoom
`gsc`, rank and leaderboard, names and skins, lag values (they're for flagging), raw snake ids.

### Encoder options

| Option | Input | Notes |
| --- | --- | --- |
| Direction sensors + MLP | e.g. 32 directions × ~6 values (nearest body, nearest head, closing speed, food, border) | Fixed size, cheap. Keeps only the nearest thing per direction. Good baseline |
| Egocentric map + CNN | 64×64 grid, ~9 channels (own body, enemy bodies, heads, speed, heading, food, prey, outside arena) | Easy to look at; what the roadmap currently describes |
| Entity tokens + transformer | ~350 tokens (self, border, ≤16 heads, ≤256 body points, ≤64 food, ≤8 prey) | Handles any number of things; attention links heads, bodies and food. Recommended main encoder |

A plain fully connected layer over a flat list of entities works poorly: slots swap when
distances change, the list must be padded and capped, and nothing is shared between slots.
