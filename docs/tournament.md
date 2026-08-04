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
| `--strategies` | none | comma-separated entrant keys to use as the field instead of all of them (e.g. `cartographer,greedy,random`) |
| `--duplicate` | off | control for deck luck by playing `k/2` fixed deals twice each with the entrants swapped (requires an even `-k`) — see [Controlling for deck luck](#controlling-for-deck-luck-duplicate) |
| `--max-turns` | `1000` | safety cap on turns per game |
| `--bootstrap N` | `0` (off) | add bootstrap confidence intervals to every rating from `N` resampled replicates (e.g. `2000`) |
| `--ci-level` | `0.95` | confidence level for `--bootstrap` intervals |
| `--quiet` | off | suppress per-pairing progress |
| `--enable-llm` | off | add the generic OpenRouter LLM entrant (`--llm-model`, `--llm-snaps`) |
| `--enable-kimi` / `--enable-haiku` | off | enter the named Kimi K2 / Claude Haiku models as distinct competitors |
| `--enable-gemini` / `--enable-gemini-v2` / `--enable-gemini-v3` | off | enter Gemini Flash on system prompt **v1** / **v2** (playbook as prose) / **v3** (playbook as a procedure) — same model, to A/B a prompt change |

LLM entrants are opt-in, slow, and metered (each turn is a live API call needing
`OPENROUTER_API_KEY`); cost scales with `-k` × field size, so keep `-k` tiny. The named
models come from `game/llm_opponents.py` and are env-overridable
(`CAMBIO_KIMI_MODEL` / `CAMBIO_HAIKU_MODEL` / `CAMBIO_GEMINI_MODEL`).

An entrant carries a **system-prompt version** as well as a model, so a prompt change is
measurable: `gemini`, `gemini-v2`, and `gemini-v3` are the same model under
[prompts v1 / v2 / v3](llm-strategy.md#prompt-versions) and meet head-to-head inside one
run. Pair it with `--duplicate` so those cells aren't deck luck:

```bash
python tournament.py --enable-gemini --enable-gemini-v2 --enable-gemini-v3 \
  --strategies random -k 100 --duplicate --bootstrap 2000
```

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

## Controlling for deck luck (`--duplicate`)

A bot dealt `A-2-3-A` beats a better bot dealt `K-Q-J-10` most of the time, and with a fresh
shuffle every game that luck is noise the rating has to average away. `--duplicate` applies
the **duplicate-bridge** fix, in [`game/deals.py`](../game/deals.py):

- `make_deals(n, seed)` pre-generates `n` fixed 52-card orders, each with its own seed.
- Each deal is played **twice**, with the deck order, the starting seat and all in-game
  randomness held identical and only the **entrants swapped** — so each side plays both
  halves of the same deal and whatever the deal was worth cancels within the pair.
- `create_initial_state(starting_turn, deck=, deal_seed=)` takes the fixed deck; `deal_seed`
  also determines mid-game reshuffles, and `simulator.play_game` reseeds global `random`
  from it so the *strategies'* own coin flips are common random numbers too.
- `k` must be even; `PairResult.deal_scores` records A's score (0–2) per deal.

**Deal sets are drawn independently per pairing** (`_pair_deals`), not shared across the
field. Sharing one set is tempting — every entrant measured on identical hands — but it
correlates all the pairings within a run so deal luck no longer averages out across them;
measured on an 8-entrant field it made run-to-run rating variance **~3× worse**. Per-pairing
deals keep that averaging and still get the within-pair mirror.

### How much does it actually buy? ~10%

Measured over 600-game pairings, comparing observed variance of the per-deal score against
the independent-games prediction:

| pairing | variance ratio | effective games |
|---|---|---|
| Cartographer vs Greedy | 0.89 | 1.12× |
| Cartographer vs Minimalist | 0.91 | 1.10× |
| Architect vs Greedy | 0.79 | 1.26× |
| Cartographer vs Random | 0.92 | 1.08× |
| Greedy vs Random | 0.97 | 1.04× |

End to end that lands about where you'd expect: over 40 repeat tournaments of an 8-entrant
field at `-k 40`, the spread of the final Elo ratings came out at a **0.94 variance ratio,
i.e. ~1.06× effective games**.

So it is **real but modest — roughly a 10% variance cut, worth ~1.1× the games**. The reason
it isn't the 2×+ duplicate bridge gets: the two halves diverge as soon as the two strategies
choose differently, after which the shared deck order stops delivering the same cards. Only
the opening 8 cards and the first discard are truly common. **Raising `-k` is still the
bigger lever** — `--duplicate` is a free extra, not a substitute.

Note most bots are deterministic given a deal, so the common-random-numbers reseed only
changes anything in pairings involving `Random` (where it helps: 1.03 → 0.92).

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

## Confidence intervals (`--bootstrap`)

A single round robin gives one point-estimate Elo per strategy but no sense of how much of
the ranking is real versus finite-sample noise. `--bootstrap N` adds a confidence band to
every rating via **`bootstrap_ratings(result, n_boot, ci, seed)`** in
[`game/tournament.py`](../game/tournament.py):

- It's the **nonparametric pairwise bootstrap**. Each of the `N` replicates resamples every
  pairing's `k` recorded games with replacement — equivalently, redraws `(a_wins, b_wins,
  ties)` from a multinomial with the observed proportions — then refits Bradley-Terry and
  re-anchors via `to_elo`. **No games are replayed**; only the cheap matrix fit re-runs, so
  even `N = 2000` is fast.
- Under `--duplicate` the resampling unit is the **deal pair**, not the game: the two
  mirrored halves share a deck and are not independent, so replicates resample
  `PairResult.deal_scores` (a block bootstrap). Resampling games there would treat the
  paired design as independent and overstate the precision.
- The band is the **percentile spread** of each entrant's rating across replicates (the
  `(1 ± ci)/2` quantiles), returned as `{index: {"lo", "hi", "median", "samples"}}`.
- With Random anchored it is pinned to exactly 1500 in every replicate, so **its band is a
  degenerate `[1500, 1500]`** by construction.

When present, the bands show up as a `95% CI` column in both the console table and the
report's rankings table, and as **capped whiskers** over each bar in the diverging chart —
overlapping whiskers mean the gap between two strategies isn't resolved at that game count.
Use a local `random.Random(seed)` internally, so bootstrapping never perturbs the
tournament's own seeded game stream.

## Reproducibility & verification

Seeded runs are deterministic. The math and bookkeeping are unit-tested in
`tests/test_tournament.py` — dominance is monotone and finite, balanced/all-tie fields
are uniform, strengths normalize to geo-mean 1, the anchor lands exactly at 1500, sides
balance (`a_starts == k//2` when `k % 4 == 0`), and seeded runs reproduce. See
[testing.md](testing.md).

## See also

- [strategies.md](strategies.md) — the entrants and their tunable knobs.
- [simulation.md](simulation.md) — the complementary "vs random" measurement.
