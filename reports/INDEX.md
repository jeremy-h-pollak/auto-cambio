# Self-play report log

| ID | Date | Games | Verdict / one-line takeaway | Folder |
|----|------|-------|-----------------------------|--------|
| 5af9 | 2026-05-22 10:03 | 1000 | Baseline (random AI); Cambio is -EV — caller wins only 44.1%. Keep as baseline. | [link](2026-05-22-100331-5af9/) |
| 2fa7 | 2026-05-24 23:47 | 2000 | Minimalist beats random 75.4%; disciplined Cambio now +EV (56.0%). Tune the thresholds. | [link](2026-05-24-234719-2fa7/) |
| 288b | 2026-05-24 23:57 | 2000 | Bargain Hunter ties Minimalist (75.2%); added complexity no gain vs random. Test strategies head-to-head. | [link](2026-05-24-235734-288b/) |
| 6994 | 2026-05-26 10:34 | 63000 | Round-robin (21 entrants): new Cartographer is #1; all 5 advanced strategies top-10. Keep; promote Cartographer. | [link](2026-05-26-103439-6994/) |
| 6414 | 2026-06-04 13:27 | 23100 | Round-robin (22 entrants): smart/greedy default is mid-pack at 1664 Elo (#14/22), below all advanced + simple low-sum bots. Keep as baseline. | [link](2026-06-04-132718-6414/) |
| 06ce | 2026-06-16 14:51 | 60 | First LLM-on-ladder round-robin (6 entrants): Kimi K2 & Claude Haiku land mid-pack (1616/1641 Elo), ≈ Greedy, below Cartographer; Kimi≈Haiku (2–2 H2H). Small k=4 sample. TBD. | [link](2026-06-16-145153-06ce/) |
| 674e | 2026-07-22 12:04 | 462000 | Deep round-robin (22 entrants × 2,000/pairing, `--det-games`): 95% CIs tighten to ±5 Elo; Cartographer 1741 still #1 but mid-pack ranks shift up to 6 rungs vs k=100. Keep — quote ratings from deep runs. | [link](2026-07-22-120426-674e/) |
| 4fac | 2026-07-22 12:04 | 23100 | Control for 674e (same field/seed at k=100): ±22 Elo bands cover ranks 2–16 — the old default resolves tiers only, not the ordering. Smoke tests only. | [link](2026-07-22-120431-4fac/) |
