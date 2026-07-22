---
id: 4fac
date: 2026-07-22
time: 120431
source: scratchpad/shallow.html (python tournament.py -k 100 --seed 1 --quiet --bootstrap 2000)
games: 23100
seed: 1
filed_at: 2026-07-22 12:04
---

# Self-play report 4fac

Round-robin tournament (not a single-strategy `simulate.py` run): 22 entrants ×
**100 games/pairing** — the old default depth. This is the control half of a paired
experiment; the treatment is [674e](../2026-07-22-120426-674e/), the identical field and
seed at 2,000 games/pairing. Filed together so the cost of shallow sampling is on record.

## Headline stats
- 22 entrants · 100 games/pairing · 23,100 games · seed=1 · max_turns=1000
- Tie rate 1.6% · avg game length 16.8 turns · throughput 637 games/sec (36s wall)
- Champion: **The Cartographer, 1740 Elo** (63.0% of 2,100 games), CI [1717, 1763]
- Cellar: **Reckless Rookie, 1347** (14.0%), CI [1320, 1370]
- Skill spread: 393 Elo first-to-last (~10:1 expected wins)
- Random anchors at 1500, rank 20/22
- Typical 95% CI half-width: **±22 Elo**

## Analysis
- Directly comparable to run [6414](../2026-06-04-132718-6414/) (same 22-entrant field,
  same k=100, different seed): Cartographer #1 and the same broad tiers, so the ladder is
  stable across seeds at the tier level.
- It is **not** stable at the rank level. Against the deep run at the same seed, six-plus
  strategies shift: Quick Closer #2 → #5, The Sprinter #6 → #11, All-Rounder #11 → #15,
  Power Player #16 → #16 but via a different path. The ±22 bands cover ranks 2–16 almost
  entirely — this ordering was never resolved.
- The highlights block shows the same fragility: "biggest upset" here is Power Player over
  The Sentinel at 54% of **100** games (an 8-rung upset); in the deep run that pairing is
  unremarkable. Single-pairing narratives at k=100 are mostly sampling noise.
- Extremes are trustworthy even here: Cartographer (1740 vs 1741 deep) and Reckless Rookie
  (1347 vs 1348) land within 1 Elo of their deep values, as do the random-tier bots.
- 23,100 games in 36s vs 462,000 in 741s — depth is cheap enough that there is no reason
  to publish a k=100 ranking.

## Findings
- **Tested:** the control condition for the `--det-games` experiment (PR #42) — what the
  old default depth actually resolves.
- **Key takeaway:** k=100 resolves the tiers (champion, the pack, the random tier, the
  cellar) and nothing finer. Its ±22 Elo bands overlap across most of the field.
- **Surprises / concerns:** past mid-pack rankings quoted from k=100 runs — including
  6414's "#14/22" placement for the greedy/smart default — carry roughly ±7 ranks of
  uncertainty and should be re-derived at depth before being cited.
- **Verdict / next step:** keep as the documented control. Use k=100 for smoke tests
  only; quote ratings from `--det-games 2000`.

*(Filed non-interactively — the session was running in auto mode, so the Findings above
come from the experiment itself rather than a user interview.)*
