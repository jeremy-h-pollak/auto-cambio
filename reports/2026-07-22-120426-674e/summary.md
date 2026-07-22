---
id: 674e
date: 2026-07-22
time: 120426
source: scratchpad/deep.html (python tournament.py --det-games 2000 --seed 1 --quiet --bootstrap 2000)
games: 462000
seed: 1
filed_at: 2026-07-22 12:04
---

# Self-play report 674e

Round-robin tournament (not a single-strategy `simulate.py` run): 22 entrants ×
**2,000 games/pairing**, balanced sides, with 2,000-replicate bootstrap CIs. This is the
deep half of a paired experiment — see [4fac](../2026-07-22-120431-4fac/) for the same
field, same seed, at the old default of 100 games/pairing. Run to validate the new
`--det-games` flag (PR #42), which lets pairings between deterministic (non-LLM)
entrants play far more games than metered LLM pairings.

## Headline stats
- 22 entrants · 2,000 games/pairing · 462,000 games · seed=1 · max_turns=1000
- Tie rate 1.6% · avg game length 16.9 turns · throughput 624 games/sec (741s wall)
- Champion: **The Cartographer, 1741 Elo** (63.2% of 42,000 games), CI [1736, 1746]
- Cellar: **Reckless Rookie, 1348** (14.9%), CI [1342, 1354]
- Skill spread: 392 Elo first-to-last (~10:1 expected wins)
- Random anchors at 1500, rank 20/22
- Typical 95% CI half-width: **±5 Elo**

Ladder (rating, 95% CI):

| # | Strategy | Rating | 95% CI |
|---|---|---|---|
| 1 | The Cartographer | 1741 | [1736, 1746] |
| 2 | Opportunist | 1708 | [1703, 1713] |
| 3 | Bargain Hunter | 1703 | [1698, 1708] |
| 4 | Minimalist | 1701 | [1696, 1706] |
| 5 | Quick Closer | 1696 | [1691, 1701] |
| 6 | The Sentinel | 1688 | [1683, 1693] |
| 7 | Card Counter | 1687 | [1683, 1692] |
| 8 | The Saboteur | 1687 | [1682, 1692] |
| 9 | The Architect | 1683 | [1678, 1688] |
| 10 | Negative Keeper | 1677 | [1672, 1681] |
| 11 | The Sprinter | 1676 | [1671, 1681] |
| 12 | Greedy Minimizer | 1672 | [1667, 1677] |
| 13 | Cambio Sniper | 1670 | [1665, 1675] |
| 14 | High Roller | 1658 | [1653, 1663] |
| 15 | All-Rounder | 1657 | [1652, 1662] |
| 16 | Power Player | 1657 | [1652, 1662] |
| 17 | Aggressive Caller | 1620 | [1615, 1625] |
| 18 | Selective Snapper | 1574 | [1569, 1579] |
| 19 | Patient Perfectionist | 1501 | [1496, 1506] |
| 20 | Random | 1500 | [1500, 1500] (anchor) |
| 21 | Cautious Optimizer | 1488 | [1483, 1493] |
| 22 | Reckless Rookie | 1348 | [1342, 1354] |

## Analysis
- **CIs shrank 4.4×** vs the paired k=100 run (±5 vs ±22 Elo), almost exactly the
  √20 ≈ 4.5 the bootstrap theory predicts. That is the headline result: the schedule
  change buys real resolution, not just more digits.
- **The middle of the ladder was noise at k=100.** Quick Closer ranked #2 there and #5
  here; The Sprinter #6 → #11; All-Rounder #11 → #15. Ratings at the top and bottom
  barely moved (Cartographer 1740 → 1741, Reckless Rookie 1347 → 1348), so the coarse
  tiers were right all along — only the pack ordering was fiction.
- Even at ±5, ranks 6–13 sit inside ~18 Elo, i.e. **still not cleanly separated**. The
  low-skill-ceiling story holds: once a bot plays sensibly, extra cleverness buys little.
  Ranks 14–16 (High Roller / All-Rounder / Power Player, 1657–1658) are a true three-way
  tie with fully overlapping bands.
- Tier structure that *is* resolved: Cartographer alone → a 1657–1708 pack →
  Aggressive Caller 1620 → Selective Snapper 1574 → the random tier (Patient
  Perfectionist 1501 ≈ Random 1500 ≈ Cautious Optimizer 1488) → Reckless Rookie 1348.
  **Patient Perfectionist and Cautious Optimizer are indistinguishable from Random.**
- Tie rate (1.6%) and mean game length (16.9 turns) are unchanged from every prior run —
  20× more games did not move either, which is a good sanity check on the simulator.
- Cosmetic nit spotted in the highlights block: "Biggest upset" reports The Sprinter over
  Quick Closer "at 50%" — the underlying share is just over 50% and gets rounded down for
  display. Worth a `.1f` there eventually; not a correctness issue.

## Findings
- **Tested:** the new `--det-games N` schedule (PR #42) — deterministic pairings play
  `N` games while LLM pairings stay at `-k` — and whether the extra depth changes the
  ladder rather than just narrowing the error bars.
- **Key takeaway:** ±5 Elo at 2,000 games/pairing vs ±22 at 100, for 12 minutes of free
  local compute. Deep runs are now the default way to quote bot ratings; k=100 is a
  smoke test only.
- **Surprises / concerns:** three strategies moved 4–6 ranks between the two runs, so
  any past conclusion drawn from a k=100 ordering in the middle of the pack should be
  treated as unsupported. Ranks 6–13 remain unresolved even here — separating them would
  need another order of magnitude, and may not be worth it given the skill ceiling.
- **Verdict / next step:** keep. Quote ratings from `--det-games 2000` runs going
  forward; pair a tiny `-k` with a large `--det-games` whenever LLM entrants are in the
  field so the API bill stays pinned to the LLM pairings.

*(Filed non-interactively — the session was running in auto mode, so the Findings above
come from the experiment itself rather than a user interview.)*
