"""
Standalone HTML report for a round-robin strategy tournament.

Reuses the self-play report's styling (game/report.py) and stays dependency-free:
a ranking table with Elo-style rating bars, a colour-graded head-to-head win-rate
matrix, and a methodology note. Opens offline as a single file.
"""

import html
from datetime import datetime

from .report import _CSS, _card, _pct
from .tournament import rankings

# Matrix cells: dark-neutral at 50%, toward blue (win) above, orange (loss) below.
_MATRIX_CSS = """
.matrix { border-collapse:collapse; font-size:12px; }
.matrix th, .matrix td { border:1px solid #11141c; padding:5px 7px; text-align:center;
                         white-space:nowrap; }
.matrix th { color:var(--muted); font-weight:500; }
.matrix th.row-head { text-align:right; color:var(--ink); font-weight:500; }
.matrix td.diag { background:#11141c; }
.matrix-wrap { overflow-x:auto; }
.legend { display:flex; align-items:center; gap:8px; color:var(--muted);
          font-size:12px; margin-top:12px; }
.legend .swatch { width:120px; height:12px; border-radius:3px;
  background:linear-gradient(90deg,#c2491f,#2a2e3a,#4f9dff); }
.rank-bar-track { background:#11141c; border-radius:5px; overflow:hidden; height:18px;
                  width:160px; }
.rank-bar-fill { height:100%; background:var(--smart); border-radius:5px; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
"""


# Fallback description for the Random baseline (it carries no `rules` of its own).
_RANDOM_RULES = [
    "Baseline coin-flip play: calls Cambio about 8% of the time; otherwise usually "
    "grabs a discard top worth 3 or less, else draws from the deck.",
    "Swaps the drawn card into a random slot, except a high card (10+) it tends to discard.",
    "Snaps each eligible matching card about 70% of the time; fires every power on a random target.",
]


def _entrant_rules(strat):
    """The human-readable rule list for an entrant's strategy.

    Parameterized profiles carry them on `.profile.rules`, the advanced strategies
    on `.rules`; the Random module has neither, so fall back to a fixed blurb.
    """
    profile = getattr(strat, "profile", None)
    if profile is not None and getattr(profile, "rules", None):
        return list(profile.rules)
    if getattr(strat, "rules", None):
        return list(strat.rules)
    return _RANDOM_RULES


def _strategies_section(result, rows):
    """One bordered box per strategy, in rank order, listing how it plays."""
    blocks = []
    for r in rows:
        e = result.entrants[r["index"]]
        items = "".join(f"<li>{html.escape(x)}</li>" for x in _entrant_rules(e.strat))
        blocks.append(
            '<div class="strategy-box" style="padding-left:14px">'
            f'<div class="strat-name">{r["rank"]}. {html.escape(e.name)} '
            f'<span class="vs">· rated {r["rating"]:.0f}</span></div>'
            f'<ul>{items}</ul></div>'
        )
    return "".join(blocks)


def _lerp(a, b, t):
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def _cell_color(pct):
    """Background rgb() for a head-to-head win share (0–100)."""
    mid = (42, 46, 58)            # --panel-ish neutral
    if pct >= 50:
        return _lerp(mid, (79, 157, 255), (pct - 50) / 50)    # → --smart
    return _lerp(mid, (255, 122, 89), (50 - pct) / 50)        # → --random


def _record(result, row, col):
    """(row_wins, col_wins, ties) for the row entrant vs the col entrant."""
    i, j = (row, col) if row < col else (col, row)
    pr = result.pairs[(i, j)]
    return (pr.a_wins, pr.b_wins, pr.ties) if row == i else (pr.b_wins, pr.a_wins, pr.ties)


