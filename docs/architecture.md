# Architecture

auto-cambio is built as **three layers with a one-way dependency** so any one layer
can be swapped without touching the others:

```
        ┌─────────────────────────────────────────────────────────┐
        │  Consumers                                                │
        │  app.py (web) · simulate.py · tournament.py               │
        └───────────────┬───────────────────────┬─────────────────┘
                        │                       │
                  ┌─────▼─────┐           ┌──────▼───────┐
   Engine ───────►│ engine.py │           │ simulator.py │  ← drives rules directly,
   (live play)    └─────┬─────┘           └──────┬───────┘    bypassing the engine
                        │                        │
                  ┌─────▼────────┐         ┌─────▼─────────────────────┐
   Strategy ─────►│ strategy.py  │         │ strategies.py / _smart.py │
   (the AI)       │ (random)     │         │ (15 tunable profiles)     │
                  └─────┬────────┘         └─────┬─────────────────────┘
                        │                        │
                  ┌─────▼────────────────────────▼─────┐
   Rules ────────►│           rules.py                 │  pure functions, no I/O
   (game logic)   │  apply_move(state, move)->new_state│
                  └────────────────────────────────────┘
```

| Layer | File | Role |
|---|---|---|
| **Rules** | [`game/rules.py`](../game/rules.py) | Pure functions only. `apply_move(state, move) -> new_state` never mutates input (uses `copy.deepcopy`). All phase constants and card logic live here. |
| **Strategy** | [`game/strategy.py`](../game/strategy.py), [`game/strategies.py`](../game/strategies.py), [`game/strategy_smart.py`](../game/strategy_smart.py) | The computer's brain: `choose_move`, `should_snap`, `apply_special` / `apply_computer_special`. The layer to optimize. See [strategies.md](strategies.md). |
| **Engine** | [`game/engine.py`](../game/engine.py) | `GameEngine` owns the mutable state and drives turn flow for **live play**. Computer turns (snaps + specials) run **synchronously**. |

`app.py` is thin Flask glue (session UUID → `GAMES` dict → `GameEngine`); no game
logic lives there. The simulator and tournament **skip the engine** and drive
`rules.apply_move` directly — see *The engine vs. simulator snap asymmetry* below.

## The game state

The entire game is a single plain Python **dict**, created by
`create_initial_state(starting_turn)` and transformed by `apply_move`. There is no
class, no ORM — just a dict that gets deep-copied on every move. Every field:

| Field | Type | Meaning |
|---|---|---|
| `phase` | str | What's legal right now (see the phase machine below). |
| `current_turn` | `"player"` \| `"computer"` | Whose turn it is. |
| `deck` | list[card] | Face-down draw pile. Reshuffled from the discard pile when empty (`_reshuffle_if_needed`). |
| `discard_pile` | list[card] | Played/discarded cards; **last element is the top** (what you snap against and can draw). |
| `player_hand` / `computer_hand` | list[card \| None] | The hands. A slot becomes `None` when its card is snapped away; a "give card" snap can **append** a slot, so hands aren't always length 4. |
| `drawn_card` | card \| None | The card currently in hand, awaiting swap/discard. |
| `player_known` / `computer_known` | list[bool] | Which of *their own* positions that player knows. |
| `player_opponent_known` | list[bool] | Which of the **computer's** cards the **player** knows (from peeks). |
| `player_reveal` / `player_opponent_reveal` | list[int] | **Transient** indices shown face-up for one response cycle (UI only). |
| `computer_acted` / `player_touched` | list[int] | **Transient** UI hints: positions the computer touched / player positions its power affected this turn. |
| `special_action` | dict \| None | Present only during `player_special`: `{"type", "step", "picks"}` — drives multi-step powers. |
| `cambio_called_by` | str \| None | `None`, `"player"`, `"computer"`, or `"player_empty"` / `"computer_empty"` (round ended by an emptied hand). |
| `message` | str | Human-facing instruction for the current phase. |
| `log` | list[str] | Chronological event log (rendered reversed in the UI). |

A **card** is `{"suit": "♠"|"♥"|"♦"|"♣", "rank": "A"|"2"|…|"10"|"J"|"Q"|"K"}`.

