# Testing & CI

## Running tests

```bash
pip install -r requirements-dev.txt    # Flask + pytest + pytest-cov
pytest                                 # run the suite
pytest --cov=game --cov-report=term-missing   # with coverage (as CI does)
```

The project is **run, not installed**. `pyproject.toml` sets `pythonpath = ["."]` so
tests can `from game.rules import …` without a package install, scopes `testpaths` to
`tests/`, and scopes coverage to `game/`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra"

[tool.coverage.run]
source = ["game"]
omit = ["tests/*"]
```

## What's covered

| File | Layer | Covers |
|---|---|---|
| `tests/test_rules.py` | Rules (unit) | `card_value` (incl. red K = −1), `hand_value` (skips `None` slots), `is_red`, `snap_eligible_indices` (rank match + known filter + empty inputs), `special_type`, `create_initial_state` shape (`deck` = 43, `[F,F,T,T]`, phase `peek`), `get_scores` (the +5 penalty rules, ties), and `apply_move` **immutability** + phase transitions. |
| `tests/test_engine.py` | Engine (integration) | A full game driven by a trivial legal-move player reaches `game_over` and scores cleanly (exercises rules + strategy + engine end-to-end); `reset()` alternates the starting player. |
| `tests/test_simulator.py` | Simulator (unit) | `GameRecord.decided_on_cards` — true on an equal-score win (card-count tie-break), false on a strict-score win and on a genuine tie. |
| `tests/test_tournament.py` | Tournament (unit) | `bradley_terry` (dominance monotone & finite, balanced/all-tie uniform, geo-mean-1 normalization), `to_elo` (exact anchor, field-mean centering), `entrants` include/exclude random, and `run_tournament` bookkeeping (pairings, balanced sides, win matrix, Random anchored at 1500, seeded reproducibility, sorted rankings). |
| `tests/test_charts.py` | Charts (unit) | The inline-SVG primitives (`donut`, `vbar_chart`, `diverging_gap_bar`, `legend`): well-formed `<svg>`, one element/`<title>` per data point, graceful "No data" + no divide-by-zero on empty/all-zero/all-equal input, and **no `<script>`**. |
| `tests/test_insights.py` | Insights (unit) | The highlight heuristics at their thresholds — self-play verdict buckets (ceiling/edge/noise/losing + the baseline-asymmetry branch), outlier flags (ties, capped, early Cambio, favourite special), first-move/fairness, and the empty-batch guard; tournament champion/cellar, skill-spread ratio, dominant matchup, upset detection, and the single-entrant guard. |
| `tests/test_report_render.py` | Report renderers | Both reports **keep every existing section heading** (the additive guarantee), **add** the SVG charts + "Interesting results" highlights, and stay **script-free**. |

There are **no tests for the Flask layer** (`app.py`); coverage is otherwise scoped to the
domain logic in `game/`.

## CI

`.github/workflows/tests.yml` runs on **every pull request** and **every push to
`main`**:

1. Checkout (`actions/checkout@v4`).
2. Python **3.13** with pip cache (`actions/setup-python@v5`).
3. `pip install -r requirements-dev.txt`.
4. `pytest --junitxml=pytest.xml --cov=game --cov-report=term-missing | tee
   pytest-coverage.txt` (with `set -o pipefail`).
5. On PRs only, post a coverage comment (`MishaKav/pytest-coverage-comment@main`).

Permissions are `contents: read` + `pull-requests: write` (for the coverage comment).

## Conventions when adding tests

- New rule behavior → unit-test it in `tests/test_rules.py`; keep `apply_move` pure so
  tests can assert the input state is untouched.
- Strategy/engine behavior that spans a whole turn cycle → an integration-style test like
  `test_engine.py` (seed the RNG for determinism, e.g. `random.seed(0)`).
- Rating/tournament math → `tests/test_tournament.py`, using the `_round_robin` helper to
  build synthetic win matrices.
- New chart primitive → `tests/test_charts.py` (assert valid `<svg>`, correct element
  count, graceful empty-data, no `<script>`). New highlight rule → `tests/test_insights.py`
  (feed a minimal stats dict / synthetic result and assert the tone+title at the threshold).
- New report section → extend `tests/test_report_render.py` so the heading is asserted
  present, locking in the "never silently drop a section" guarantee.
