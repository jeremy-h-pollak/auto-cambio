"""
Standalone HTML analysis report for a batch of simulated Cambio games.

No third-party dependencies: charts are plain HTML/CSS bars, and the whole
report is a single self-contained file that opens offline.
"""

import html
from collections import Counter
from datetime import datetime


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _pct(num, den):
    return (100.0 * num / den) if den else 0.0


def _seat_score(rec, seat):
    return rec.player_score if seat == "player" else rec.computer_score


def _histogram(values, max_bins=24):
    """Return (bins, bin_width): list of (label, count) covering the value range."""
    if not values:
        return [], 1
    lo, hi = min(values), max(values)
    span = hi - lo
    width = max(1, -(-span // max_bins)) if span else 1  # ceil(span/max_bins)
    counts = Counter()
    for v in values:
        start = lo + ((v - lo) // width) * width
        counts[start] += 1
    bins = []
    start = lo
    while start <= hi:
        label = str(start) if width == 1 else f"{start}–{start + width - 1}"
        bins.append((label, counts.get(start, 0)))
        start += width
    return bins, width


def compute_stats(records, timing):
    n = len(records)
    decisive = [r for r in records if not r.is_tie]

    smart_wins = sum(1 for r in records if r.smart_won)
    random_wins = sum(1 for r in records if r.random_won)
    ties = sum(1 for r in records if r.is_tie)
    starter_wins = sum(1 for r in records if r.starter_won)

    smart_first = [r for r in records if r.smart_seat == r.starting_seat]
    smart_second = [r for r in records if r.smart_seat != r.starting_seat]

    cambio_games = [r for r in records if r.ending == "cambio"]
    caller_wins = sum(1 for r in cambio_games if r.winner_seat == r.cambio_caller)

    lengths = [r.length for r in records]
    hist, hist_width = _histogram(lengths)

    return {
        "n": n,
        "smart_wins": smart_wins,
        "random_wins": random_wins,
        "ties": ties,
        "smart_winrate": _pct(smart_wins, n),
        "random_winrate": _pct(random_wins, n),
        "tie_rate": _pct(ties, n),
        "starter_winrate": _pct(starter_wins, n),
        "starter_winrate_decisive": _pct(
            sum(1 for r in decisive if r.starter_won), len(decisive)
        ),
        "smart_first_winrate": _pct(sum(1 for r in smart_first if r.smart_won), len(smart_first)),
        "smart_second_winrate": _pct(sum(1 for r in smart_second if r.smart_won), len(smart_second)),
        "avg_smart_score": _mean(_seat_score(r, r.smart_seat) for r in records),
        "avg_random_score": _mean(
            _seat_score(r, "computer" if r.smart_seat == "player" else "player") for r in records
        ),
        "avg_margin": _mean(abs(r.player_score - r.computer_score) for r in records),
        "avg_length": _mean(lengths),
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "endings": Counter(r.ending for r in records),
        "cambio_games": len(cambio_games),
        "cambio_success": _pct(caller_wins, len(cambio_games)),
        "avg_snaps_smart": _mean(r.snaps[r.smart_seat] for r in records),
        "avg_snaps_random": _mean(r.snaps["computer" if r.smart_seat == "player" else "player"] for r in records),
        "length_hist": hist,
        "length_hist_width": hist_width,
        "timing": timing,
    }


# ── HTML rendering ─────────────────────────────────────────────────────────

_CSS = """
:root { --bg:#0f1117; --panel:#1a1d27; --ink:#e6e8ee; --muted:#9aa0ad;
        --smart:#4f9dff; --random:#ff7a59; --tie:#9aa0ad; --accent:#48d597; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:980px; margin:0 auto; padding:32px 24px 64px; }
h1 { font-size:26px; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 28px; }
h2 { font-size:18px; margin:34px 0 14px; border-bottom:1px solid #2a2e3a; padding-bottom:8px; }
.strategy-box { border-left:4px solid var(--smart); margin:0 0 26px; }
.strategy-box .strat-name { font-size:18px; font-weight:600; margin-bottom:4px; }
.strategy-box .strat-name .vs { color:var(--muted); font-weight:400; font-size:14px; }
.strategy-box ul { margin:10px 0 2px 20px; display:flex; flex-direction:column; gap:7px; }
.strategy-box li { color:#cdd3df; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }
.card { background:var(--panel); border:1px solid #262a36; border-radius:12px; padding:16px 18px; }
.card .label { color:var(--muted); font-size:13px; }
.card .value { font-size:28px; font-weight:600; margin-top:4px; }
.card .value small { font-size:14px; color:var(--muted); font-weight:400; }
.panel { background:var(--panel); border:1px solid #262a36; border-radius:12px; padding:18px 20px; }
.bar-row { display:flex; align-items:center; gap:12px; margin:8px 0; }
.bar-label { width:160px; color:var(--muted); font-size:13px; text-align:right; }
.bar-track { flex:1; background:#11141c; border-radius:6px; overflow:hidden; height:26px; }
.bar-fill { height:100%; display:flex; align-items:center; justify-content:flex-end;
            padding:0 8px; color:#08111d; font-size:12px; font-weight:600; white-space:nowrap; }
.hist { display:flex; align-items:flex-end; gap:3px; height:200px; padding-top:18px; }
.hist-col { flex:1; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; }
.hist-bar { width:100%; background:var(--smart); border-radius:4px 4px 0 0; position:relative; min-height:1px; }
.hist-bar span { position:absolute; top:-16px; left:50%; transform:translateX(-50%);
                 font-size:10px; color:var(--muted); }
.hist-x { display:flex; gap:3px; margin-top:6px; }
.hist-x div { flex:1; text-align:center; font-size:10px; color:var(--muted);
              white-space:nowrap; overflow:hidden; }
table { width:100%; border-collapse:collapse; margin-top:6px; }
td,th { text-align:left; padding:6px 8px; border-bottom:1px solid #262a36; font-size:14px; }
th { color:var(--muted); font-weight:500; }
"""


def _bar(label, value_pct, color, text=None):
    text = text if text is not None else f"{value_pct:.1f}%"
    width = max(0.0, min(100.0, value_pct))
    return (
        f'<div class="bar-row"><div class="bar-label">{html.escape(label)}</div>'
        f'<div class="bar-track"><div class="bar-fill" '
        f'style="width:{width:.2f}%;background:{color}">{html.escape(text)}</div></div></div>'
    )


def _hist_html(bins):
    if not bins:
        return "<p>No data.</p>"
    top = max(c for _, c in bins) or 1
    cols = "".join(
        f'<div class="hist-col"><div class="hist-bar" style="height:{(c/top*100):.1f}%">'
        f'<span>{c}</span></div></div>'
        for _, c in bins
    )
    xs = "".join(f"<div>{html.escape(lbl)}</div>" for lbl, _ in bins)
    return f'<div class="hist">{cols}</div><div class="hist-x">{xs}</div>'


def _card(label, value, sub=""):
    sub = f" <small>{html.escape(sub)}</small>" if sub else ""
    return (f'<div class="card"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(str(value))}{sub}</div></div>')


def render_html(stats, config):
    s = stats
    t = s["timing"]
    end = s["endings"]
    n = s["n"]

    cards = "".join([
        _card("Games", f"{n:,}"),
        _card("Smart win rate", f"{s['smart_winrate']:.1f}%"),
        _card("Random win rate", f"{s['random_winrate']:.1f}%"),
        _card("Tie rate", f"{s['tie_rate']:.1f}%"),
        _card("Starter win rate", f"{s['starter_winrate']:.1f}%"),
        _card("Throughput", f"{t['games_per_s']:,.0f}", "games/sec"),
    ])

    winrates = (
        _bar("Smart", s["smart_winrate"], "var(--smart)") +
        _bar("Random", s["random_winrate"], "var(--random)") +
        _bar("Tie", s["tie_rate"], "var(--tie)")
    )

    firstmove = (
        _bar("Smart moves first", s["smart_first_winrate"], "var(--smart)") +
        _bar("Smart moves second", s["smart_second_winrate"], "var(--smart)") +
        _bar("Starter wins (all)", s["starter_winrate"], "var(--accent)") +
        _bar("Starter wins (decisive only)", s["starter_winrate_decisive"], "var(--accent)")
    )

    endings = "".join(
        _bar(name.capitalize(), _pct(end.get(name, 0), n), color,
             f"{end.get(name, 0)} ({_pct(end.get(name, 0), n):.1f}%)")
        for name, color in (("cambio", "var(--smart)"), ("empty", "var(--accent)"), ("capped", "var(--random)"))
    )

    runtime_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>" for k, v in [
            ("Total wall time", f"{t['total_s']:.2f} s"),
            ("Average per game", f"{t['per_game_ms']:.2f} ms"),
            ("Throughput", f"{t['games_per_s']:,.0f} games/sec"),
        ]
    )

    misc_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>" for k, v in [
            ("Avg smart final score", f"{s['avg_smart_score']:.2f}"),
            ("Avg random final score", f"{s['avg_random_score']:.2f}"),
            ("Avg victory margin", f"{s['avg_margin']:.2f}"),
            ("Avg game length", f"{s['avg_length']:.1f} turns ({s['min_length']}–{s['max_length']})"),
            ("Games ended by Cambio call", f"{s['cambio_games']:,}"),
            ("Cambio-caller success rate", f"{s['cambio_success']:.1f}%"),
            ("Avg snaps/game — smart", f"{s['avg_snaps_smart']:.2f}"),
            ("Avg snaps/game — random", f"{s['avg_snaps_random']:.2f}"),
        ]
    )

    strategy_name = config.get("strategy_name", "Smart AI")
    strategy_rules = config.get("strategy_rules", [])
    rules_html = "".join(f"<li>{html.escape(r)}</li>" for r in strategy_rules)
    strategy_box = (
        f'<div class="panel strategy-box">'
        f'<div class="strat-name">Strategy under test: {html.escape(strategy_name)} '
        f'<span class="vs">— vs Random AI</span></div>'
        f'<ul>{rules_html}</ul></div>'
    )

    cfg = html.escape(
        f"{n:,} games · seed={config.get('seed')} · "
        f"{strategy_name} vs Random · max_turns={config.get('max_turns')} · "
        f"generated {datetime.now():%Y-%m-%d %H:%M:%S}"
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cambio Report — {html.escape(strategy_name)}</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Cambio Self-Play Report</h1>
  <p class="sub">{cfg}</p>

  {strategy_box}

  <div class="cards">{cards}</div>

  <h2>Win rates &mdash; Smart vs Random</h2>
  <div class="panel">{winrates}</div>

  <h2>First-move advantage</h2>
  <div class="panel">{firstmove}
    <p class="sub" style="margin:12px 0 0">Comparing Smart's win rate when it moves first vs second
    isolates the starting-player edge from the strategy edge.</p>
  </div>

  <h2>Game-length distribution (turns)</h2>
  <div class="panel">{_hist_html(s['length_hist'])}</div>

  <h2>How games end</h2>
  <div class="panel">{endings}</div>

  <h2>Run-time</h2>
  <div class="panel"><table>{runtime_rows}</table></div>

  <h2>Other statistics</h2>
  <div class="panel"><table>{misc_rows}</table></div>
</div></body></html>"""


def write_report(records, timing, config, path):
    stats = compute_stats(records, timing)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(stats, config))
    return stats
