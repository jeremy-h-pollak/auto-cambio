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
| `tests/test_rules.py` | Rules (unit) | `card_value` (incl. red K = −1), `hand_value` (skips `None` slots), `is_red`, `snap_eligible_indices` / `opp_snap_eligible_indices` (rank match + known filter + empty inputs), `special_type`, `special_message` (every step + unknown-stype fallback), `create_initial_state` shape (`deck` = 43, `[F,F,T,T]`, phase `peek`), `get_scores` (the +5 penalty rules, ties), and **every `apply_move` branch**: immutability, phase transitions, snap guards (None slot / wrong rank / unknown card), swap onto an empty slot, `draw_discard` from an empty pile, and the four player special-ability flows (`pick_card` for `peek_own` / `peek_opponent` / two-step `blind_switch` / three-step `looking_switch`, `decide_switch` true & false, `skip_special`, `give_card` including the hand-emptying last-turn branch). |
| `tests/test_engine.py` | Engine (integration) | A full game driven by a trivial legal-move player reaches `game_over` and scores cleanly (exercises rules + strategy + engine end-to-end); `reset()` alternates the starting player; the simultaneous-snap coin flip (both seats can snap) is tested in both branches via patched `random.random`; `_run_computer_turn` early-returns when phase isn't `COMPUTER_TURN`. |
| `tests/test_strategies_advanced.py` | Advanced strategies (unit) | The five EV+memory bots (`Architect`, `Cartographer`, `Saboteur`, `Sprinter`, `Sentinel`) plus the shared `AdvancedStrategy` machinery: registry/`get_advanced`, `_remember` / `_prune_memory` (drops slots whose card changed or is now `None`), `_est_own_total` / `_est_opp_total`, every `choose_move` branch (Cambio call vs draw vs swap vs gamble vs power-fire vs plain discard, plus the `last_turn` path), `should_snap` (positives accepted, red K refused by default but accepted under Sprinter), `apply_special` for all four `stype`s with their "remembered-low" and "no useful memory" branches, and the Cartographer / Saboteur / Sentinel knob overrides. |
| `tests/test_strategy_smart.py` | Smart-strategy facade (unit) | `game/strategy_smart.py` rebinds the greedy `SmartStrategy` profile's methods at module level — these tests load the facade, exercise `choose_move` / `should_snap` / `apply_computer_special`, and assert `SMART_AI_DESCRIPTION` is populated. |
| `tests/test_simulator.py` | Simulator (unit) | `GameRecord.decided_on_cards` — true on an equal-score win (card-count tie-break), false on a strict-score win and on a genuine tie. |
| `tests/test_tournament.py` | Tournament (unit) | `bradley_terry` (dominance monotone & finite, balanced/all-tie uniform, geo-mean-1 normalization), `to_elo` (exact anchor, field-mean centering), `entrants` include/exclude random, and `run_tournament` bookkeeping (pairings, balanced sides, win matrix, Random anchored at 1500, seeded reproducibility, sorted rankings), including the **split schedule** — `det_k` deepens only non-LLM pairings, defaults to `k`, and reaches `on_pair`. |
| `tests/test_charts.py` | Charts (unit) | The inline-SVG primitives (`donut`, `vbar_chart`, `diverging_gap_bar`, `legend`): well-formed `<svg>`, one element/`<title>` per data point, graceful "No data" + no divide-by-zero on empty/all-zero/all-equal input, and **no `<script>`**. |
| `tests/test_insights.py` | Insights (unit) | The highlight heuristics at their thresholds — self-play verdict buckets (ceiling/edge/noise/losing + the baseline-asymmetry branch), outlier flags (ties, capped, early Cambio, favourite special), first-move/fairness, and the empty-batch guard; tournament champion/cellar, skill-spread ratio, dominant matchup, upset detection, the thin-pairing guard (share highlights ignore pairings under 30 games), and the single-entrant guard. |
| `tests/test_report_render.py` | Report renderers | Both reports **keep every existing section heading** (the additive guarantee), **add** the SVG charts + "Interesting results" highlights, stay **script-free**, and surface an uneven det/LLM game schedule in the cards, config line, and matrix tooltips. |

There are **no tests for the Flask layer** (`app.py`); coverage is otherwise scoped to the
domain logic in `game/`.

## CI and the 95% merge gate

`.github/workflows/tests.yml` runs on **every pull request** and **every push to
`main`**:

1. Checkout (`actions/checkout@v4`).
2. Python **3.13** with pip cache (`actions/setup-python@v5`).
3. `pip install -r requirements-dev.txt`.
4. `pytest --junitxml=pytest.xml --cov=game --cov-report=term-missing | tee
   pytest-coverage.txt` (with `set -o pipefail`).
5. Post a coverage comment on PRs (`MishaKav/pytest-coverage-comment@main`),
   even on failure (`if: always()`) so reviewers see the number when CI is red.

Permissions are `contents: read` + `pull-requests: write` (for the coverage comment).

**Coverage threshold: 95%.** `[tool.coverage.report] fail_under = 95` in
`pyproject.toml` makes `pytest --cov` exit non-zero whenever total coverage on
`game/` dips below 95%. Combined with the branch-protection rule on `main`
(requires the `test` check), a PR with insufficient coverage **cannot be merged**
— the merge button stays disabled until the check goes green.

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
