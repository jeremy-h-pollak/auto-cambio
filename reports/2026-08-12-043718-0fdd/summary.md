---
id: 0fdd
date: 2026-08-12
time: 043718
source: /Users/jeremypollak/auto-cambio/.claude/worktrees/prompt-change/gemini-v1v3.html
games: 40
seed: random
filed_at: 2026-08-12 04:37
---

# Tournament report 0fdd — prompt v3 (operational playbook) head-to-heads

Follow-up to **6efc**, which found prompt **v2** (the Cartographer's playbook as *prose*)
a null vs **v1** (rules only): 52–47–1, p=0.62. The interview read was "it wasn't the
content, it was the format." **v3** tests that: the same playbook as an **operational
decision procedure** (ordered draw/after-draw priority lists + numeric thresholds
interpolated from the bot's attributes + a worked example). Measured as two 2-entrant
head-to-heads (same model, `google/gemini-3.1-flash-lite`, only the prompt differs).

Run as isolated 2-entrant pairings because full multi-entrant runs kept getting killed by
the environment at the ~1 h mark — and the both-LLM direct cells always ran *last*, so every
kill destroyed exactly the data needed. A 2-entrant field puts the one cell that matters
first, finishing in ~14 min inside the safe window.

## Headline stats
- Two 40-game head-to-heads, 20 duplicate deals each, 2000 bootstrap replicates. Both clean
  (**0 heuristic fallbacks**; $0.65 + $0.71).
- Direct records (first-named entrant's W–L–T):
  - **v3 vs v1: 16–23–1 → v3 41.2%** (p=0.27; 95% CI 27–57%)
  - **v3 vs v2: 14–25–1 → v3 36.2%** (p=0.08; 95% CI 23–52%)
  - (for reference, from 6efc) **v2 vs v1: 52–47–1 → 52.5%** (p=0.62)
- **Pooled: v3 vs the v1/v2 baseline over 80 games → 30–48–2 = 38.8%** (p=0.04).

## Analysis
- **Ordering: v1 ≈ v2 > v3.** Rules-only and the prose playbook are statistically tied; the
  operational procedure (v3) is the **worst** of the three, significantly below the v1/v2
  baseline when the two cells are pooled (38.8%, p=0.04).
- So "it was the format" is **refuted, and then some** — making the playbook prescriptive
  did not rescue it, it *hurt*. Plausible mechanism (speculative): a rigid step-by-step
  procedure overrides gemini-flash-lite's own situational reasoning with a heuristic it
  executes imperfectly, so it plays a worse copy of the bot instead of a better version of
  itself. The data shows the *what*, not the *why*.
- Consistent with the whole arc: describing the best deterministic player in the system
  prompt does not make this model play better — as prose it's a wash, as a procedure it's a
  net negative.

## Findings (interview)
- **Tested:** Does the Cartographer's playbook delivered as an operational procedure (v3)
  beat rules-only (v1) and the prose form (v2)? (Idea 1 "done better.")
- **Key takeaway:** No — v3 is **measurably worse** (pooled 38.8% vs the v1/v2 baseline,
  p=0.04). Neither prose nor procedure yields a stronger LLM strategy for flash-lite.
- **Surprises / concerns:** v3 being *worse* (not just null) was unexpected; the prescriptive
  format appears to actively degrade play. Small per-cell samples (k=40) — the negative
  direction is consistent across both opponents and significant when pooled, but a larger run
  would tighten it. Environment repeatedly killed long runs (~1 h); mitigated by 2-entrant
  jobs. OpenRouter credit exhausted mid-effort and had to be topped up.
- **Verdict / next step:** Idea 1 is closed as a strategy improvement — it does not produce a
  better bot in any form tried. The versioned-prompt A/B harness (v1/v2/v3 as entrants) is the
  durable value and stays. Any future prompt idea plugs into it the same way.
