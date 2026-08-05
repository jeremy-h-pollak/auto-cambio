---
id: "6267"
date: 2026-08-04
time: "123829"
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/idea2/tournament-opus-ladder.html
games: 80
seed: 43
filed_at: 2026-08-04 12:38
---

# Tournament report 6267 — opus prompt vs the deterministic ladder

## Headline stats
- Round-robin, 5 entrants · 10 pairings · k=8 as 4 duplicate deals/pairing · 80
  games · seed 43 · 770s runtime.
- Rankings: **The Cartographer 1645 (20–12, 62.5%)** and **Gemini Flash · Opus
  prompt 1645 (20–12, 62.5%)** tied at the top; Greedy Minimizer 1597 (17–15);
  Selective Snapper 1517 (12–20); Random anchor 1500 (11–21).
- Head-to-head for the LLM: lost to Cartographer 3–5; beat Greedy 5–3, Snapper
  6–2, Random 6–2. No ranking upsets anywhere in the matrix.
- 95% bootstrap CIs (2,000 replicates): LLM [1531, 1797], Cartographer
  [1484, 1850] — heavily overlapping at k=8.
- LLM cost/quality: 258 calls, 546k tokens in / 7.0k out, ~$0.14; **2 fallbacks
  in 260 calls** (transient DNS failures, not credit) ≈ 0.8% contamination.
- Skill spread first-to-last just 145 Elo; tie rate 0%; avg game 8.2 turns.

## Analysis
- This is the second measurement of the Opus-authored prompt (idea 2). The first
  (same-model A/B vs the v1 rules-only prompt, k=12 duplicate) put opus +145 Elo
  and 9–3 head-to-head; this run places the same entrant against real reference
  bots.
- The placement is a step-change vs the previous LLM filing (06ce): Kimi K2 and
  Claude Haiku on the v1 prompt landed ≈ Greedy (1616/1641), clearly below
  Cartographer. Here the *cheapest* model in the stable ties the #1 hand-written
  bot — the prompt, not model scale, is doing the lifting.
- The tie is built on the Random pairings: Cartographer went only 4–4 vs Random
  while the LLM went 6–2, cancelling Cartographer's 5–3 edge in the direct
  matchup. At k=8 that 4–4 is plausibly deck luck.

## Findings (interview)
- **Tested:** Whether the log-derived Opus-authored prompt (idea 2) lifts cheap
  Gemini Flash Lite from mid-pack to the top of the deterministic ladder.
- **Key takeaway:** It ties the #1 bot — Flash Lite + opus prompt matches
  Cartographer (1645 Elo, 62.5%) and beats every other rung; prior LLM entrants
  only reached Greedy level. The prompt works.
- **Surprises / concerns:** Small k / wide CIs (±~130 Elo — ranks could shuffle
  on a rerun); Cartographer going 4–4 vs Random shows how much deck luck k=8
  leaves in; 2 DNS fallbacks (~0.8% of calls) — negligible but nonzero
  contamination.
- **Verdict / next step:** Keep the opus prompt — merge PR #44 as-is; after a
  credit top-up, run a larger k (e.g. 40 duplicate) to confirm the
  top-of-ladder placement.
