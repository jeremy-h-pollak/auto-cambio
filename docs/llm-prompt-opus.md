# The Opus-authored strategy prompt (`opus`)

An experiment in log-driven prompt authoring: instead of hand-writing strategy
advice for the LLM bot (or transplanting a heuristic bot's playbook), **Claude
Opus reviewed real game evidence and wrote the prompt itself**. The result ships
as prompt version `opus` in [`game/llm_prompts.py`](../game/llm_prompts.py),
selectable everywhere the LLM strategy runs.

## What was reviewed (2026-08-04)

- **16 full transcripts** of The Cartographer (the ladder's #1 hand-written bot,
  81% win rate in the sample) vs Random, plus 8 Greedy-vs-Random games for
  contrast — generated with `simulate.py` (free, no API calls).
- **92 real decisions** by `google/gemini-3.1-flash-lite` under the original v1
  rules-only prompt, sampled from `llm_logs/*.jsonl` (every decision `kind`,
  plus all rejected/error replies).

## Key findings

- **Winners play small and fast** [transcripts]: winning score median 5 (12 of
  16 wins at ≤6); all 16 Cartographer games ended by Cambio in ~10 turns.
- **Value swaps beat powers** [transcripts]: the 81% bot used a power **0 times
  in 16 games**; the weaker Greedy bot used 44 in 8 games, and its games ran
  ~70% longer.
- **The #1 LLM failure is refilling empty slots** [llm-log]: 13 of 16 rejected
  replies tried to place a card into an `empty` position (illegal — empties are
  permanent and score 0, i.e. they are *good*).
- **The discard pile is ignored** [llm-log]: the top was taken once in 14
  draws — including passing on a `K♥(-1)` and then calling Cambio at **13**.
- **Swaps target unknowns while known high cards sit** [llm-log]: e.g. swapping
  a drawn 3 into a `?` slot while holding a known `J♠(11)`.
- **Blind switch is near-random** [llm-log]: 12 of 12 accepted, 8 trading `?`
  for `?`; one gave away its only card (a 3); two missed a *seen* opponent Ace.
- **Powers get burned on the last turn** [llm-log], when information is
  worthless and only swaps count.
- **Verbose `reason` strings** (15–30 words on all 92 calls) waste the
  512-token reply cap.

## What the prompt does about it

The `opus` prompt keeps the v1 rules block and JSON contract essentially intact
and adds a compact playbook the small model can execute mechanically:

- `EMPTY SLOTS ARE GOOD` + "only answer with an index the prompt lists" —
  kills the dominant illegal-reply mode.
- Three named quantities computable from the visible snapshot — `MINE` (known
  total + 6 per own `?`), `THEIRS`, `H` (highest known card) — replacing
  play-by-vibes with arithmetic (deck EV ≈ 6.46 → count a `?` as 6).
- Numeric Cambio gates: call at `MINE <= 6`, or `MINE <= 10` with a 4-point
  margin over `THEIRS`; never at `MINE >= 12`.
- A narrow discard-take rule (red King, or ≤4 you can place) and a swap-target
  rule (over `H` when `H >= 7`, else the lowest `?`, if the draw is 3+ better).
- Power discipline: peek unknowns only; J/Q takes a *seen* ≤3 or dumps `H >= 8`,
  else declines — never `?` for `?`; last turn, powers are dead.
- `"reason"` capped at ~15 words.

## Measuring it

`gemini` and `gemini-opus` are the same model (`CAMBIO_GEMINI_MODEL` moves both)
behind different prompts, so entering both A/Bs the prompt alone:

```bash
# Prompt-only A/B inside the full ladder (costs money — see llm-strategy.md):
python tournament.py --enable-gemini --enable-gemini-opus -k 8 --duplicate --bootstrap 2000

# Or cheap single-strategy runs:
python simulate.py --strategy llm --enable-llm --llm-prompt opus -n 10 --seed 1
```

Every prompt-log/JSONL entry records `prompt_version`, so mixed-version logs
stay attributable. Related experiment: the sibling `v2` prompt (Cartographer's
playbook transplanted verbatim) on the `worktree-prompt-change` branch — `opus`
is the independent, log-derived take on the same question.
