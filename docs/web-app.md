# Web app

The web game is **Flask + pure HTMX** — every player action posts a form, the server
returns an HTML fragment, and HTMX swaps it into the page. There is **no hand-written
JavaScript**. Game logic lives entirely in [`game/`](../game/); `app.py` is glue.

Launch with `./run-game.sh` (or `python app.py`) and open <http://localhost:5001>.
Port 5001 is used because macOS AirPlay reserves 5000. Flask runs in **debug mode**, so
template edits hot-reload but Python changes need a server restart.

## Sessions → games

State is held **server-side, per session**:

```python
GAMES: dict[str, GameEngine] = {}     # app.py
```

- Each browser session gets a UUID stored in the Flask session cookie (`session["sid"]`).
- `_get_engine()` looks up (or lazily creates) the `GameEngine` for that `sid` in `GAMES`.
- `session["opponent"]` holds the chosen opponent key; a fresh `GameEngine` is built with
  the matching strategy.

Because `GAMES` is an in-process dict, **state is lost when the Flask process restarts**,
and it does not scale across workers. Fine for local single-player use.

## Routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Landing page — renders the opponent chooser (`partials/chooser.html`). |
| `/choose` | POST | Re-render the chooser (HTMX "New Game" / "Back"). |
| `/describe` | POST | Show the chosen opponent's rules and a confirm prompt (`partials/confirm.html`). |
| `/play` | GET | Render the board for the current engine. |
| `/move` | POST | Apply the player's move, run the computer's response, return `partials/board.html`. |
| `/new` | POST | Set `session["opponent"]`, build a fresh `GameEngine`, return the board. |

## The synchronous move cycle

`/move` is the heart of it. It reads the form, calls `engine.player_move(...)`, and
returns the re-rendered board. Crucially, **the computer's entire response happens inside
that one call** — `GameEngine.player_move` applies the player's move, runs computer
snaps, then loops `_run_computer_turn()` until it's the player's turn again
([`game/engine.py`](../game/engine.py)). So the returned fragment already shows the
post-computer state; HTMX never has to poll. See [architecture.md](architecture.md) for
why computer turns are synchronous.

## Template context

`_template_context(engine)` builds everything the board needs:

```python
{
  "state": s,                       # the full game-state dict
  "card_value", "hand_value", "is_red",   # rules helpers exposed to Jinja
  "player_score", "computer_score", # only when phase == game_over, else None
  "snap_eligible":     snap_eligible_indices(s["player_hand"], s["discard_pile"], s["player_known"]),
  "opp_snap_eligible": opp_snap_eligible_indices(s["computer_hand"], s["player_opponent_known"], s["discard_pile"]),
  "opponent", "opponent_name", "opponent_rules",
}
```

`snap_eligible` / `opp_snap_eligible` are precomputed index lists so the template can
just highlight clickable cards.

## HTMX flow

```
GET /  ──► chooser.html ──(POST /describe)──► confirm.html ──(POST /new)──► board.html
                                                                                │
   board.html ──(POST /move, hidden form fields)──► board.html  (loops each move)
                                                                                │
                       game over ──(POST /new)──► fresh board.html
```

Every interactive element is a small `<form hx-post="…" hx-target="#board"
hx-swap="outerHTML">` — clicking a card or button posts the form and replaces the
`#board` div with the server's new render. `base.html` loads HTMX 2.0.4; `game.html`
just `{% include %}`s the active partial.

## Form fields posted to `/move`

`board.html` posts these hidden fields (the route reads each via `request.form.get`):

| Field | Values | Used for |
|---|---|---|
| `action` | `start`, `draw_deck`, `draw_discard`, `swap`, `discard_drawn`, `snap`, `pick_card`, `decide_switch`, `skip_special`, `call_cambio` | Which move. |
| `hand_index` | `0`–`n` | Which hand position (swap / snap / pick). |
| `owner` | `player` \| `computer` | Whose card, during a special pick (`pick_card`). |
| `do_switch` | `true` \| `false` | The K looking-switch decision (`decide_switch`). |
| `target` | `computer` | Marks a snap against the **opponent's** hand. |

The interactive states in `board.html` are gated by phase:

- **peek** → "Start Game" button (`start`).
- **player_draw** → click deck/discard to draw; "Call Cambio"; snap highlights.
- **player_action** → click a hand card to `swap`, or "Discard Drawn Card".
- **player_special** → click cards to `pick_card`; "Skip Power"; for K, "Switch" /
  "Don't Switch" (`decide_switch`).
- **game_over** → result banner + "Play Again" (`/new`).

## Opponent chooser

Defined in `app.py`:

- `HARDEST_KEY = "minimalist"` — surfaced as 🔥 **Hardest Mode** (the strongest of the 15
  profiles vs. random, ~75% win rate).
- `NAMED_OPPONENTS = ["greedy", "aggressive", "conservative", "snapper", "power"]`.
- `OPPONENT_KEYS = ["hardest"] + NAMED_OPPONENTS + ["random"]` — the chooser display order.
- `_opponent_info(key)` → `(name, rules)`; `_strategy_object(key)` → the strategy the
  engine drives. The chooser shows each bot's human-readable `rules` so you know what
  you're up against. See [strategies.md](strategies.md).

## Snapping the opponent's card

When you click a *known computer card* that matches the discard top, `board.html` posts
`action=snap` + `target=computer` (with no `owner`). `/move` forwards `target` to
`engine.player_move(...)`, which threads it into the `move` dict; `apply_move` then runs
the opponent-snap branch — `{"action": "snap", "by": "player", "target": "computer",
"hand_index": i}` removes the opponent's card and enters the `give_card` special, where
you pick one of your own cards to hand them.

> History: `player_move` originally didn't accept `target` (its signature stopped at
> `do_switch`), so this click raised `TypeError: ... unexpected keyword argument 'target'`
> and 500'd. Fixed by adding `target=None` to `player_move` and forwarding it; regression
> test: `tests/test_engine.py::test_player_move_forwards_target_for_opponent_snap`.
