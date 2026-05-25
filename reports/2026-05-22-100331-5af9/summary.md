---
id: 5af9
date: 2026-05-22
time: 100331
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/simulate/cambio_report.html
games: 1000
seed: 1
filed_at: 2026-05-22 10:03
---

# Self-play report 5af9

## Headline stats
- 1,000 games, computer vs. computer, seed 1 — runtime 1.45s (689 games/s)
- Outcomes: Player (starting) 454 (45.4%) · Computer 510 (51.0%) · Tie 36 (3.6%)
- Mean final score: player 18.23, computer 17.67 (lower is better) · mean win margin 10.99
- Game length: mean 12.7 turns · median 10 · min 2 · max 72
- Cambio: 952 calls (player 488 / computer 464) — ended 95.2% of games; caller won only 420 (44.1% of calls)
- Endings: cambio 952 · empty_hand 48 · aborted 0
- Specials per game: blind switch (J/Q) 0.93 · peek opp (9/10) 0.73 · looking switch (K) 0.60 · peek own (7/8) 0.49
- Snaps: mean 1.89/game · median 1 · max 7 · draws 4,354 deck vs 1,743 discard (28.6% discard)

## Analysis
- First filed run — establishes the baseline; no prior run to compare against.
- The starting player (Player, who always moves first) wins **less** than the second mover, 45.4% vs 51.0%. A small but consistent first-mover disadvantage under random play.
- Calling Cambio is net-negative: the caller wins only 44.1% of the time, so the random AI is calling Cambio when it doesn't hold the lowest score and eating the +5 penalty. This is the clearest lever for a smarter strategy.
- Healthy otherwise: 0 aborted games (none hit the turn cap), fast, and the score/length distributions look reasonable for random play. Special abilities fire rarely (peek-own just 0.49/game) since draws aren't being steered.

## Findings (interview)
- **Tested:** Baseline run of the current random AI — establishing a reference point before any strategy optimization.
- **Key takeaway:** Calling Cambio is -EV under the current random play (caller wins only 44.1%); the AI calls too loosely.
- **Surprises / concerns:** The starting player winning <50% is counterintuitive and worth confirming it's real rather than a bug; the sub-50% caller win rate hints the call/snap logic is calling Cambio while behind.
- **Verdict / next step:** Keep this as the baseline and move on to strategy work, with Cambio-call timing as the first lever to improve.

## Action distribution (added 2026-05-25)
Report regenerated in the **unified format** with a per-seat **"Action distribution — observed vs expected"** section; every number above is unchanged (the simulator only gained observational counters — no RNG was touched). Both seats run the random strategy here, so both carry an Expected (coded) column — making this run the cleanest validation of the random implementation:
- **Call Cambio:** player 7.4% · computer 7.6% of draw-phase decisions, vs the coded **8%** ✓ (slightly under because a game ending mid-sequence truncates the decision pool).
- **Draw source:** reproduces the split exactly — player 4,354 deck / 1,743 discard.
- **Action phase:** swap ≈ 52% / discard ≈ 48%, consistent with the 40%-base + high-card (≥10 → 70%) boost.
- **Specials & snaps** per seat reproduce the figures above (e.g. player blind-switch 467, peek-opp 400).
