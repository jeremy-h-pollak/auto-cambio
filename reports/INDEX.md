# Self-play report log

| ID | Date | Games | Verdict / one-line takeaway | Folder |
|----|------|-------|-----------------------------|--------|
| 5af9 | 2026-05-22 10:03 | 1000 | Baseline (random AI); Cambio is -EV — caller wins only 44.1%. Keep as baseline. | [link](2026-05-22-100331-5af9/) |
| 2fa7 | 2026-05-24 23:47 | 2000 | Minimalist beats random 75.4%; disciplined Cambio now +EV (56.0%). Tune the thresholds. | [link](2026-05-24-234719-2fa7/) |
| 288b | 2026-05-24 23:57 | 2000 | Bargain Hunter ties Minimalist (75.2%); added complexity no gain vs random. Test strategies head-to-head. | [link](2026-05-24-235734-288b/) |
| 6994 | 2026-05-26 10:34 | 63000 | Round-robin (21 entrants): new Cartographer is #1; all 5 advanced strategies top-10. Keep; promote Cartographer. | [link](2026-05-26-103439-6994/) |
| 6414 | 2026-06-04 13:27 | 23100 | Round-robin (22 entrants): smart/greedy default is mid-pack at 1664 Elo (#14/22), below all advanced + simple low-sum bots. Keep as baseline. | [link](2026-06-04-132718-6414/) |
| 06ce | 2026-06-16 14:51 | 60 | First LLM-on-ladder round-robin (6 entrants): Kimi K2 & Claude Haiku land mid-pack (1616/1641 Elo), ≈ Greedy, below Cartographer; Kimi≈Haiku (2–2 H2H). Small k=4 sample. TBD. | [link](2026-06-16-145153-06ce/) |
| 6efc | 2026-08-04 11:12 | 300 | Prompt-A/B (Gemini Flash v1 vs v2): adding the Cartographer's playbook to the system prompt is a **null** — v2 beat v1 52–47–1 over 100 games (p=0.62), Elo CIs overlap. Clean run (0.02% fallback, $2.50). Next: iterate v2 format / stronger model. | [link](2026-08-04-111245-6efc/) |
| 0fdd | 2026-08-12 04:37 | 80 | Prompt v3 (playbook as an **operational procedure**) head-to-heads: v3 is **worse**, not better — loses 16–23–1 to v1 and 14–25–1 to v2; pooled 38.8% vs the v1/v2 baseline (p=0.04). "It was the format" refuted — prescriptive form *hurts* flash-lite. Idea 1 closed; harness kept. Clean runs. | [link](2026-08-12-043718-0fdd/) |
