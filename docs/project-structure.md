# Project structure

Annotated layout of the repository. Paths are relative to the repo root.

```
auto-cambio/
├── app.py                      # Flask web app: sessions, routes, template context
├── simulate.py                 # CLI: self-play simulation → report.html
├── tournament.py               # CLI: round-robin tournament → tournament.html
├── run-game.sh                 # ./run-game.sh  → python app.py
├── run-sim.sh                  # ./run-sim.sh   → python simulate.py "$@"
├── run-tournament.sh           # ./run-tournament.sh → python tournament.py "$@"
│
├── game/                       # The domain logic (three-layer core)
│   ├── __init__.py
│   ├── rules.py                # RULES layer: pure apply_move, phases, card/scoring logic
│   ├── strategy.py             # STRATEGY: the random baseline bot
│   ├── strategies.py           # STRATEGY: StrategyProfile + SmartStrategy + 15 named bots
│   ├── strategy_smart.py       # STRATEGY: thin facade exposing the "greedy" profile as a module
│   ├── engine.py               # ENGINE: GameEngine — owns state, drives live turn flow
│   ├── simulator.py            # Self-play runner (drives rules directly; symmetric snaps)
│   ├── report.py               # Standalone HTML report for a simulation batch
│   ├── tournament.py           # Round-robin + Bradley-Terry → Elo rating
│   └── tournament_report.py    # Standalone HTML report for a tournament (ranking + matrix)
│
├── templates/                  # Jinja2 templates (pure HTMX, no hand-written JS)
│   ├── base.html               # HTML shell; loads HTMX 2.0.4 and the stylesheet
│   ├── game.html               # Wrapper that includes the active partial
│   └── partials/
│       ├── chooser.html        # Opponent-selection lobby
│       ├── confirm.html        # "Play this AI?" confirmation with its rules
│       └── board.html          # The game board — HTMX swap target (#board)
│
├── static/
│   └── css/style.css           # All styling for the web app
│
├── tests/                      # pytest suite (run in CI)
│   ├── test_rules.py           # Unit tests for the pure rules layer
│   ├── test_engine.py          # Integration smoke test for full-game turn flow
│   └── test_tournament.py      # Unit tests for Bradley-Terry / Elo + tournament bookkeeping
│
├── reports/                    # Archived experiment runs (see reports-workflow.md)
│   ├── INDEX.md                # One-row-per-run log table
│   └── <date>-<time>-<id>/     # report.html + summary.md per filed run
│
├── docs/                       # ← you are here
├── CLAUDE.md                   # Guidance for Claude Code; points at docs/
├── README.md                   # Human-facing entry point
├── pyproject.toml              # pytest + coverage config (not a packaged install)
├── requirements.txt            # Runtime deps: Flask>=3.0
├── requirements-dev.txt        # + pytest, pytest-cov
├── .github/workflows/tests.yml # CI: pytest + coverage comment on PRs
└── .gitignore                  # ignores report.html / tournament.html, coverage artifacts
```

## File responsibilities

### Entry points

- **`app.py`** — Flask glue. Maps a session UUID to a `GameEngine` in the in-memory
  `GAMES` dict, builds the template context, and exposes the routes. No game logic.
  See [web-app.md](web-app.md).
- **`simulate.py`** — argparse CLI for self-play (smart-vs-random or random-vs-random).
  Calls `simulator.run_simulation` and `report.write_report`. See [simulation.md](simulation.md).
- **`tournament.py`** — argparse CLI for the round-robin across all strategies. Calls
  `tournament.run_tournament` and `tournament_report.write_tournament_report`. See
  [tournament.md](tournament.md).
- **`run-*.sh`** — thin wrappers that `cd` to the repo root (so `templates/`, `static/`
  resolve) and `exec` the matching Python entry point, forwarding `"$@"`.

### `game/` — the core

- **`rules.py`** — the rules layer. `apply_move`, `create_initial_state`, `card_value`,
  `hand_value`, `snap_eligible_indices`, `special_type`, `get_scores`, and the phase
  constants. Pure; never mutates input. See [architecture.md](architecture.md).
- **`strategy.py`** — the **random** baseline strategy (the yardstick every smart bot
  aims to beat). Module-level `choose_move` / `should_snap` / `apply_computer_special` /
  `apply_special`.
- **`strategies.py`** — the **smart** strategies: the `StrategyProfile` dataclass of
  tunable knobs, the `SmartStrategy` engine that interprets a profile, and `PROFILES`
  (15 named bots). `get(key)` returns a bound `SmartStrategy`. See [strategies.md](strategies.md).
- **`strategy_smart.py`** — a thin module facade binding the `"greedy"` profile so it can
  be imported like the random strategy module.
- **`engine.py`** — `GameEngine` for live play: owns mutable `state`, runs computer
  snaps and turns synchronously, alternates the starting player on `reset()`.
- **`simulator.py`** — batch self-play. `run_simulation(n, smart, opponent, …)` →
  `(records, timing)`; `play_game(...)` → a `GameRecord`. Enforces the symmetric snap
  sweep self-play needs.
- **`report.py`** — `write_report(records, timing, config, path)`: computes stats
  (`compute_stats`) and renders a self-contained HTML file.
- **`tournament.py`** — `entrants`, `run_tournament`, `bradley_terry`, `to_elo`,
  `rankings`; the rating math.
- **`tournament_report.py`** — `write_tournament_report(...)`: rankings table +
  head-to-head win-rate matrix as standalone HTML.

### Templates & static

Pure-HTMX front end; see [web-app.md](web-app.md) for the request flow. `board.html` is
the swap target for `#board`; `chooser.html` and `confirm.html` are the lobby.

### Tests, CI, config

See [testing.md](testing.md). `pyproject.toml` configures pytest (`testpaths=["tests"]`,
`pythonpath=["."]` so `from game.rules import …` works without installing) and scopes
coverage to `game/`. The project is **run, not installed** — there's no `setup.py` /
build.

### `reports/`

Archived self-play runs, one folder per filed run, logged in `INDEX.md`. Produced by the
`/file` skill — see [reports-workflow.md](reports-workflow.md).
