"""
Inline-SVG chart primitives for the HTML reports.

Dependency-free and JavaScript-free: every function returns a self-contained
`<svg>` string that renders offline in any browser. Charts reference the report's
CSS colour variables (--smart, --random, --tie, --accent, --muted) so the palette
stays centralised in game/report.py's stylesheet. Native `<title>` elements give
hover tooltips without a line of script.
"""

import html
import math

# Shared geometry / palette anchors (kept in sync with report.py's _CSS).
_TRACK = "#11141c"      # bar/ring background
_GRID = "#2a2e3a"       # axis + gridline colour


def _esc(s):
    return html.escape(str(s))


def _fmt_int(n):
    return f"{n:,}"


def _nice_max(value, ticks=4):
    """Round `value` up to a clean axis maximum (1·, 2·, 2.5·, 5·, 10· a power
    of ten) so y-tick labels land on round numbers."""
    if value <= 0:
        return ticks  # so an all-zero chart still draws a labelled axis
    raw = value / ticks
    mag = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 2.5, 5, 10):
        if step * mag >= raw:
            return step * mag * ticks
    return 10 * mag * ticks


def _empty(width, height, msg="No data"):
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'class="chart-svg" role="img" aria-label="{_esc(msg)}">'
        f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
        f'dominant-baseline="central" class="chart-empty">{_esc(msg)}</text></svg>'
    )


# ── Donut ──────────────────────────────────────────────────────────────────

def donut(segments, *, size=170, thickness=26, center_label=None, center_sub=None):
    """A ring chart of proportions.

    segments: list of (label, value, color). Values are absolute (counts or
    percentages); zero-value segments are skipped. `center_label`/`center_sub`
    render stacked text in the hole (e.g. a headline percentage and its caption).
    """
    total = sum(max(0.0, v) for _, v, _ in segments)
    if total <= 0:
        return _empty(size, size)

    cx = cy = size / 2
    r = (size - thickness) / 2
    parts = [
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'class="chart-svg" role="img">',
        f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{_TRACK}" '
        f'stroke-width="{thickness}"/>',
        f'<g transform="rotate(-90 {cx} {cy})">',
    ]
    cumulative = 0.0  # in pathLength-100 units, measured clockwise from 12 o'clock
    for label, value, color in segments:
        if value <= 0:
            continue
        frac = 100.0 * value / total
        pct_of_total = value / total * 100.0
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{color}" '
            f'stroke-width="{thickness}" pathLength="100" '
            f'stroke-dasharray="{frac:.3f} {100 - frac:.3f}" '
            f'stroke-dashoffset="{-cumulative:.3f}">'
            f'<title>{_esc(label)}: {_fmt_int(round(value))} ({pct_of_total:.1f}%)</title>'
            f'</circle>'
        )
        cumulative += frac
    parts.append('</g>')

    if center_label is not None:
        parts.append(
            f'<text x="{cx}" y="{cy - (5 if center_sub else 0)}" text-anchor="middle" '
            f'dominant-baseline="central" class="donut-center">{_esc(center_label)}</text>'
        )
    if center_sub is not None:
        parts.append(
            f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" '
            f'dominant-baseline="central" class="donut-sub">{_esc(center_sub)}</text>'
        )
    parts.append('</svg>')
    return "".join(parts)


def legend(segments):
    """A small flex legend matching `donut` segments: list of (label, value, color)."""
    items = "".join(
        f'<span class="lg-item"><span class="lg-swatch" style="background:{color}"></span>'
        f'{_esc(label)}</span>'
        for label, _, color in segments
    )
    return f'<div class="chart-legend">{items}</div>'


# ── Vertical bar chart (with axis) ───────────────────────────────────────────

def vbar_chart(bins, *, color="var(--smart)", width=720, height=240,
               pad_left=42, pad_bottom=34, pad_top=18, pad_right=8, y_ticks=4):
    """Vertical bars with a labelled y-axis and x-axis tick labels.

    bins: list of (label, count). Used for the game-length distribution.
    """
    if not bins:
        return _empty(width, height)

    counts = [c for _, c in bins]
    top = _nice_max(max(counts) if counts else 0, y_ticks)
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    base_y = pad_top + plot_h
    n = len(bins)
    slot = plot_w / n
    bar_w = slot * 0.72
    gap = (slot - bar_w) / 2

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'class="chart-svg" role="img"><g class="axis">',
    ]
    # y gridlines + tick labels
    for t in range(y_ticks + 1):
        val = top * t / y_ticks
        y = base_y - plot_h * t / y_ticks
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}"/>'
            f'<text x="{pad_left - 6}" y="{y:.1f}" text-anchor="end" '
            f'dominant-baseline="central" class="tick">{val:,.0f}</text>'
        )
    parts.append('</g>')

    # bars + x labels — thin x labels when crowded so they stay legible
    label_every = max(1, math.ceil(n / 16))
    for i, (label, count) in enumerate(bins):
        x = pad_left + i * slot + gap
        h = (plot_h * count / top) if top else 0
        y = base_y - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'rx="2" fill="{color}"><title>{_esc(label)}: {_fmt_int(count)}</title></rect>'
        )
        if i % label_every == 0:
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{base_y + 14:.0f}" text-anchor="middle" '
                f'class="tick">{_esc(label)}</text>'
            )
    parts.append('</svg>')
    return "".join(parts)


