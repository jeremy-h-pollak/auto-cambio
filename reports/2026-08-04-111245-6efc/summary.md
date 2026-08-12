---
id: 6efc
date: 2026-08-04
time: 111245
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/prompt-change/gemini-v1-v2-k100.html
games: 300
seed: random
filed_at: 2026-08-04 11:12
---

# Tournament report 6efc

A/B of a **system-prompt change** for the LLM strategy, using the new versioned-prompt
harness: **Gemini Flash v1** (rules only) vs **Gemini Flash v2** (rules + The
Cartographer's playbook, generated from the bot's own `rules` bullets) entered as two
distinct competitors, plus Random as the anchor. High-power rerun after a k=8 pilot
(report from the prior session) proved too noisy to resolve the gap.

## Headline stats
- 3 entrants · 100 games/pairing · 300 games · seed=None · max_turns=1000 · tie rate 1.0% · avg length 9.5 turns
- Final Elo (Random anchored at 1500, Bradley-Terry, 2000 bootstrap replicates):
  1. **Gemini Flash V2 (LLM)** — 1808 (69.0%, 138–60–2) · 95% CI [1748, 1882]
  2. **Gemini Flash (LLM)** — 1786 (65.0%, 130–68–2) · 95% CI [1727, 1860]
  3. Random — 1500 (14.5%, 29–169–2)
- **Direct head-to-head (the whole point): V2 beat V1 52–47–1 over 100 games** = 52.5%.
- Run cleanliness: **1 heuristic fallback of 4,207 LLM calls (0.02%)** — 0 v1, 1 v2; 0 credit/API errors.
- Cost: **$2.50** (google/gemini-3.1-flash-lite; 9.20M in / 178K out tokens); ~69 min active.

## Analysis
- **Null result.** The +22 Elo edge for v2 is not significant: the direct 52–47–1 cell is
  a two-sided **p = 0.62** (z = 0.50) against 50-50, with a Wilson 95% CI on v2's win share
  of **43%–62%**. The two entrants' Elo intervals ([1748,1882] vs [1727,1860]) overlap by
  ~112 of ~130 points. The report's own insight engine flagged the overlapping bands.
- **Contrast with the k=8 pilot**, where v2 also "won" (1784 vs 1767) but the Cartographer
  fell to 4th at 43.8% — a tell that k=8 couldn't resolve anything. At k=100 the run is
  clean (0.02% fallback, balanced 2059/2148 call split) and trustworthy; the answer it
  gives is "no measurable effect," not noise.
- Both LLMs comfortably beat Random (~65–69%), consistent with prior LLM-on-ladder runs
  (06ce). The prompt change is what didn't move the needle, not the model.

## Findings (interview)
- **Tested:** Idea 1 — does putting the strongest deterministic bot's (The Cartographer's)
  playbook into the LLM system prompt (v2) improve play vs the rules-only prompt (v1)?
- **Key takeaway:** **v2 is a null result** — v2 beat v1 52–47–1 (p=0.62), Elo CIs overlap
  heavily. Handing over the playbook as prose gave no measurable gain for flash-lite.
- **Surprises / concerns:** Only one cheap model (gemini-3.1-flash-lite) was tested, and the
  playbook was delivered as description rather than worked examples — a stronger model or a
  more prescriptive/structured format could still differ.
- **Verdict / next step:** **Iterate the v2 format** — try few-shot worked examples or a
  stronger model (full Gemini Flash, not lite) before concluding the idea is dead. The
  versioned-prompt A/B harness that made this measurable in one clean run is kept regardless.
