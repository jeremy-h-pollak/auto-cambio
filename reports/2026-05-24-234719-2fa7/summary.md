---
id: 2fa7
date: 2026-05-24
time: 234719
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/strategy-ridcards/reports/minimalist.html
games: 2000
seed: 1
filed_at: 2026-05-24 23:47
---

# Self-play report 2fa7

## Headline stats
- 2,000 games, seed 1 — **Minimalist (smart) vs Random AI**, max_turns=1000, throughput 837 games/s (2.39s total)
- Win rates: **Smart 75.4% · Random 20.2% · Tie 4.3%**
- Avg final score: smart 8.69 vs random 17.24 (lower is better) · avg victory margin 11.42
- First-move: Smart moving first 77.8% vs second 72.9%; starter wins 50.5% overall (52.8% decisive-only)
- Cambio: 1,964 games (98.2%) ended by a call; **caller success 56.0%**
- Endings: cambio 1,964 (98.2%) · empty 36 (1.8%) · capped 0 (0.0%)
- Game length: mean 13.1 turns (range 2–40)
- Snaps/game: smart 1.12 · random 1.07
- (This minimalist report format omits the per-ability and deck-vs-discard draw breakdowns the baseline `5af9` had.)

### Strategy under test — Minimalist
- Snaps every matching card (even negatives) to shrink its hand as fast as possible.
- Grabs any discard-pile card worth ≤4; gambles a draw ≤6 onto an unknown slot.
- Calls Cambio once all four cards are known and their total is ≤7.

## Analysis
- First strategy run filed against baseline `5af9` (random vs random). The Minimalist heuristic **decisively beats random**, 75.4% to 20.2%.
- **Cambio flipped from -EV to +EV:** caller success went from 44.1% (baseline) to 56.0% here — the disciplined "only call when all four known and total ≤7" rule is doing exactly what the baseline flagged as the weakest lever.
- **First-mover sign flipped:** in the baseline, going first was a disadvantage (45.4%); with a real strategy the starter wins 50.5% (52.8% decisive), and Smart gains ~5pt moving first (77.8% vs 72.9%). Strategy edge dominates positional edge.
- Hand quality: avg smart score 8.69 vs random 17.24 — the low-hand focus pays off directly.
- Clean run: 0 capped games, fast. Snap rate is modest (~1.1/game) despite the snap-everything rule — fewer matching opportunities than the rule's aggressiveness suggests.

## Findings (interview)
- **Tested:** The Minimalist strategy — the first real low-hand heuristic measured against the random baseline.
- **Key takeaway:** All four landed — Minimalist dominates random (75.4%), disciplined Cambio is now +EV (56.0%), the low-hand focus works (8.69 vs 17.24), and the first-move sign flipped to a slight edge.
- **Surprises / concerns:** The thresholds (≤7 call / ≤4 grab / ≤6 draw) are hand-tuned and likely not optimal; and it's only been tested against Random — a weak opponent, so 75% may not hold against a smarter or mirror strategy.
- **Verdict / next step:** Tune the thresholds — sweep the ≤7 / ≤4 / ≤6 parameters to find better values (and, per the concern, eventually test against a stronger opponent than Random).
