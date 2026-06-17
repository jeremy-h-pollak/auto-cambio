# LLM strategy (OpenRouter)

An opt-in strategy that puts a real LLM in the decision loop instead of a
hand-written heuristic. The model is given **only the rules and the cards it
legitimately knows**, then asked to choose each move. It is **off by default
everywhere** because every decision is a live, metered, network API call.

- `game/llm_client.py` — thin OpenRouter chat client + run-wide token/cost accounting.
- `game/strategy_llm.py` — `LLMStrategy`, implementing the usual duck-typed
  interface (`choose_move` / `should_snap` / `apply_special` /
  `apply_computer_special`); see [strategies.md](strategies.md).

## Setup

1. Sign in at <https://openrouter.ai>. To actually evaluate the bot, add a little
   credit (Settings → Credits, e.g. $5). Free models work too (see billing below).
2. Create an API key (Keys page) and **set a per-key credit limit** (e.g. $5) so
   spend is hard-capped. Copy the `sk-or-...`.
3. Put it in a `.env` file at the repo root (gitignored; auto-loaded via
   `python-dotenv`). Copy the template and edit it:
   ```bash
   cp .env.example .env
   # then set OPENROUTER_API_KEY=sk-or-...  (and optionally OPENROUTER_MODEL)
   ```
   (Exporting the vars in your shell instead also works — `.env` is just the
   convenient default.)
4. (Optional) choose the model. `DEFAULT_MODEL` in `game/llm_client.py` is a cheap
   default (`google/gemini-3.1-flash-lite`). Override with `OPENROUTER_MODEL` in
   `.env`. Confirm current ids/pricing on <https://openrouter.ai/models> — model
   slugs change over time.

### Billing — no surprise charges

