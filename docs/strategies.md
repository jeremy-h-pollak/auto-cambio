# Strategies (the AI layer)

A "strategy" is the computer's brain. The engine and simulator only depend on a small
**duck-typed interface**, so any object/module that implements it can play a seat:

```python
choose_move(state, known_indices)     -> move dict        # the turn decision
should_snap(state, hand_index, seat)  -> bool             # snap this card?
apply_special(state, seat, stype)     -> state            # resolve a power (seat-general)
apply_computer_special(state, stype)  -> state            # engine entry point (seat="computer")
```

`choose_move` is called **twice per turn**: first with `drawn_card is None` (return
`draw_deck` / `draw_discard` / `call_cambio`), then with the drawn card set (return
`swap` / `discard_drawn`). `move` dicts look like `{"action": "swap", "hand_index": 2}`.

There are two implementations:

## 1. The random baseline — `game/strategy.py`

A module (not a class) of pure-random decisions with light heuristics. It's the
**yardstick** every smart bot is measured against, and the default web opponent.

- **Draw phase:** 8% chance to call Cambio; otherwise 75% chance to take the discard top
  when it's worth ≤ 3, else draw from the deck.
- **Action phase:** discard the drawn card 70% of the time when it's ≥ 10 (else 40%);
  otherwise swap it into a random slot.
- **Snap:** snaps each eligible card with probability 0.7.
- **Specials:** target random valid cards.

These coded probabilities are echoed in the simulation report's "Expected (random)"
column so the implementation can be validated (see [simulation.md](simulation.md)).

## 2. The smart strategies — `game/strategies.py`

A **single parameterized** strategy (`SmartStrategy`) interpreting a `StrategyProfile`
of knobs. All 16 named bots are just different profiles — there's one decision algorithm,
not sixteen.

### `StrategyProfile` knobs

```python
@dataclass
class StrategyProfile:
    key: str
    name: str
    rules: list                       # human-readable bullets (shown in UI + reports)
    snap_mode: str = "always"         # "always" | "high_only"
    snap_min_value: int = 7           # min card value to snap when snap_mode == "high_only"
    snap_skip_negative: bool = False  # never snap a negative card (keep red Kings, -1)
    draw_discard: bool = True         # take the discard top when it beats your largest known card
    draw_discard_max: int | None = None   # ALSO take the discard top when its value <= this
    gamble_max: int = 6               # max drawn value to gamble onto an UNKNOWN slot
    cambio_all_known_sum: int = 8     # call Cambio when all cards known and sum <= this
    cambio_known_sum: int | None = None   # call with <=1 unknown when known-sum <= this
    discard_specials_for_info: bool = False  # always discard peek cards (7-10) to fire their power
```

### How `SmartStrategy` decides (`choose_move`)

- **Call Cambio?** via `_should_call_cambio`: when all live cards are known and the hand
  sum ≤ `cambio_all_known_sum`, **or** (if `cambio_known_sum` is set) with ≤ 1 unknown and
  the known-sum ≤ `cambio_known_sum`.
- **Draw source:** take the discard top if (`draw_discard` and it's lower than your
  largest known card) **or** (its value ≤ `draw_discard_max`); else draw from the deck.
- **Place or discard:** if `discard_specials_for_info` and the draw is a 7–10 peek card,
  discard it to fire the power. Else swap it over your largest known card if the draw is
  lower; else if the draw ≤ `gamble_max` and an unknown slot exists, gamble it there;
  else discard it (firing any power).
- **`should_snap`:** snap unless `snap_skip_negative` and the card is negative, or
  `snap_mode == "high_only"` and the card's value < `snap_min_value`.

`SmartStrategy.apply_special` is **seat-general** (works for either seat) and, when
`seat == "computer"`, also sets the live-app UI hint fields (`player_reveal`,
`computer_acted`, `player_touched`). Its switch powers act greedily (swap toward lower
value).

### The 16 named profiles (`PROFILES`)

`get(key)` returns a bound `SmartStrategy(PROFILES[key])`.

| Key | Name | Flavor (full bullets live in `rules`) |
|---|---|---|
| `greedy` | Greedy Minimizer | The default. Snap all, take cheaper discards, gamble ≤6, call at sum ≤8. |
| `aggressive` | Aggressive Caller | Bold gambles (≤8) and early calls (≤12, or ≤6 with one unknown). |
| `conservative` | Patient Perfectionist | Deck only, never gamble, call only at sum ≤5. |
| `snapper` | Selective Snapper | Snaps only cards ≥7 — deliberately keeps low/negative cards. |
| `power` | Power Player | Always fires peek cards (7–10); gambles only ≤4. |
| `keeper` | Negative Keeper | Greedy, but never snaps a negative (hoards red Kings). |
| `scrooge` | Bargain Hunter | Grabs any discard ≤4; keeps negatives. |
| `sniper` | Cambio Sniper | Holds out — calls only at sum ≤6; gambles ≤5. |
| `closer` | Quick Closer | Ends fast — calls at ≤10; grabs discards ≤3. |
| `highroller` | High Roller | Gambles aggressively (≤9). |
| `cautious` | Cautious Optimizer | Never gambles; calls at ≤7. |
| `opportunist` | Opportunist | Grabs discards ≤5, fires peeks, calls at ≤9. |
| `counter` | Card Counter | Always fires peek cards to map its hand. |
| `allrounder` | All-Rounder | Cheap discards (≤3), calls at ≤9 or ≤5 with one unknown. |
| `minimalist` | Minimalist | **Hardest Mode.** Snaps everything (even negatives), discards ≤4, calls at ≤7. |
| `reckless` | Reckless Rookie | **Easiest Mode.** Built to lose — never snaps, grabs any discard, gambles every draw, calls Cambio the instant its hand is known. ~36% vs random. |

## 3. The LLM strategy — `game/strategy_llm.py`

An **opt-in** strategy (`LLMStrategy`) that implements the same four-method interface
but delegates each decision to a real LLM via OpenRouter, given only the rules and the
cards it legitimately knows. It is off by default everywhere (it makes a live, metered
API call per decision) and gated behind `--enable-llm` / `CAMBIO_ENABLE_LLM`. On any
API/parse/illegal-move failure it falls back to the Greedy Minimizer (loudly logged).
See **[llm-strategy.md](llm-strategy.md)** for setup, the prompt contract, and cost
handling.

## Adding a new strategy

1. Add a `StrategyProfile` entry to `PROFILES` in `game/strategies.py` with a unique
   `key`, a `name`, a human-readable `rules` list, and whichever knobs you want to tune.
2. That's it for tuning-only bots — no engine change. It's immediately available to:
   - the **simulator**: `./run-sim.sh --strategy <key>`,
   - the **tournament**: it auto-enters via `entrants()` (which iterates `PROFILES`),
   - the **web app**: add the key to `NAMED_OPPONENTS` in `app.py` to surface it in the
     chooser (any key in `PROFILES` already resolves via `_strategy_object`).
3. If you need behavior the knobs can't express, extend `SmartStrategy` (keep it
   seat-general) or write a new module/class implementing the four-method interface above.

### `game/strategy_smart.py`

A thin facade that binds the `"greedy"` profile and re-exports `choose_move`,
`should_snap`, `apply_special`, `apply_computer_special`, and `SMART_AI_DESCRIPTION` at
module level — so a single default "smart" strategy can be imported the same way as the
random module.

## See also

- [simulation.md](simulation.md) — measure a strategy against random.
- [tournament.md](tournament.md) — rank all strategies against each other.
- [rules.md](rules.md) — the rules these decisions operate within.
