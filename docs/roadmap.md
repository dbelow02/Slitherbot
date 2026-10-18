# Slitherbot Roadmap

Goal: an agent that plays slither.io by itself.

```
                read game state every Δ                                hold arrow key for x ≤ Δ
Browser (Playwright) ──▶ raw state ──▶ egocentric map ──▶ JEPA encoder ──z_t──▶ RL policy ──(key ∈ {Left, Right, none}, x)──▶ Browser
        │                    │
        │                    └──▶ reward / death signal / probe labels (training only)
        └── occasional screenshot ──▶ debugging only (checks that the map matches the screen)
```

Phases run mostly in order. Each one ends with an **exit criterion**, so you know when it's done
and can move on.

**Status (2026-10-18):** the data collector (`DataCollection/`) is built and tested live; it
covers most of Phases 0–2 except the map renderer. Next: collect data, write the map renderer,
and measure the remaining Phase 0 numbers. Checked boxes below are done. Details of the data
decisions are in [input-data-decisions.md](input-data-decisions.md); the file format is in
[data-format.md](data-format.md).

---

## Phase 0: Recon and key decisions (a few days)

### Decisions made

| Topic        | Decision |
| ------------ | -------- |
| Server       | **Public slither.io servers**, played through the real client. |
| Observation  | **Game state read from the page every Δ**, drawn by us into an **egocentric map**: a small multi-channel image centered on our head, rotated so our heading points up, at a fixed world scale. |
| Screenshots  | **Debugging only.** Taken occasionally (e.g. every ~10 s and just before each death) to check that our maps match what the game shows. Not used for training. |
| Action       | **A random arrow-key press between two state reads**: `(key ∈ {Left, Right, none}, x)`, holding the key for `x` seconds, `x ≤ Δ`. |
| Labels       | Length, rank, death, and probe targets, all computed from the same game state. |

