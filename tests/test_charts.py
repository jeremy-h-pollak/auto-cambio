"""Unit tests for the inline-SVG chart primitives (game/charts.py)."""

from game import charts


def _is_svg(s):
    return s.lstrip().startswith("<svg") and s.rstrip().endswith("</svg>")


# ── donut ──────────────────────────────────────────────────────────────────

def test_donut_renders_one_arc_per_nonzero_segment():
    svg = charts.donut([("A", 3, "var(--smart)"), ("B", 1, "var(--random)")],
                       center_label="75%", center_sub="A wins")
    assert _is_svg(svg)
    # background ring + 2 segment arcs = 3 circles; 2 segment <title>s.
    assert svg.count("<circle") == 3
    assert svg.count("<title>") == 2
    assert "75%" in svg and "A wins" in svg
    # share is computed from the value, not assumed: 3/4 → 75.0%
    assert "75.0%" in svg


def test_donut_skips_zero_segments():
    svg = charts.donut([("A", 5, "var(--smart)"), ("Zero", 0, "var(--random)")])
    assert svg.count("<title>") == 1  # the zero segment is dropped


def test_donut_empty_is_graceful():
    assert "No data" in charts.donut([])
    assert "No data" in charts.donut([("A", 0, "x"), ("B", 0, "y")])


# ── vbar_chart ───────────────────────────────────────────────────────────────

def test_vbar_chart_has_a_bar_per_bin_with_titles():
    bins = [("2-3", 4), ("4-5", 10), ("6-7", 2)]
    svg = charts.vbar_chart(bins)
    assert _is_svg(svg)
    assert svg.count("<rect") == len(bins)
    assert svg.count("<title>") == len(bins)
    assert "4-5" in svg  # x label present


def test_vbar_chart_empty_is_graceful():
    assert "No data" in charts.vbar_chart([])


def test_vbar_chart_all_zero_counts_does_not_crash():
    svg = charts.vbar_chart([("a", 0), ("b", 0)])
    assert _is_svg(svg)
    assert svg.count("<rect") == 2


# ── diverging_gap_bar ────────────────────────────────────────────────────────

def test_diverging_gap_bar_one_bar_per_row():
    rows = [("Top", 1700.0), ("Mid", 1500.0), ("Low", 1400.0)]
    svg = charts.diverging_gap_bar(rows)
    assert _is_svg(svg)
    assert svg.count("<rect") == len(rows)
    assert svg.count("<title>") == len(rows)
    assert "1700" in svg and "1500" in svg


def test_diverging_gap_bar_all_equal_does_not_divide_by_zero():
    svg = charts.diverging_gap_bar([("A", 1500.0), ("B", 1500.0)], anchor=1500.0)
    assert _is_svg(svg)


def test_diverging_gap_bar_empty_is_graceful():
    assert "No data" in charts.diverging_gap_bar([])


# ── dependency-free guarantee ────────────────────────────────────────────────

def test_charts_emit_no_script():
    outputs = [
        charts.donut([("A", 1, "x")]),
        charts.vbar_chart([("a", 1)]),
        charts.diverging_gap_bar([("A", 1600.0)]),
        charts.legend([("A", 1, "x")]),
    ]
    for svg in outputs:
        assert "<script" not in svg.lower()