### `special_action` detail

```python
{"type": "peek_own" | "peek_opponent" | "blind_switch" | "looking_switch" | "give_card",
 "step": 1 | 2 | 3,          # multi-step powers advance the step
 "picks": [{"owner": "player"|"computer", "index": int}, ...]}  # accumulated selections
```

## The phase machine

Phase constants live in `rules.py`:

```python
PHASE_PEEK           = "peek"
PHASE_PLAYER_DRAW    = "player_draw"
PHASE_PLAYER_ACTION  = "player_action"
PHASE_PLAYER_SPECIAL = "player_special"
PHASE_GAME_OVER      = "game_over"
COMPUTER_TURN        = "computer_turn"
```

Typical flow for a player turn:

```
peek ──start──► player_draw ──draw_deck/draw_discard──► player_action
                   │                                        │
                   │ call_cambio                  swap ─────┤ discard_drawn
                   ▼                                        ▼            │
              computer_turn ◄──────────────────────────────┘   (special? )
                   │                                          ┌──────────┘
                   │ (engine loops computer turns)            ▼
                   ▼                                   player_special
              player_draw (your next turn)         (pick_card / decide_switch
                   ...                               / skip_special) ─► advance
              game_over ◄── cambio called or a hand emptied, after the last turn
```

- `player_special` is entered only when **you** discard a special card (or after you
  snap an opponent's card → `give_card`). The computer resolves its own specials
  in-strategy without a phase change.
- `computer_turn` is where the engine takes over (live play). The human never sees this
  phase as an interactive state — `player_move` loops through all computer turns before
  returning.

## Key invariants & gotchas

**1. `apply_move` is pure.** It deep-copies the input state and returns a new one;
callers reassign (`state = apply_move(state, move)`). This is what lets the engine,
simulator, and tests share one rules implementation safely. Verified by
`tests/test_rules.py::test_apply_move_does_not_mutate_input`.

**2. Computer turns run synchronously inside `player_move`.** When the human posts a
move, `GameEngine.player_move` applies it, then runs computer snaps and loops
`_run_computer_turn()` until the phase is no longer `computer_turn`. So the HTTP
response already contains the fully-resolved post-computer state — no polling, no
async. See [web-app.md](web-app.md).

**3. Transient reveals clear on specific actions only.** `player_reveal`,
`player_opponent_reveal`, `computer_acted`, and `player_touched` are wiped only when
`action ∈ {"start", "draw_deck", "draw_discard", "call_cambio"}` **and**
`current_turn == "player"` (`_CLEAR_REVEAL_ON` in `rules.py`). This deliberately keeps a
peeked card visible for the whole turn cycle (your action → the computer's response →
until you draw again). Computer actions never clear reveals.

**4. The `start` action wipes `player_known`.** `apply_move(..., "start")` resets
`player_known` to all-`False` (the human "puts the cards back down" after the peek),
while `computer_known` keeps its `[F, F, T, T]` opening knowledge. This is an asymmetry
that matters only at the rules level for snap eligibility.

**5. The engine vs. simulator snap asymmetry — important.** The engine calls
`_run_computer_snaps()` after **every** internal `apply_move`, which gives a bot roughly
3× the snap opportunities a turn-boundary player gets — fine for a human opponent, but it
**skews self-play**. So `game/simulator.py` does **not** use the engine: it drives
`rules.apply_move` directly and runs a single **symmetric** `_snap_sweep` at each turn
boundary, and it **skips the `start` action** so both seats keep the symmetric opening
knowledge `[F, F, T, T]`. Bottom line: **use `GameEngine` for live play, the simulator
for measuring strategies.** Details in [simulation.md](simulation.md).

## Where to make changes

- **New rule / card behavior** → `game/rules.py` (keep `apply_move` pure). Add tests in
  `tests/test_rules.py`.
- **Smarter AI** → add a `StrategyProfile` in `game/strategies.py` (see
  [strategies.md](strategies.md)); no engine change needed.
- **UI / interaction** → `templates/partials/board.html` + `app.py` context (see
  [web-app.md](web-app.md)).
- **New metric in reports** → `game/report.py` (sim) or `game/tournament_report.py`
  (tournament).
