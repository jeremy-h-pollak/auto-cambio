# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation — read this first

Rich, durable context lives in **[`docs/`](docs/)** — consult it before re-scanning the
code, and update the matching doc when you change behavior. Map: [docs/README.md](docs/README.md).

- [overview.md](docs/overview.md) — what the project is; the three entry points.
- [rules.md](docs/rules.md) — full rules of the Cambio variant.
- [architecture.md](docs/architecture.md) — three layers, the full state dict, the phase machine, key invariants (incl. the engine-vs-simulator snap asymmetry).
- [project-structure.md](docs/project-structure.md) — per-file responsibilities.
- [web-app.md](docs/web-app.md) — Flask routes, sessions, HTMX flow, `board.html` form fields.
- [strategies.md](docs/strategies.md) — the strategy interface, `StrategyProfile` knobs, the 15 bots, how to add one.
- [simulation.md](docs/simulation.md) · [tournament.md](docs/tournament.md) — self-play and the Bradley-Terry/Elo rating.
- [testing.md](docs/testing.md) · [reports-workflow.md](docs/reports-workflow.md) — tests/CI and the `/file` experiment log.

The sections below are a quick reference; the docs above are the source of truth.

## Running the app

```bash
python app.py          # starts Flask on port 5001 (5000 is taken by macOS AirPlay)
```

Open `http://localhost:5001` in a browser. Flask runs in debug mode so template changes reload automatically; Python changes require a server restart.

## Architecture

Three-layer separation — swap any layer without touching the others:

| Layer | File | Role |
|---|---|---|
| Rules | `game/rules.py` | Pure functions only. `apply_move(state, move) -> new_state` never mutates input (`copy.deepcopy`). All phase constants live here. |
| Strategy | `game/strategy.py` | Computer AI. `choose_move`, `should_snap`, `apply_computer_special`. Currently random; this is the layer to optimize. |
| Engine | `game/engine.py` | `GameEngine` owns state, drives turn flow. Computer turns (including snaps and specials) run **synchronously** inside `player_move()` so the HTTP response already contains the post-computer state. |

`app.py` is thin Flask glue: session UUID → `GAMES` dict → `GameEngine`. No game logic lives here.

## State model

The game state is a plain Python dict stored server-side, keyed by a session UUID. Key fields:

- `phase` — controls what actions are legal: `peek`, `player_draw`, `player_action`, `player_special`, `computer_turn`, `game_over`
- `player_known` / `computer_known` — `[bool, bool, bool, bool]`, tracks which hand positions are known to that player
- `player_opponent_known` — what the player knows about the computer's hand (via peeks)
- `player_reveal` / `player_opponent_reveal` — transient lists of indices shown face-up for exactly one response cycle; cleared only when `action in {"start", "draw_deck", "draw_discard", "call_cambio"}` **and** `current_turn == "player"`
- `special_action` — `{"type", "step", "picks"}` dict present only during `player_special` phase; drives multi-step special abilities

## Card values

A=1, 2–10=face value, J=11, Q=12, Black K (♠♣)=13, Red K (♥♦)=−1. Lowest hand sum wins; Cambio caller gets +5 penalty if they don't have the lowest score.

## Special abilities (discard-only, not on swap)

| Card | Power |
|---|---|
| 7 / 8 | Peek own card |
| 9 / 10 | Peek opponent card |
| J / Q | Blind switch |
| K | Looking switch (peek both, decide to swap) |

Switch powers are blocked after Cambio is called.

## Frontend

Pure HTMX — no hand-written JS. Every player action posts to `/move` with hidden form fields; the server returns `partials/board.html` and HTMX swaps `#board outerHTML`. The template receives `snap_eligible` (list of player hand indices matching discard top) computed in `app.py`.
