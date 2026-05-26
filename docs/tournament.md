# Tournament & ratings

The tournament plays **every strategy against every other** in a round robin and ranks
them all on a single **Elo-style scale**. Where the [simulator](simulation.md) measures a
strategy against random, the tournament separates strategies that the simulator's ~75%
ceiling can't.

```bash
./run-tournament.sh                                 # 15 profiles + random, 100 games/pairing
./run-tournament.sh -k 400 --seed 1 --quiet
./run-tournament.sh --no-random -o profiles.html    # profiles only, no random anchor
# (./run-tournament.sh forwards all args to `python tournament.py`)
```

## CLI flags (`tournament.py`)

| Flag | Default | Meaning |
|---|---|---|
| `-k, --games` | `100` | games per pairing (a multiple of 4 balances sides exactly) |
| `-o, --output` | `tournament.html` | path for the HTML report |
| `--seed` | none | random seed for reproducible runs |
| `--no-random` | off | exclude the random baseline (profiles only) |
| `--max-turns` | `1000` | safety cap on turns per game |
| `--quiet` | off | suppress per-pairing progress |

The output is a standalone HTML report plus a console rankings table, via
[`game/tournament_report.py`](../game/tournament_report.py). The report has:

- an SVG **rating diverging-bar chart** — each entrant's Elo drawn left/right of the 1500
  anchor, so the skill spread reads at a glance — above the **rankings table**;
- the colour-graded **head-to-head win-rate matrix**;
- the **methodology** note; and
- an **Interesting results** highlights block: champion, cellar dweller, skill spread (in
  expected-win-ratio terms via the 400 Elo ≈ 10:1 rule), the most dominant matchup, and the
  biggest upset (a lower-ranked entrant winning a head-to-head). It is dependency-free
  inline SVG/HTML — charts from [`game/charts.py`](../game/charts.py), highlight heuristics
  from [`game/insights.py`](../game/insights.py).

## The field

`entrants(include_random=True)` returns the **15 named profiles** (in `PROFILES` order)
plus **Random**. So the default field is 16 entrants → C(16, 2) = 120 pairings × `k`
games. Each entrant is an `Entrant(key, name, strat)`.

## How it runs — balanced round robin

`run_tournament(field_, k, seed, max_turns, on_pair)`:

- Plays every unordered pair `k` times, driven through `simulator.play_game` so both
  seats get the **symmetric snap handling** self-play needs (see [simulation.md](simulation.md)).
- **Balanced sides** via `_sides(g)`: it cycles the four (which seat A takes) × (who
  starts) combinations, so over any multiple of 4 games each entrant starts half the time
  and sits in each seat half the time. This removes first-move bias from the rating.
- **Only win/loss/tie matters** — margins are ignored; a tie counts as **half a win** to
  each side.
- Returns a `TournamentResult` with the win matrix, per-entrant W/L/T tallies, fitted
  `strengths`, Elo `ratings`, and timing.

## The rating: Bradley-Terry → Elo

This is the principled model for a complete round robin. Constants live at the top of
[`game/tournament.py`](../game/tournament.py):

```python
ELO_SCALE     = 400.0   # rating points per decade of strength ratio (Elo convention)
ANCHOR_RATING = 1500.0  # Random (or the field mean, if absent) sits here
BT_ALPHA      = 0.5     # smoothing: pseudo wins+losses added to each played pair
```

- **`bradley_terry(win, ngames, alpha=BT_ALPHA)`** — fits a strength `pᵢ` per entrant via
  the Hunter (2004) minorization-maximization iteration (maximum-likelihood pairwise
  comparison). A symmetric prior of `alpha` pseudo-wins and `alpha` pseudo-losses is added
  to every *played* pair so no strength runs to 0 or ∞ even if a bot sweeps or never wins.
  Strengths are normalized to a **geometric mean of 1**.
- **`to_elo(strengths, anchor_index)`** — maps strengths to ratings:
  `ratingᵢ = anchor_rating + scale · log₁₀(pᵢ / p_ref)`. With Random present it's the
  reference, so **Random lands exactly at 1500**; without it (`--no-random`), the field's
  geometric mean centers at 1500. A 400-point gap ≈ a 10:1 expected win ratio.
- **`rankings(result)`** — per-entrant rows sorted by rating (descending), each tagged
  with `rank`, plus win%, score% (wins + ½ ties), and W/L/T.

So the headline number for each strategy is **points above coin-flip-against-random
(1500)**.

## Reproducibility & verification

Seeded runs are deterministic. The math and bookkeeping are unit-tested in
`tests/test_tournament.py` — dominance is monotone and finite, balanced/all-tie fields
are uniform, strengths normalize to geo-mean 1, the anchor lands exactly at 1500, sides
balance (`a_starts == k//2` when `k % 4 == 0`), and seeded runs reproduce. See
[testing.md](testing.md).

## See also

- [strategies.md](strategies.md) — the entrants and their tunable knobs.
- [simulation.md](simulation.md) — the complementary "vs random" measurement.
