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

# Play against it in the web app:
CAMBIO_ENABLE_LLM=1 python app.py    # the "OpenRouter LLM" opponent appears in the chooser
```

Without `--enable-llm` / `CAMBIO_ENABLE_LLM`, the strategy is invisible:
`simulate.py --strategy llm` errors out, and the web chooser omits it. Optional
flags: `--llm-model <id>` and `--llm-snaps` (let the model decide snaps too).

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
  changes). Unknown slots render as `?`. Public facts (discard top, deck count,
  whose turn, recent public log events) are always included.
- **A single model drives moves *and* specials** through that one conversation —
  it picks peek/switch targets and the K look-then-switch decision via focused
  follow-up prompts in the same chat.
- **Snaps** use a cheap built-in heuristic by default (the snap checks fire often
  and would dominate cost); `--llm-snaps` routes them through the model.

## Cost & failure handling

- `game/llm_client.py` accumulates calls / tokens / cost for the run; `simulate.py`
  and `tournament.py` print a one-line summary at the end
  (`llm_client.summary_line()`).
- `game/llm_client.py` retries transient transport errors and HTTP 429/5xx with a
  short exponential backoff (1s, 2s, 4s; honoring `Retry-After`) before giving up —
  this smooths over free-tier rate limits. Hard 4xx (400 bad model, 401 bad key,
  402 no credit) surface immediately.
- **Every** API error, unparseable reply, or illegal move retries once, then
  **falls back to the Greedy Minimizer** so games always finish. Each fallback is
  announced loudly — a `⚠ LLM fallback (...)` line on stderr **and** in the game
  log — and counted in the end-of-run summary (`smart.fallback_count`). A non-zero
  count usually means a bad model id or a missing/invalid API key.