# ── Diverging rating chart (tournament) ──────────────────────────────────────

def diverging_gap_bar(rows, *, anchor=1500.0, width=720, row_height=26,
                      pad_left=150, pad_right=54, pad_top=10, pad_bottom=10):
    """Ratings as bars diverging from an `anchor` (default 1500 = coin-flip).

    rows: list of (name, rating) or (name, rating, (lo, hi)). Bars extend right of
    the anchor (above it, --smart) or left (below it, --random); useful for reading
    the skill spread. When a row carries a `(lo, hi)` confidence band, a thin
    capped whisker is drawn over its bar so overlapping intervals are visible.
    """
    if not rows:
        return _empty(width, 80)

    rows = [(r[0], r[1], r[2] if len(r) > 2 else None) for r in rows]
    # The axis must span the bars *and* any whisker ends, or whiskers would clip.
    extents = []
    for _, rating, band in rows:
        extents.append(abs(rating - anchor))
        if band is not None:
            extents += [abs(band[0] - anchor), abs(band[1] - anchor)]
    max_dev = max(extents, default=0) or 1.0
    plot_w = width - pad_left - pad_right
    half = plot_w / 2
    zero_x = pad_left + half
    height = pad_top + pad_bottom + row_height * len(rows)

    def _x(value):
        return zero_x + half * (value - anchor) / max_dev

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'class="chart-svg" role="img">',
        # anchor line
        f'<line x1="{zero_x:.1f}" y1="{pad_top}" x2="{zero_x:.1f}" y2="{height - pad_bottom}" '
        f'class="axis-anchor"/>',
        f'<text x="{zero_x:.1f}" y="{pad_top - 2}" text-anchor="middle" '
        f'class="tick">{anchor:.0f}</text>',
    ]
    bar_h = row_height * 0.6
    for i, (name, rating, band) in enumerate(rows):
        cy = pad_top + i * row_height + row_height / 2
        dev = rating - anchor
        length = half * abs(dev) / max_dev
        color = "var(--smart)" if dev >= 0 else "var(--random)"
        x = zero_x if dev >= 0 else zero_x - length
        band_title = ""
        if band is not None:
            band_title = f" · 95% CI [{band[0]:.0f}, {band[1]:.0f}]"
        parts.append(
            f'<text x="{pad_left - 8}" y="{cy:.1f}" text-anchor="end" '
            f'dominant-baseline="central" class="tick name">{_esc(name)}</text>'
            f'<rect x="{x:.1f}" y="{cy - bar_h / 2:.1f}" width="{length:.1f}" '
            f'height="{bar_h:.1f}" rx="3" fill="{color}">'
            f'<title>{_esc(name)}: {rating:.0f} ({dev:+.0f} vs {anchor:.0f}){band_title}</title></rect>'
        )
        if band is not None:
            lo_x, hi_x = _x(band[0]), _x(band[1])
            cap = bar_h * 0.4
            parts.append(
                f'<g class="ci-whisker" stroke="var(--ink)" stroke-width="1.3" '
                f'opacity="0.85">'
                f'<line x1="{lo_x:.1f}" y1="{cy:.1f}" x2="{hi_x:.1f}" y2="{cy:.1f}"/>'
                f'<line x1="{lo_x:.1f}" y1="{cy - cap:.1f}" x2="{lo_x:.1f}" y2="{cy + cap:.1f}"/>'
                f'<line x1="{hi_x:.1f}" y1="{cy - cap:.1f}" x2="{hi_x:.1f}" y2="{cy + cap:.1f}"/>'
                f'</g>'
            )
        parts.append(
            f'<text x="{width - pad_right + 6}" y="{cy:.1f}" text-anchor="start" '
            f'dominant-baseline="central" class="tick">{rating:.0f}</text>'
        )
    parts.append('</svg>')
    return "".join(parts)
