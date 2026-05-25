---
id: 288b
date: 2026-05-24
time: 235734
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/strategy-ridcards/reports/scrooge.html
games: 2000
seed: 1
filed_at: 2026-05-24 23:57
---

# Self-play report 288b

## Headline stats
- 2,000 games, seed 1 — **Bargain Hunter (smart) vs Random AI**, max_turns=1000, throughput 827 games/s (2.42s total)
- Win rates: **Smart 75.2% · Random 21.4% · Tie 3.5%**
- Avg final score: smart 8.98 vs random 16.97 (lower is better) · avg victory margin 11.05
- First-move: Smart moving first 77.0% vs second 73.4%; starter wins 49.7% overall (51.5% decisive-only)
- Cambio: 1,969 games (98.5%) ended by a call; **caller success 57.3%**
- Endings: cambio 1,969 (98.5%) · empty 31 (1.6%) · capped 0 (0.0%)
- Game length: mean 13.1 turns (range 2–38)
- Snaps/game: smart 1.01 · random 1.09
- (Minimalist report format — omits the per-ability and deck-vs-discard draw breakdowns.)

### Strategy under test — Bargain Hunter
- Snatches any discard-pile card worth ≤4 (guaranteed-cheap), and takes the discard when it beats its highest known card.
- Keeps negative cards (never snaps a red King).
- Replaces its highest known card when the draw is lower; gambles a draw ≤6 onto an unknown slot; otherwise discards and uses the power.
- Calls Cambio once all four cards are known and their total is ≤8 (up from Minimalist's ≤7).

## Analysis
- Read against `2fa7` (Minimalist), this is **essentially a dead heat**: 75.2% vs 75.4% win rate — within noise.
- Despite being a more elaborate strategy (beat-highest-known discards, explicit negative-keeping, ≤8 call threshold), it produced **no win-rate gain** and a **slightly worse average hand** (8.98 vs 8.69). Caller success edged up (57.3% vs 56.0%) and snaps dropped (1.01 vs 1.12, consistent with never snapping red Kings).
- Two distinct low-hand strategies converging to ~75% strongly suggests a **ceiling against Random** — random is too weak an opponent to separate them. The 75% figure says more about the opponent than the strategy.
- Clean run: 0 capped, fast, distributions in line with `2fa7`.

| Metric | 2fa7 Minimalist | 288b Bargain Hunter |
|---|---|---|
| Smart win rate | 75.4% | 75.2% |
| Avg smart score | 8.69 | 8.98 |
| Caller success | 56.0% | 57.3% |
| Call threshold | ≤7 | ≤8 |
| Snaps/game (smart) | 1.12 | 1.01 |

## Findings (interview)
- **Tested:** The Bargain Hunter strategy — a more elaborate low-hand variant (beat-highest-known discards, keep negatives, ≤8 Cambio threshold).
- **Key takeaway:** It ties Minimalist at ~75% — the added complexity bought no win-rate improvement over the simpler `2fa7`.
- **Surprises / concerns:** Still only tested against Random (a weak opponent, so the 75% may be meaningless); no gain over the simpler Minimalist despite more rules; and the average hand regressed (8.98 vs 8.69).
- **Verdict / next step:** Test the strategies head-to-head — run Minimalist vs Bargain Hunter (and/or against a stronger AI) to actually separate them, since Random can't.
