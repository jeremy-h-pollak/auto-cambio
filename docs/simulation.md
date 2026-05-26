# Self-play simulation

The simulator plays many computer-vs-computer games and writes a standalone HTML
report plus a console summary. Use it to **measure a strategy against the random
baseline**.

```bash
./run-sim.sh                                        # 500 games, greedy vs random
./run-sim.sh --strategy minimalist --seed 1 -n 2000 --quiet
./run-sim.sh --strategy random --seed 1 -n 1000     # random-vs-random baseline
# (./run-sim.sh forwards all args to `python simulate.py`)
```

## CLI flags (`simulate.py`)

| Flag | Default | Meaning |
|---|---|---|
| `-n, --games` | `500` | number of games to simulate |
| `-o, --output` | `report.html` | path for the HTML report |
| `--strategy` | `greedy` | a profile key from `strategies.PROFILES`, or `random` for the random-vs-random baseline |
| `--seed` | none | random seed for reproducible runs |
| `--quiet` | off | suppress the per-game log; show a progress counter only |
| `--max-turns` | `1000` | safety cap on turns per game |

Without `--quiet`, each game streams its full move log; with `--quiet` you get a
progress line. `--strategy` is validated against `PROFILES` (plus `random`).

## What it measures

The smart strategy plays the `--strategy` profile; the opponent is always the random
strategy. Per game, the simulator balances **which seat is smart** and **who moves
first** (both randomized), so neither seat nor first-move bias contaminates the win rate.
`--strategy random` runs random-vs-random (labelled "Random A / Random B") as a
calibration baseline.

A run produces:

- **Headline cards:** games, smart/random win rate, tie rate, starter win rate, throughput.
- **Win rates:** an SVG **donut** (smart / random / tie split, with the smart win rate in
  the hole) beside the exact win-rate bars.
- **First-move advantage:** smart's win rate moving first vs second, plus starter-wins
  overall and decisive-only — isolates the starting-player edge from the strategy edge.
- **Game-length distribution:** an SVG **bar chart with a labelled y-axis**; hover a bar
  for its exact count.
- **How games end:** `cambio` / `empty` / `capped` breakdown — an SVG donut beside the bars.
- **Run-time** and **other statistics:** avg scores, avg margin, avg length,
  Cambio-caller success rate, avg snaps/game per seat.
- **Action distribution — observed vs expected:** per-seat mix of every decision. The
  random seat's observed shares are checked against its coded probabilities (the cleanest
  check is Call Cambio ≈ 8%); the smart seat is deterministic, shown as "—".
- **Interesting results:** an auto-generated highlights block at the bottom — a
  plain-language headline verdict (bucketed against the ~75% ceiling), notable outliers
  (high tie rate, capped games, early Cambio calls, favourite special, lopsided wins…),
  and first-move/fairness commentary. Each highlight is colour-keyed by tone.

Charts are **inline SVG** (no JavaScript, no CDN); reports stay self-contained HTML that
opens offline with **no third-party dependencies**. The SVG primitives live in
[`game/charts.py`](../game/charts.py), the highlight heuristics in
[`game/insights.py`](../game/insights.py), and assembly in
[`game/report.py`](../game/report.py) (`compute_stats` + `render_html`).

## How it runs games — and the snap symmetry

The simulator (`game/simulator.py`) **does not use `GameEngine`**. It drives
`rules.apply_move` directly, for a deliberate reason documented at the top of the file:

> The engine runs a computer snap-check after *every* internal `apply_move`, which gives
> a bot ~3× the snap opportunities a turn-boundary player gets and skews self-play
> results. Here both seats get a single, **symmetric** snap sweep at each turn boundary,
> and we skip the `"start"` action (which would wipe only `player_known`) so both seats
> keep the symmetric opening knowledge `[F, F, T, T]`.

Key pieces:

- **`play_game(strat_by_seat, starting_seat, smart_seat, seat_strategy, max_turns)`** →
  a `GameRecord` (winner, scores, length, ending, per-seat snap/special/action tallies,
  log). It runs an opening `_snap_sweep`, then alternates `_take_turn` + `_snap_sweep`
  until `game_over` or the turn cap.
- **`_snap_sweep`** checks both seats against the current discard top, applies eligible
  snaps (resolving simultaneous eligibility with a coin flip), and re-evaluates after
  each snap. This is the symmetric counterpart to the engine's per-move snapping.
- **`run_simulation(n, smart, opponent, seed, …)`** → `(records, timing)`. Seeds the RNG
  once, randomizes the smart seat and starter each game.

Because `_take_turn` consumes no RNG for its bookkeeping, **seeded runs are bit-for-bit
reproducible**. See [architecture.md](architecture.md) for the broader engine-vs-simulator
distinction.

## Interpreting results — the ~75% ceiling

Strong low-hand strategies converge near a **~75% win rate vs. random** (e.g. Minimalist
75.4%, Bargain Hunter 75.2%) — two quite different bots tie, which says the *opponent* is
the limiting factor, not the strategy. Random is too weak to separate good strategies.
To rank strategies against each other, use the [tournament](tournament.md).

## Logging a run

Filed runs are archived under `reports/<date>-<time>-<id>/` with a `summary.md`, via the
`/file` skill — see [reports-workflow.md](reports-workflow.md). The default `report.html`
is gitignored, so file it (which copies it into a dated folder) to keep it.
