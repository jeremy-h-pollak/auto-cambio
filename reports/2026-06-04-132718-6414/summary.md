---
id: 6414
date: 2026-06-04
time: 132718
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/tournament-smart/tournament-smart.html
games: 23100
seed: 42
filed_at: 2026-06-04 13:27
---

# Self-play report 6414

Round-robin tournament (not a single-strategy `simulate.py` run): 22 entrants ×
100 games/pairing, balanced sides. Run to locate where the "smart" strategy —
`game/strategy_smart.py`, a facade re-exporting the **greedy** profile (web/engine
default opponent) — lands on the Elo ladder.

## Headline stats
- 22 entrants · 100 games/pairing · 23,100 games · seed=42 · max_turns=1000
- Tie rate 1.6% · avg game length 16.7 turns · throughput 651 games/sec
- Elo anchored on Random = 1500 (Bradley-Terry → 400·log₁₀ strength ratio)
- **Smart strategy = Greedy Minimizer: rank 14/22, Elo 1664, 52.8% win (1109–954–37)**
- Champion: The Cartographer — 1748 Elo, 64.4% wins
- Cellar: Reckless Rookie — 1361 Elo, 15.9% wins
- Skill spread: 387 Elo first-to-last (~9:1 expected wins)
- All 5 advanced bots finish above greedy: Cartographer 1748 (#1), Saboteur 1700 (#4),
  Architect 1689 (#6), Sprinter 1682 (#8), Sentinel 1679 (#10)
- Most dominant matchup: Aggressive Caller 94% over Reckless Rookie
- Biggest upset: Sentinel (#10) beats Bargain Hunter (#2) head-to-head, 56%

## Analysis
- Consistent with prior tournament run 6994 (2026-05-26): Cartographer remains #1 and
  all advanced strategies stay top-10. The Elo numbers here are not directly comparable
  to 6994 (different game count/seed) but the ordering holds.
- The default opponent (greedy / "smart") is only +164 over random and sits mid-pack —
  beaten by every advanced bot and by simple low-sum profiles (Minimalist 1705,
  Bargain Hunter 1708). Disciplined "keep it low, snap matches, call on a known small
  total" heuristics outperform greedy's higher Cambio threshold.
- Ladder is wide and well-separated (387 Elo), so rankings are meaningful rather than noise.

## Findings (interview)
- **Tested:** Where the smart strategy (greedy, the web/engine default) lands on the Elo ladder.
- **Key takeaway:** Smart/greedy is mid-pack — rank 14/22 at 1664, below all 5 advanced bots
  and several simple profiles.
- **Surprises / concerns:** Greedy sits *below* simple bots (Minimalist, Bargain Hunter) —
  the shipped default opponent is weaker than untuned low-sum heuristics; a stronger default
  may be worth promoting.
- **Verdict / next step:** Keep this as the current Elo baseline; no change yet.