def _rankings_table(rows):
    body = []
    ratings = [r["rating"] for r in rows]
    lo, hi = min(ratings), max(ratings)
    span = (hi - lo) or 1.0
    for r in rows:
        fill = 8 + 92 * (r["rating"] - lo) / span     # 8–100% so the floor stays visible
        bar = (f'<div class="rank-bar-track"><div class="rank-bar-fill" '
               f'style="width:{fill:.1f}%"></div></div>')
        body.append(
            f'<tr><td class="num">{r["rank"]}</td>'
            f'<td>{html.escape(r["name"])}</td>'
            f'<td class="num">{r["rating"]:.0f}</td>'
            f'<td>{bar}</td>'
            f'<td class="num">{r["win_pct"]:.1f}%</td>'
            f'<td class="num">{r["wins"]}–{r["losses"]}–{r["ties"]}</td>'
            f'<td class="num">{r["games"]:,}</td></tr>'
        )
    return (
        '<table><thead><tr><th>#</th><th>Strategy</th><th>Rating</th><th></th>'
        '<th>Win%</th><th>W–L–T</th><th>Games</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )


def _matrix_table(result, rows):
    order = [r["index"] for r in rows]          # rank order, best → worst
    k = result.k
    head = '<th class="row-head"></th>' + "".join(
        f'<th title="{html.escape(rows[c]["name"])}">{c + 1}</th>'
        for c in range(len(order))
    )
    body = []
    for r_pos, row in enumerate(order):
        cells = [f'<th class="row-head">{r_pos + 1}. {html.escape(result.entrants[row].name)}</th>']
        for col in order:
            if row == col:
                cells.append('<td class="diag"></td>')
                continue
            rw, cw, ti = _record(result, row, col)
            pct = _pct(rw + 0.5 * ti, k)
            r_, g_, b_ = _cell_color(pct)
            title = f"{result.entrants[row].name} vs {result.entrants[col].name}: {rw}–{cw}–{ti}"
            cells.append(
                f'<td style="background:rgb({r_},{g_},{b_})" title="{html.escape(title)}">'
                f'{pct:.0f}</td>'
            )
        body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="matrix-wrap"><table class="matrix">'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        '<div class="legend"><span>opponent win share for the row strategy</span>'
        '<span class="swatch"></span><span>0% · 50% · 100%</span></div>'
    )


def render_tournament_html(result, config=None):
    config = config or {}
    rows = rankings(result)
    n = len(result.entrants)
    t = result.timing
    anchored = any(e.key == "random" for e in result.entrants)

    cards = "".join([
        _card("Entrants", n),
        _card("Games / pairing", f"{result.k:,}"),
        _card("Total games", f"{result.total_games:,}"),
        _card("Tie rate", f"{_pct(result.total_ties, result.total_games):.1f}%"),
        _card("Avg game length", f"{result.mean_length:.1f}", "turns"),
        _card("Throughput", f"{t['games_per_s']:,.0f}", "games/sec"),
    ])

    anchor_note = ("Random is fixed at 1500 as the calibration floor; every other "
                   "rating reads as points above coin-flip play."
                   if anchored else
                   "Ratings are centered so the field's mean is 1500.")

    methodology = f"""
    <ul>
      <li><b>Format.</b> Every pair of strategies plays {result.k:,} games. Sides are
      balanced — each strategy starts half its games and sits in each physical seat
      half the time — so first-move bias cancels out.</li>
      <li><b>Outcome.</b> Lowest hand sum wins (Cambio caller takes a +5 penalty if it
      isn't lowest). Only win/loss/tie is recorded; <b>margin is ignored</b>. A tie
      counts as half a win to each side.</li>
      <li><b>Rating.</b> A Bradley-Terry model is fit to all pairwise results at once
      (Hunter 2004 MM iteration), then mapped to an Elo-style scale via
      rating = anchor + 400·log<sub>10</sub>(strength ratio). {anchor_note} A small
      symmetric prior keeps every rating finite. A 400-point gap ≈ a 10:1 expected
      win ratio.</li>
    </ul>"""

    cfg = html.escape(
        f"{n} entrants · {result.k:,} games/pairing · {result.total_games:,} games · "
        f"seed={result.seed} · max_turns={result.max_turns} · "
        f"generated {datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cambio Round-Robin Tournament</title><style>{_CSS}{_MATRIX_CSS}</style></head>
<body><div class="wrap">
  <h1>Cambio Round-Robin Tournament</h1>
  <p class="sub">{cfg}</p>

  <div class="cards">{cards}</div>

  <h2>Rankings</h2>
  <div class="panel">{_rankings_table(rows)}</div>

  <h2>How each strategy plays</h2>
  <div class="panel">
    <p class="sub" style="margin:0 0 18px">Every entrant's playbook, in rank order —
    how it draws, swaps, snaps, uses card powers, and decides to call Cambio.</p>
    {_strategies_section(result, rows)}
  </div>

  <h2>Head-to-head win rates</h2>
  <div class="panel">
    <p class="sub" style="margin:0 0 14px">Each cell is the row strategy's win share
    against the column strategy (ties = ½). Columns are numbered in the same rank
    order as the rows; hover a cell for the raw W–L–T.</p>
    {_matrix_table(result, rows)}
  </div>

  <h2>Methodology</h2>
  <div class="panel">{methodology}</div>
</div></body></html>"""


def write_tournament_report(result, config, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_tournament_html(result, config))
    return result
