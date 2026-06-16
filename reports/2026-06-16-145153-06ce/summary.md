---
id: 06ce
date: 2026-06-16
time: 145153
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/new-ai-tournament/tournament_results_20260616-104354/tournament.html
games: 60
seed: 1
filed_at: 2026-06-16 14:51
---

# Tournament report 06ce

First round-robin to place **live LLM models on the bot ladder** (Kimi K2 and
Claude Haiku via OpenRouter), using the new `--llm-models` multi-model support and
the sharpened LLM prompts.

## Headline stats
- 6 entrants · 4 games/pairing · 60 games · seed=1 · max_turns=1000
- Final Elo (Random anchored at 1500):
  1. The Cartographer — 1721 (75.0%)
  2. Greedy Minimizer — 1654 (60.0%)
  3. **Claude Haiku (LLM)** — 1641 (60.0%)
  4. **Kimi K2 (LLM)** — 1616 (50.0%)
  5. Random — 1500 (30.0%)
  6. Selective Snapper — 1398 (15.0%)
- Kimi vs Haiku head-to-head: **2–2** (tie)
- Cost: $2.26 (Kimi $0.74 / Haiku $1.52); 2.75M in / 13.9K out tokens
- Run cleanliness: 6 heuristic fallbacks of 851 LLM calls (0.7%) — all
  malformed-JSON, **0 credit/API errors**
- Timing: ~36 min active engine time; ~10h calendar (machine asleep for ~96% of it)

## Analysis
- Both LLMs land **mid-pack**: comfortably above Random and Snapper, roughly even
  with the Greedy Minimizer, and clearly below the top hand-tuned bot,
  **The Cartographer** (~80–105 Elo higher). The EV-reasoning bot still beats the
  general-purpose models.
- **Kimi ≈ Haiku.** Their direct H2H was 2–2 and the 25-Elo gap is within noise at
  this sample size — treat them as equal on this evidence.
- vs prior runs (6994, 6414 in INDEX): those were large heuristic-only
  round-robins; this is the first to include LLM entrants, so it's a new baseline
  rather than a directly comparable rerun.

## Findings (interview)
- **Tested:** benchmark Kimi K2 and Claude Haiku against the heuristic bot ladder
  (first LLM-on-ladder run).
- **Key takeaway:** the LLMs are mid-pack — competent, but below the Cartographer;
  hand-tuned EV strategy still wins.
- **Surprises / concerns:** (1) sample is small (k=4, 60 games) so mid-table gaps
  aren't statistically separable; (2) wall-clock was dominated by the Mac sleeping,
  not real work — engine time was only ~36 min.
- **Verdict / next step:** TBD. Likely candidates: re-run larger with `caffeinate`
  (keep the machine awake) and/or top up OpenRouter credit for a full 10-entrant,
  higher-k run to tighten the ratings.
