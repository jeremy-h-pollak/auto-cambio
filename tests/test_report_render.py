"""Render-layer tests: the graphical upgrade is additive (no section removed),
the new SVG charts + highlights are present, and the output stays script-free."""

from game import strategies
from game import strategy as random_strategy
from game.report import compute_stats, render_html
from game.simulator import run_simulation
from game.tournament import entrants, run_tournament
from game.tournament_report import render_tournament_html


# ── self-play report ─────────────────────────────────────────────────────────

def _render_selfplay():
    profile = strategies.PROFILES["greedy"]
    smart = strategies.SmartStrategy(profile)
    records, timing = run_simulation(
        40, smart=smart, opponent=random_strategy, seed=1, max_turns=300,
        smart_label="smart", opponent_label="random")
    stats = compute_stats(records, timing)
    config = {"seed": 1, "max_turns": 300, "strategy_name": profile.name,
              "strategy_key": profile.key, "strategy_rules": profile.rules}
    return render_html(stats, config)


def test_selfplay_keeps_every_existing_section():
    html = _render_selfplay()
    for heading in ("Win rates", "First-move advantage", "Game-length distribution",
                    "How games end", "Run-time", "Other statistics",
                    "Action distribution"):
        assert heading in html, f"lost section: {heading}"


def test_selfplay_adds_svg_and_highlights():
    html = _render_selfplay()
    assert html.count("<svg") >= 3            # win-rate donut, length chart, endings donut
    assert "Interesting results" in html
    assert 'class="highlight ' in html


def test_selfplay_is_script_free():
    assert "<script" not in _render_selfplay().lower()


# ── tournament report ────────────────────────────────────────────────────────

def _render_tournament():
    field = entrants(include_random=True)[:5]
    result = run_tournament(field, k=8, seed=1, max_turns=300)
    return render_tournament_html(result, {})


def test_tournament_keeps_every_existing_section():
    html = _render_tournament()
    for heading in ("Rankings", "Head-to-head win rates", "Methodology"):
        assert heading in html, f"lost section: {heading}"


def test_tournament_adds_svg_and_highlights():
    html = _render_tournament()
    assert "<svg" in html                     # rating diverging-bar chart
    assert "Interesting results" in html
    assert 'class="highlight ' in html


def test_tournament_is_script_free():
    assert "<script" not in _render_tournament().lower()