OpenRouter is **prepaid**. Your card is charged only when **you click to buy
credits**; usage draws down that balance and stops (HTTP 402) at $0 — it is never
silently billed. **Auto-top-up is off by default**, so your maximum exposure is the
credit you chose to load, and a **per-key spend limit** caps it further regardless
of any bug. `:free` models cost $0 but are rate-limited (~20 req/min; ~50 req/day
until you've bought ≥$10 lifetime, then ~1000/day) — since this strategy makes
2–5 calls per turn (50–100 per game), free tier suits only a tiny wiring check.

## Running it

```bash
# Self-play vs Random (keep -n small — every turn is an API call):
python simulate.py --strategy llm --enable-llm -n 5 --seed 1

# Add it to the round-robin (cost scales with -k × field size — use a tiny -k):
python tournament.py --enable-llm -k 4

# Enter the two named models as distinct competitors, ranked against the whole field:
python tournament.py --enable-kimi --enable-haiku -k 4

# Play against it in the web app:
CAMBIO_ENABLE_LLM=1 python app.py    # the two LLM opponents appear in the chooser
```

Without `--enable-llm` / `CAMBIO_ENABLE_LLM`, the strategy is invisible:
`simulate.py --strategy llm` errors out, and the web chooser omits it. Optional
flags: `--llm-model <id>` and `--llm-snaps` (let the model decide snaps too).

### Web chooser: two model-specific opponents

With `CAMBIO_ENABLE_LLM=1`, the web chooser surfaces **two** named LLM opponents
rather than one generic entry, so you can pick which model to play against:

- **Kimi K2 (LLM)** — `moonshotai/kimi-k2`
- **Claude Haiku (LLM)** — `anthropic/claude-haiku-4.5`

Both are plain `LLMStrategy` instances built with an explicit `model=` (see
`_strategy_object` in `app.py`); the model id is recorded on every prompt-log entry
(below), so the log header tells you which model produced each move. OpenRouter
slugs drift, so each is overridable without code edits via `CAMBIO_KIMI_MODEL` /
`CAMBIO_HAIKU_MODEL`, e.g.:

```bash
CAMBIO_ENABLE_LLM=1 CAMBIO_KIMI_MODEL=moonshotai/kimi-k2-thinking python app.py
```

The model registry lives in `game/llm_opponents.py` (`NAMED_LLM_OPPONENTS`), shared by
both `app.py` and `tournament.py`. `simulate.py` still uses only the generic `llm`
strategy plus `--llm-model` / `OPENROUTER_MODEL`, but `tournament.py` can now enter the
named models as distinct competitors via `--enable-kimi` / `--enable-haiku` (each a
separate entrant with its own model, rankable against the full field).

## Prompt log — watch what the model is asked and answers

When you play the web app against either LLM opponent, a collapsible **“AI prompt
log”** panel appears under the board and updates after each move. Every model call
is captured (newest first) with the three things that define the decision:

- **Reasoning** — the model's own one-sentence rationale. Every prompt requires a
  leading `"reason"` key in the JSON reply (reason-before-move), so the panel shows
  *why* it played each move, not just what. It is best-effort: a missing reason is
  logged as blank and never fails the move.
- **GSi** — the fair-information game-state snapshot the model saw that turn. This
  now includes a **known-card total** line (the sum of the cards this seat
  legitimately knows) so the model doesn't have to recompute it each turn.
- **Pi** — the assembled prompt: the instruction + the legal moves it was offered.
- **Mi** — the raw model reply, plus the parsed move (or the error, if a reply was
  illegal/unparseable or the API failed).

This is an *observation* view: GSi shows the AI's own perspective, so it
deliberately reveals the cards the model legitimately knows about — handy for
debugging, but it does spoil some of the opponent's hand.

The same entries are appended as JSON lines to a transcript file so you can review a
full game afterward. The default path is `llm_logs/prompts.jsonl` under the repo
root (gitignored); override it with `CAMBIO_LLM_LOG=/path/to/log.jsonl`. Each line
carries a UTC `ts`, a per-game `session` id, the `seat`, the decision `kind`
(`draw`, `action`, `snap`, `peek_own`, `peek_opponent`, `blind_switch`, `look`,
`look_decide`), the `model`, the `state`/`prompt`/`full_prompt`, the raw `response`,
the `parsed` move, the model's `reason`, and any `error`. Both sinks are populated in `LLMStrategy._ask`
(`game/strategy_llm.py`), the single point every prompt flows through; a failed file
write is swallowed (one stderr warning) so logging never interrupts a game.

Note: with the default snap heuristic (web default; no `--llm-snaps`), snap
decisions make no API call and so produce no prompt-log entries.

## How it works

- **One running conversation per game.** A system message states the rules and
  which seat the model is and who moved first; each decision is appended as a new
  user/assistant exchange. The conversation lives in `state["_llm"][seat]`, which
  survives because `rules.apply_move` deep-copies the state (same trick the
  advanced strategies use for memory) and resets when the next game's state is
  created.
- **Fair information only.** Each prompt is built solely from what the seat
  legitimately knows: its own `*_known` slots and opponent slots it has peeked
  (tracked in `state["_lmem"][seat]`, pruned when a remembered card publicly
  changes). Unknown slots render as `?`, and a **known-card total** (the sum over
  the slots this seat knows) is included so the model isn't left to add them up.
  Public facts (discard top, deck count, whose turn, recent public log events) are
  always included.
- **Reason-before-move.** Every prompt asks the model to lead its JSON reply with a
  short `"reason"` so it reasons before committing; the rationale is captured in the
  prompt log / JSONL but is best-effort and never affects move validation.
- **A single model drives moves *and* specials** through that one conversation —
  it picks peek/switch targets and the K look-then-switch decision via focused
  follow-up prompts in the same chat.
- **Snaps** use a cheap built-in heuristic by default (the snap checks fire often
  and would dominate cost); `--llm-snaps` routes them through the model.

## Cost & failure handling

- `game/llm_client.py` accumulates calls / tokens / cost for the run; `simulate.py`
  and `tournament.py` print a one-line summary at the end
  (`llm_client.summary_line()`). A multi-model run (e.g. Kimi + Haiku in one
  tournament) also gets a **per-model** breakdown via `llm_client.summary_by_model()`.
- Requests cap `max_tokens` low (replies are tiny JSON moves). OpenRouter
  credit-checks the *requested* max, not the actual output, so a model's huge
  default would trigger premature `402`s when little credit remains; the cap lets a
  run use nearly its full budget without changing real cost.
- `game/llm_client.py` retries transient transport errors and HTTP 429/5xx with a
  short exponential backoff (1s, 2s, 4s; honoring `Retry-After`) before giving up —
  this smooths over free-tier rate limits. Hard 4xx (400 bad model, 401 bad key,
  402 no credit) surface immediately.
- **Every** API error, unparseable reply, or illegal move retries once, then
  **falls back to the Greedy Minimizer** so games always finish. Each fallback is
  announced loudly — a `⚠ LLM fallback (...)` line on stderr **and** in the game
  log — and counted in the end-of-run summary (`smart.fallback_count`). A non-zero
  count usually means a bad model id or a missing/invalid API key.