Why game state instead of screenshots: see [input-data-decisions.md](input-data-decisions.md#game-state-not-screenshots).

Consequences of the other choices:
- **Public servers can't be paused or sped up, and only one copy should run.** Data comes in at
  real-time speed (1 hour of play = 1 hour of data). Phase 5 therefore leans on offline RL and
  planning inside the JEPA rather than lots of live trial and error. Keep it to **one bot
  instance at a time** and follow the game's terms of service. The bot plays alongside real people.
- **Random actions die fast.** Most episodes will be short, with small snakes in uncrowded areas.
  Phase 2 still needs the scripted bot and human play to cover large snakes and crowded fights.

### What one step looks like

```
t_k                    t_k + x                         t_k + Δ
 │ read state k         │                                │ read state k+1
 │ keydown(key) ────────┤ keyup(key)                     │
 └──────────────────────┴────────────────────────────────┘
          a_k = (key, duration = x)
```

Record the **actual** timestamps of each state read, keydown and keyup, not just the scheduled
ones, and take them from in-page `performance.now()` so they share one clock. The JEPA needs to
know exactly which action fell between which two states.

### Recon results (live client, checked 2026-10-18)

- **Some globals were renamed.** The current client uses `window.slither` (was `snake`),
  `window.slithers` (was `snakes`), and `window.slither_count`. Older bot scripts that use
  `window.snake` won't work as written.
- **How the client draws other snakes.**
  - The server sends a snake when it comes near you: id, heading, target heading, speed, `fam`,
    skin, and body points. The client adds it to `slithers[]`.
  - Further messages move heads and add or remove body points. A "remove" message either starts a
    death animation (`dead = true`) or deletes the snake.
  - Every frame, the client predicts motion between server updates: it moves heads by speed and
    turns them toward `wang`. It then draws each body as a smoothed curve through `pts`
    (`xx + fx`, `yy + fy`), with thickness scaled by `sc`.
  - A snake is drawn only if one of its points is inside the view box
    `view_xx ± (mww2/gsc + 84)`, `view_yy ± (mhh2/gsc + 84)`.
  - **The server sends only nearby snakes**: 3 in `slithers` while the leaderboard showed 465
    players. So the state has about what's on screen plus a margin, not the whole map.
- **Arrow keys work.** A synthetic `keydown`/`keyup` for `ArrowLeft` sets `window.kd_l` and turns
  the snake. A length-11 snake turned about **4 rad/s (~230°/s)** while the key was held and stopped
  as soon as the key was released. So holding for **~0.8 s already turns ~180°**, and anything
  over ~1.6 s is a full circle. Pick the range of `x` with that in mind. Large snakes are thought to
  turn more slowly, so measure turn rate against length (`window.slither.sct`).
- **The bottom-of-screen text is HTML, not part of the canvas.** `window.lbf.innerText` returns
  `"Your length: 11\nYour rank: 352 of 465"`. There is **no in-game clock**, so record time
  yourself.
- **Length can be computed from game state**, and the result matched the on-screen value:
  `Math.floor(15 * (fpsls[sct] + fam / fmlts[sct] - 1) - 5)`, using `window.slither.sct` and
  `.fam`.
- **Death:** `window.playing` becomes `false`, `window.slither` becomes `null`, and
  `window.lastscore.innerText` reads `"Your final length was N"`. The restart button reads
  "Play Again".
- **Arena geometry:** `window.grd` (32550) is the arena radius, and the arena center is at
  `(grd, grd)`. `window.view_dist` is the camera's distance from the center, so
  `grd - view_dist` is the **distance to the deadly border**.

### What is collected

Everything the client holds about snakes, food and prey, unfiltered, plus our snake's state and
timing. The field list is in [data-format.md](data-format.md); the reasons are in
[input-data-decisions.md](input-data-decisions.md#save-everything-the-client-holds).

### The egocentric map (first version)

One of the model-input options; the choice between this and entity tokens is still open (see
[input-data-decisions.md](input-data-decisions.md#model-input-open-decision)). The data is the
same either way.

- **Size and scale:** e.g. 64×64 cells covering a fixed world radius `R_map`. Start with
  `R_map` ≈ the half-width a mid-sized snake can see on screen (`mww2/gsc`, measured), so the
  agent sees about what a player sees.
- **Frame:** our head at the center, rotated so our heading points up.
- **Channels** (one value per cell):
  1. own body (drawn as thick lines between points, thickness from `sc`)
  2. enemy bodies
  3. enemy heads
  4. enemy speed at head cells (shows boosting enemies)
  5. enemy heading at head cells, as cos and sin, rotated into our frame (2 channels)
  6. food, summed `sz` per cell
  7. prey
  8. outside the arena (1 beyond the border)
- **Extra inputs (not drawn):** own speed, length, `sc`, distance to border, last action.

Render the maps in Python (NumPy, or Numba if needed) from the saved raw state. Then changing
channels, `R_map`, or resolution only means re-rendering, not re-collecting.

### Still to do in Phase 0

- [x] A script that starts a round, reads the state every Δ, holds Left / Right / nothing for a
      random `x`, detects death, restarts, and saves debug screenshots. Built as the
      `DataCollection` package ([docs](datacollection/overview.md)).
- [ ] **Measure how long a state read takes**, with in-page filtering, in crowded and empty
      areas. If it's well under 10 ms, consider Δ = 100 ms instead of 200 ms.
- [ ] **Choose Δ and the distribution of `x`.** Starting point: Δ = 200 ms, `x` uniform in
      [0, Δ]. That allows 0 to about 45° per step on a small snake. Then measure turn rate vs.
      length and adjust.
- [ ] **Write the map renderer and check it against screenshots.** Draw the map without rotation at
      the screen's scale and overlay it on a debug screenshot taken at the same moment. Bodies,
      heads, food, and the border should line up.
- [ ] **Measure the visible radius** (`mww2/gsc`) for small and large snakes, and pick `R_map`.
- [x] Check that the game runs headless on the public server (it does, with headless Chrome).
      **Fix the viewport size** (1280×800 by default). It sets how far the client sees, and possibly which
      snakes the server sends.
- [ ] **Compute:** maps are small (64×64×9), so Apple Silicon (MPS) is enough for the JEPA and RL
      at first.

**Exit:** the collector runs 20 episodes with no human help. [input-data-decisions.md](input-data-decisions.md) records Δ, the
`x` distribution, the action set, `R_map`, map resolution and channels, viewport, the measured
state-read time, and turn rate vs. length. The map/screenshot overlay check passes.

---

## Phase 1: Game environment wrapper (1–2 weeks)

A reusable package (`slither_env`) that every later phase imports. It grows out of the
`DataCollection` package, which already has the browser control, state reader, action writer and
scheduler.

- [x] `SlitherBrowser`: launches Playwright with a **fixed viewport**, loads the game, starts a round, declines non-essential cookies, closes
      popups/ads. Keeps the mouse still so it never overrides the arrow keys.
- [x] **State reader.** One `page.evaluate` that returns the state as compact JSON: scalars plus
      every entity the client holds, rounded. Every JS name lives in this one
      module (the client already renamed `snake` → `slither` once).
- [ ] **Map renderer** (`render_map(raw_state) -> (channels, extras)`). Pure function, shared
      by the live env, offline dataset tools, and training. Unit-test it on saved states.
- [x] **Debug screenshots.** `page.screenshot()` every N steps and on the last step before
      death, saved with the step index. Never on the critical path: take it right after the
      keyup, not between the state read and the keydown.
- [x] **Action writer.** `(key, x)` → `keydown`, wait `x`, `keyup`, recording the real
      timestamps of both. Confirm the key registered with `kd_l` / `kd_r`. Always send `keyup`
      before the next state read, including on errors, so a key never stays stuck down.
- [x] **Fixed-interval scheduler.** Step `k` starts at `t_0 + kΔ`, not "Δ after the last step
      finished", so delays don't add up. Log how late each step is. Flag a step as **bad** when it
      is late by more than ~20% of Δ, `lag_mult` ≠ 1, `fps` drops sharply, or `connected` is
      `false`.
- [x] **Death and restart.** Death = `slither.dead` true or `dead_mtm` ≠ −1 (`playing` stays true
      for a few seconds of death animation). Save `lastscore.innerText`, press Play Again, wait
      for a live round, start a new episode.
- [ ] `SlitherEnv(gymnasium.Env)`: `reset()`, `step(action) -> obs, reward, terminated,
      truncated, info`. `obs` is the map plus extra inputs. `info` holds the raw state,
      timestamps, and the bad-step flag.
- [ ] **Action space.** Raw: `(key ∈ {Left, Right, none}, x ∈ [0, Δ])`. For RL, also offer a
      discrete version: `none` plus Left/Right × 3 durations (e.g. Δ/3, 2Δ/3, Δ) = 7 actions.
      Data collection always logs the raw `(key, x)`.
- [x] **One instance only.** No parallel browsers, because we're on the public server. Make the
      env robust to running unattended for hours instead (reconnects, page reloads, a watchdog).

**Exit:** a random agent plays 100 episodes back to back with no human help. You have measured
step lateness, bad-step rate, state-read and render time, and crash/reconnect rate.

---

## Phase 2: Data collection (1–2 weeks, then ongoing)

This is the current `DataCollection/` package. Data arrives at real-time speed from one
instance, so **plan to run collection unattended for long stretches** (e.g. overnight) from the
start.

A JEPA world model learns only what the data shows, so you need a **mix of behaviors**. All of
them use the same `(key, x)` actions so the data is consistent:

| Policy                          | Why                                              |
| ------------------------------- | ------------------------------------------------ |
| Random `(key, x)`               | Broad, unbiased action variety. Your main source |
| Scripted heuristic bot          | Long-lived snakes, large sizes, crowded scenes   |
| Human play (arrow keys only)    | Skilled behavior; useful for behavior cloning    |
| ε-noised heuristic              | Covers states near the heuristic's mistakes      |

- [x] **Recorder.** Each step saves: the **raw state** (not the map), the action `(key, x)`, the
      scheduled and actual timestamps (state read, keydown, keyup), the bad-step flag, and reward
      terms. Debug screenshots are saved as image files indexed by step.
- [x] **Storage.** Group by episode. Raw states have variable-length entity lists, so they are
      stored as gzipped JSON lines per episode ([data-format.md](data-format.md)). Still to do:
      rendered maps as a **cache** (zarr / `.npz` shards) keyed by renderer version, so they can be deleted and
      rebuilt. Version the dataset (`v0`, `v1`…).
- [x] **Heuristic bot.** Picks a target heading from the state (toward food, away from nearby
      snake bodies and the border), then turns it into an action: key = which way to turn,
      `x` = angle error ÷ measured turn rate (capped at Δ). It's also the **baseline to beat**.
- [x] **Human recording mode.** You play with the arrow keys while in-page key listeners log key
      timings. Convert those to `(key, x)` per step so it matches the bot data. If both keys are
      pressed in one step, keep the one held longer and flag the step.
- [ ] **Dataset tools.** Done: summary stats (`datacollection summarize`: episodes, hours,
      lengths, bad-step rate, size). Still to do: an episode viewer that plays maps back next to
      the nearest debug screenshot, an action histogram, and death causes.
- [x] **Validation.** For each step, compare the change in heading (`slither.ang`) with what the
      action should give (`±x × turn rate`): `datacollection summarize --check-turns`. A mismatch
      means states, actions, or timestamps are misaligned. Off-by-one-step errors here quietly
      break the action-conditioned JEPA. Still to do: spot-check maps against debug screenshots.

**Exit:** about 10–20 hours of gameplay across the policies above (at Δ = 200 ms that's
~180k–360k steps), passing validation with a low bad-step rate. Write down the heuristic bot's
median and 90th-percentile final length.

---

## Phase 3: Quick baselines (a few days)

Get reference numbers before building anything complicated.

- [ ] **Behavior cloning from maps:** a small CNN trained on heuristic or human data → `(key, x)`.
      Gives a maps-to-action number and a first test of the full live loop (state read → map →
      model → key press) against the real game, including whether it fits in the time budget.
- [ ] **Random-init encoder + linear probe:** the score a JEPA encoder has to beat in Phase 4.

**Exit:** a results table with random agent, heuristic, and behavior cloning (median / p90
length, survival time).

---

## Phase 4: JEPA world model (3–6 weeks)

The input is the egocentric map (plus extra inputs), not pixels. One time step = Δ. Bad steps are
masked out of the loss.

Build it in stages, from simple to the full version:

1. **v0: single-map JEPA (I-JEPA style).** Context encoder + EMA target encoder + predictor that
   predicts embeddings of masked regions of one map. Small ViT (patch 4–8 on 64×64) or a CNN.
   Shows the training setup works.
2. **v1: multi-step JEPA.** Encode a short stack of maps and predict embeddings of masked
   space-time regions (V-JEPA style). Captures motion: where enemies are heading and how fast.
3. **v2: action-conditioned predictor.** `P(z_t, a_t, a_{t+1}, …) → ẑ_{t+1..t+H}`, with the
   target encoder supplying the true `z_{t+k}`. Encode each action as
   `[one-hot(key), x / Δ]`. This makes it a **world model** in embedding space, which Phase 5
   plans with (like V-JEPA 2-AC / DINO-WM). **This is the stage that matters most:** with clean
   maps, perception is easy, and the value is in predicting what happens next.

Training details:
- [ ] Prevent collapse (all maps mapping to the same embedding) with an EMA target + stop-gradient,
      or a variance/covariance penalty (VICReg / SIGReg-style). Track **embedding std, effective
      rank (RankMe), and predictor loss** on held-out episodes.
- [ ] Split train/val by episode, not by step.
- [ ] Maps are centered and heading-up by design. Avoid augmentations that break this (shifts,
      rotations). Mirroring left↔right is fine **if you also swap Left/Right in the action**.
- [ ] Turn rate depends on size, so give the predictor `sc` (or length) as an extra input.

**Evaluation: linear probes on frozen embeddings.** Labels come from the raw state:
- own speed and length
- distance and direction to the nearest enemy body point
- food density by direction
- distance to the border
- **death within the next N steps** (most useful for RL)
- for v2: probe accuracy on *predicted* embeddings at k = 1, 3, 5 steps ahead, including the
  future distance to the nearest enemy and future death. Also check that the predicted turn
  matches the action (Left vs. Right vs. none).

The inputs are drawn from the same state, so probes on the *current* step will be easy. The
real test is the *future* probes from v2.

**Exit:** the JEPA's probes clearly beat the random-init encoder (Phase 3), and v2's predictions
keep useful probe accuracy for at least ~1 s ahead (5 steps at Δ = 200 ms).

---

## Phase 5: Reinforcement learning on the embedding (3–6 weeks)

The policy takes `z_t` (plus the extra inputs and, optionally, the last action) and outputs
`(key, x)`, or one of the 7 discrete actions.

Because there is only one real-time instance, **live trial and error is the scarcest resource**.
Do as much learning as possible from logged data and inside the JEPA world model.

- [ ] **Reward.** `Δlength` plus a death penalty, maybe a small per-step survival bonus. Kill
      rewards (`kill_count`) are optional, add them later. Normalize the scale.
- [ ] **Reward and death heads** trained on frozen embeddings using the logged data. These are
      also a check: if a linear head can't predict death, the embedding isn't ready for RL.
- [ ] Try these in order:
  1. **Offline RL / BC+RL** on the collected dataset (IQL, or behavior cloning warm-started then
     fine-tuned). No live game needed during training.
  2. **Planning with the world model (MPC).** Each step, sample candidate action sequences
     (e.g. CEM over `(key, x)` for the next H steps), roll them out with the v2 predictor, score
     them with the reward/death heads, and execute the first action. Needs no live training,
     only the per-step compute.
  3. **Train the policy inside the world model** (Dreamer / TD-MPC2 style), then **fine-tune
     live in small amounts** with the single instance, adding those episodes to the dataset.
- [ ] **Latency budget.** The decision has to be made between the state read and the keydown,
      and every millisecond of thinking delays the action within its Δ window. Aim for
      state read + render + encode + policy (or planning) < ~50 ms at Δ = 200 ms. Log it per
      step. If MPC is too slow, distill it into a fast policy.

**Exit:** an RL or planning agent beats the heuristic bot's median final length over ≥ 50 live
episodes.

---

## Phase 6: Full agent and data flywheel (1–2 weeks, then ongoing)

- [ ] `slitherbot play`: one command that runs the full agent live on the public server, with
      logging. Same env, same Δ, same renderer version, same action format as data collection.
- [ ] Live monitoring: length over time, death causes, step lateness, decision latency, bad-step
      rate, and an optional live view of the map with probe predictions.
- [ ] **Death review.** For each death, save the last few maps and the debug screenshot taken
      just before it, so you can see what the agent missed.
- [ ] **Flywheel.** Every live episode is recorded in the same dataset format. Retrain or
      fine-tune the JEPA on the new states the agent reaches (reduces mismatch between training
      and live data), then retrain the policy. Live time is limited, so let the agent play
      unattended and do the retraining in between.
- [ ] Optional: fine-tune the encoder end to end with a small learning rate once the policy is stable.
- [ ] Optional: add boost (Up arrow, `kd_u`) as a third action dimension once turning works well.
- [ ] Optional: a second, coarser map (larger `R_map`) if deaths show the agent needs to see
      farther.

**Exit:** each flywheel round reliably improves on the previous model.

---

## Suggested repo layout

`DataCollection/` is a standalone uv project right now. Several stages need the same env code, so
a **uv workspace** keeps them separate while sharing that code:

```
Slitherbot/
├── pyproject.toml            # [tool.uv.workspace] members = ["packages/*"]
├── packages/
│   ├── slither_env/          # Playwright control, state reader, map renderer, arrow-key actions, gymnasium env  (Phase 1)
│   ├── datacollection/       # policies, recorder, dataset tools (now: DataCollection/)                         (Phase 2)
│   ├── jepa/                 # models, training, probes                                                         (Phase 4)
│   ├── rl/                   # reward heads, offline RL, planning                                               (Phase 5)
│   └── agent/                # live inference loop, monitoring                                                  (Phase 6)
├── configs/                  # one config per experiment
├── data/                     # gitignored; raw states, map caches, debug screenshots, by version
└── docs/                     # roadmap, data decisions, data format, one page per Python file
```

Tooling: `torch` (MPS / CUDA), `playwright`, `gymnasium`, `numpy` (+ `numba` if rendering is
slow), `pyarrow`, `zarr`, an experiment tracker (TensorBoard or W&B), `pytest` for the state
reader, renderer, and data checks.

---

## Main risks

| Risk | What to do about it |
| ---- | ------------------- |
| One real-time instance on a public server means little live data | Run collection unattended for long stretches; offline RL first; plan and train inside the JEPA world model |
| Client update breaks the JS state reader (`snake` → `slither` already happened once) | Put all JS access in one module with a smoke test that runs at the start of every session |
| Map renderer bug: the map doesn't match the game | Overlay check against debug screenshots in Phase 0; spot checks in the dataset viewer; unit tests on saved states |
| Client state is the client's prediction between server updates, not exact server truth | That's also what a human sees, so it's fine; flag laggy steps where prediction drifts most |
| Map radius too small: the agent can't see threats a player would see | Pick `R_map` from the measured visible radius; review deaths; add a coarser second map if needed |
| Anti-bot measures / effect on real players | One instance only, respect the game's terms, stop if the account or IP gets flagged |
| Lag or slow state reads break the action-to-state link | Fixed-schedule stepping, real timestamps, bad-step flags masked out of training |
| Turn rate changes with snake size, so the same `x` means different turns | Measure turn rate vs. length; give `sc` to the model; check with the heading-change validation |
| Random-action data covers mostly small, short-lived snakes | Mix in heuristic and human play; ε-noise; Phase 6 flywheel |
| JEPA collapse, or a world model that predicts only the easy parts | Collapse metrics from day one; judge it by the *future* probes (enemy distance, death), not current-step probes |
| Inference too slow for the step interval | Small encoder, measure latency in the Phase 3 BC loop, distill planning into a fast policy |

---

## Next concrete steps

1. Run unattended collection (`datacollection collect --policy mixed`) and record a few hours of
   human play. Check each batch with `datacollection summarize --check-turns`.
2. Write `render_map` and check it against the debug screenshots.
3. Measure state-read time, visible radius, and turn rate vs. length from the collected data.
   Settle Δ, the `x` range, and `R_map` in [input-data-decisions.md](input-data-decisions.md).
4. Turn the collector's browser and step loop into `SlitherEnv`.
