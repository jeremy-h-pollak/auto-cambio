---
id: 6994
date: 2026-05-26
time: 103439
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/complex-tournament/tournament-advanced.html
report_type: round-robin tournament
games: 63000
seed: 1
filed_at: 2026-05-26 10:34
---

# Tournament report 6994

Round-robin across **21 entrants** (the 15 existing profiles + 5 new advanced
strategies + Random), 300 games/pairing, balanced sides, Bradley-Terry → Elo with
Random anchored at 1500. This is the head-to-head test the prior run (288b) called for.

## Headline stats
- 21 entrants · 210 pairings · **63,000 games** · seed 1 · max_turns 1000
- Tie rate **4.9%** · avg game length **18.0 turns** · 574 games/sec (~110s)
- Rating span **1479–1728 ≈ 249 pts**

## Rankings (top of the ladder)
1. **The Cartographer — 1728 (59.0%)**  ← new, outright #1
2. Minimalist — 1704
3. Opportunist — 1699
4. Quick Closer — 1694
5. Card Counter — 1692
6. Bargain Hunter — 1688
7. **The Architect — 1687**  ← new
8. **The Saboteur — 1686**  ← new
9. **The Sprinter — 1683**  ← new
10. **The Sentinel — 1677**  ← new
- Bottom: Aggressive Caller 1621, Selective Snapper 1562, Random 1500,
  Patient Perfectionist 1492, Cautious Optimizer 1479.

## Analysis
- **All 5 new strategies landed in the top 10 of 21**, and a new strategy (The
  Cartographer) is the outright #1, beating every existing profile by ~24 pts.
- The new strategies add what the parameterized field lacks: per-game **opponent
  memory** (recorded peeks), **expected-value reasoning** (unknown = deck mean ≈6.46),
  and **purposeful card powers**. Verified fair-info-only.
- **Information-gathering is the dominant lever.** Cartographer wins by spending
  7/8/9/10 on peeks to map its own hand → more snaps + a precise low-total Cambio.
  Switch powers (Saboteur, #8) and extreme tempo turn out to be marginal.
- Two tuning facts mattered between the first and final run: (1) generalizing
  "fire a peek card for its power while the table is fuzzy" lifted the four laggards
  from mid-pack into the top 10; (2) gambling onto an unknown is only +EV **below
  the deck mean (≤6)** — Sprinter's original `gamble_max=7` was negative-EV.
- Stable across seeds: on seed 2, Cartographer was #1 again (1738, 36-pt margin),
  all 5 new strategies still top-10.

## Findings (interview)
- **Tested:** The 5 new advanced strategies (opponent memory + expected-value
  reasoning), to see whether they out-rate the existing field head-to-head.
- **Key takeaway:** All three at once — (1) information-gathering wins (Cartographer
  is the clear #1), (2) all 5 new strategies reached the top 10, and (3) the skill
  ceiling stays compressed even so.
- **Surprises / concerns:** The ladder barely widened (~249 pts vs the prior ~238) —
  added complexity raised the top only modestly. Consistent with Cambio being a
  high-variance, low-ceiling game.
- **Verdict / next step:** Keep the new strategies; promote The Cartographer (or its
  information-first logic) toward the engine's default AI.
