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
│   ├── strategy_llm.py         # STRATEGY: opt-in LLM-in-the-loop bot (OpenRouter)
│   ├── llm_client.py           # OpenRouter chat client + run-wide token/cost accounting
│   ├── llm_prompts.py          # Versioned system prompts (v1 rules-only, v2 + playbook)
│   ├── llm_opponents.py        # Named LLM entrants: key → model id + prompt version
│   ├── engine.py               # ENGINE: GameEngine — owns state, drives live turn flow
│   ├── simulator.py            # Self-play runner (drives rules directly; symmetric snaps)
│   ├── deals.py                # Fixed shuffles for duplicate-bridge mirrored play
│   ├── charts.py               # Inline-SVG chart primitives (donut, bar, diverging) — no JS
│   ├── insights.py             # Auto-generated "interesting results" highlight heuristics
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
│   ├── test_simulator.py       # Unit tests for GameRecord bookkeeping
│   ├── test_deals.py           # Unit tests for duplicate deals + the mirrored schedule
│   ├── test_tournament.py      # Unit tests for Bradley-Terry / Elo + tournament bookkeeping
│   ├── test_charts.py          # Inline-SVG primitives: validity, empty-data, no <script>
│   ├── test_insights.py        # Highlight heuristics: thresholds + guards
│   └── test_report_render.py   # Reports keep every section + add SVG/highlights, script-free
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
- **`strategy_llm.py`**, **`llm_client.py`**, **`llm_prompts.py`**, **`llm_opponents.py`** —
  the opt-in LLM strategy: the bot itself, the OpenRouter client, the versioned system
  prompts (`v1` rules-only / `v2` + the top bot's playbook), and the registry mapping a
  named entrant (`kimi`, `haiku`, `gemini`, `gemini-v2`, `gemini-v3`) to a model id + prompt version.
  Off by default everywhere. See [llm-strategy.md](llm-strategy.md).
- **`engine.py`** — `GameEngine` for live play: owns mutable `state`, runs computer
  snaps and turns synchronously, alternates the starting player on `reset()`.
- **`simulator.py`** — batch self-play. `run_simulation(n, smart, opponent, …)` →
  `(records, timing)`; `play_game(...)` → a `GameRecord`. Enforces the symmetric snap
  sweep self-play needs. Pass `deal=` / `duplicate=True` to fix the shuffle.
- **`deals.py`** — `Deal` (a frozen 52-card order + a seed for the randomness a game
  consumes after the deal) and `make_deals(n, seed)`. Backs `--duplicate`: the same deal
  played twice with the entrants swapped, so deck luck cancels. See
  [tournament.md](tournament.md#controlling-for-deck-luck-duplicate).
- **`charts.py`** — dependency-free inline-SVG chart primitives shared by both reports:
  `donut`, `vbar_chart`, `diverging_gap_bar`, `legend`. No JavaScript; each returns a
  self-contained `<svg>` string that uses the report's CSS colour variables.
- **`insights.py`** — the highlights engine: `self_play_highlights(stats, config)` and
  `tournament_highlights(result, rows)`, pure heuristics returning a list of
  `{tone, icon, title, text}` dicts. Thresholds are named constants at the top.
- **`report.py`** — `write_report(records, timing, config, path)`: computes stats
  (`compute_stats`) and renders a self-contained HTML file with donuts, an SVG length
  chart, and the "Interesting results" section.
- **`tournament.py`** — `entrants`, `run_tournament`, `bradley_terry`, `to_elo`,
  `rankings`; the rating math.
- **`tournament_report.py`** — `write_tournament_report(...)`: an SVG rating chart,
  rankings table, head-to-head win-rate matrix, and "Interesting results" as standalone HTML.

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
