"""
Auto-generated "interesting results" highlights for the HTML reports.

Pure, deterministic heuristics over the already-computed stats — no HTML, no
randomness — so they can be unit-tested directly and rendered by either report.
Each function returns a list of highlight dicts:

    {"tone": "good|bad|neutral|warn", "icon": "🏆", "title": "...", "text": "..."}

`tone` drives the colour accent in the report; the render layer turns these into
cards. The thresholds below are gathered as named constants so they are easy to
audit and tune.
"""

import math

# ── Tunable thresholds ───────────────────────────────────────────────────────
CEILING_PCT = 75.0          # documented win-rate ceiling vs Random (strong bots converge here)
STRONG_PCT = 72.0           # "near the ceiling" band floor
EDGE_PCT = 60.0             # clearly beats Random
SLIGHT_PCT = 52.0           # slight edge
NOISE_BAND = 2.0            # +/- around 50% treated as indistinguishable
HIGH_TIE = 15.0             # tie rate worth flagging
TIEBREAK_NOTE = 10.0        # card-count tie-break rate worth flagging
CAP_WARN = 1.0              # % of games hitting the turn cap
CALLER_GOOD = 80.0          # Cambio-caller success that reads as well-timed
CALLER_WARN = 50.0          # Cambio-caller success that reads as called-too-early
BIG_MARGIN = 6.0            # lopsided average victory margin (points)
SNAP_GAP = 0.5              # snaps/game asymmetry between seats
STARTER_EDGE = 5.0          # first-move advantage worth calling real (points off 50)
STARTER_NEGLIGIBLE = 2.0    # first-move advantage small enough to dismiss
SEAT_LEAN = 5.0             # gap between moving-first and moving-second win rates
ELO_PER_DECADE = 400.0      # 400 Elo ≈ a 10:1 expected win ratio
CI_Z = 1.959964             # two-sided 95% normal quantile

# STARTER_EDGE / STARTER_NEGLIGIBLE / SEAT_LEAN are point-estimate thresholds and
# sit *below the noise floor* of a default n=500 batch. Measured on 200 runs of
# 500 games with the same strategy on both sides (so seat contributes nothing and
# only turn order can): the first/second gap has a true value of +3.0 pts but a
# per-run SD of 4.5, and the starter win rate a true 51.6% with an SD of 2.3. At
# those thresholds "Leans on moving first" fired on 40.5% of runs — always
# overstating the effect, since it can only fire when noise pushes the estimate
# past 5 — while "Fair start" (52.5%) and "First move matters" (8.0%) fired on
# the same underlying truth, contradicting each other run to run.
#
# So the thresholds below are now applied to a 95% confidence interval rather
# than to the point estimate: a verdict is only printed when the whole interval
# supports it. They remain the fallback when a caller passes rates without the
# underlying counts.


def _pct(num, den):
    return (100.0 * num / den) if den else 0.0


def _wilson_ci(wins, n, z=CI_Z):
    """Wilson 95% CI (percentage points) for a rate; None if counts are absent."""
    if not n:
        return None
    p = wins / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100.0 * (centre - half), 100.0 * (centre + half))


def _diff_ci(w1, n1, w2, n2, z=CI_Z):
    """Wald 95% CI (percentage points) for rate1 - rate2; None if counts absent."""
    if not n1 or not n2:
        return None
    p1, p2 = w1 / n1, w2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    delta = 100.0 * (p1 - p2)
    return (delta - 100.0 * z * se, delta + 100.0 * z * se)


def _games_for(halfwidth, z=CI_Z):
    """Games needed for a rate's 95% half-width to fall under `halfwidth` points."""
    return int(math.ceil((z * 50.0 / halfwidth) ** 2))


def _h(tone, icon, title, text):
    return {"tone": tone, "icon": icon, "title": title, "text": text}


# ── Self-play ────────────────────────────────────────────────────────────────

def self_play_highlights(stats, config):
    """Highlights for a self-play simulation report. Guards sparse data; never raises."""
    config = config or {}
    s = stats
    n = s.get("n", 0)
    out = []
    if not n:
        return [_h("neutral", "📊", "No games", "The batch was empty — nothing to summarise.")]

    label_a = config.get("label_a", "Smart")
    label_b = config.get("label_b", "Random")
    name = config.get("strategy_name", label_a)
    wr = s["smart_winrate"]
    lr = s["random_winrate"]

    # (a) Headline verdict
    if config.get("a_is_random"):
        gap = abs(wr - lr)
        tone = "warn" if gap > 5.0 else "neutral"
        out.append(_h(
            tone, "⚖️", "Baseline sanity check",
            f"Random-vs-random: {label_a} {wr:.1f}% / {label_b} {lr:.1f}% "
            f"(ties {s['tie_rate']:.1f}%). A clean harness should be near-symmetric; "
            f"the {gap:.1f}-pt split is "
            + ("wider than expected — check for seat/turn bias." if gap > 5.0
               else "within noise.")
        ))
    elif wr >= STRONG_PCT:
        out.append(_h(
            "good", "🏆", f"{name} crushes Random",
            f"{wr:.1f}% win rate — right at the documented ~{CEILING_PCT:.0f}% ceiling "
            f"against Random. Strong low-hand play, but Random can no longer separate it "
            f"from other strong bots; rank it in the tournament instead."
        ))
    elif wr >= EDGE_PCT:
        out.append(_h(
            "good", "🏆", f"{name} clearly beats Random",
            f"{wr:.1f}% win rate — a solid edge, but below the ~{CEILING_PCT:.0f}% "
            f"ceiling the strongest bots reach. Room to tighten the heuristics."
        ))
    elif wr >= SLIGHT_PCT:
        out.append(_h(
            "neutral", "📊", f"{name} edges out Random",
            f"{wr:.1f}% win rate — only a slight advantage over coin-flip play."
        ))
    elif wr >= 50.0 - NOISE_BAND:
        out.append(_h(
            "warn", "⚠️", f"{name} ≈ Random",
            f"{wr:.1f}% win rate is inside the noise band around 50% — the strategy "
            f"adds no measurable edge over random play."
        ))
    else:
        out.append(_h(
            "bad", "🛑", f"{name} loses to Random",
            f"{wr:.1f}% win rate — worse than coin-flip. Likely a bug or an inverted "
            f"heuristic; lowest hand sum should win."
        ))

    # (b) Notable outliers / extremes
    if s["tie_rate"] >= HIGH_TIE:
        out.append(_h(
            "warn", "🤝", "Lots of ties",
            f"{s['tie_rate']:.1f}% of games tie — scores cluster tightly, so draws "
            f"matter more than margins here."
        ))
    if s["tiebreak_rate"] >= TIEBREAK_NOTE:
        out.append(_h(
            "neutral", "🃏", "Decided on cards",
            f"{s['tiebreak_rate']:.1f}% of decisive games came down to holding more "
            f"cards at an equal score, not to a lower score."
        ))
    cap_pct = _pct(s["endings"].get("capped", 0), n)
    if cap_pct >= CAP_WARN:
        out.append(_h(
            "warn", "⏱️", "Games hitting the turn cap",
            f"{cap_pct:.1f}% of games ran to max_turns without ending — a possible "
            f"stall; check the cap or the strategy's end-game."
        ))
    if s["cambio_games"]:
        cs = s["cambio_success"]
        if cs >= CALLER_GOOD:
            out.append(_h(
                "good", "🎯", "Well-timed Cambio calls",
                f"Callers win {cs:.1f}% of the games they end — the call is being saved "
                f"for a genuine lead."
            ))
        elif cs <= CALLER_WARN and s["cambio_games"] >= 0.05 * n:
            out.append(_h(
                "warn", "🎯", "Cambio called too early",
                f"Callers win only {cs:.1f}% of the games they end — the +5 penalty for "
                f"not being lowest is biting."
            ))
    if s["avg_margin"] >= BIG_MARGIN:
        out.append(_h(
            "neutral", "💪", "Lopsided wins",
            f"Average victory margin is {s['avg_margin']:.1f} points — games are decided "
            f"decisively rather than on the wire."
        ))
    snap_gap = s["avg_snaps_smart"] - s["avg_snaps_random"]
    if abs(snap_gap) >= SNAP_GAP:
        leader, follower = (label_a, label_b) if snap_gap > 0 else (label_b, label_a)
        out.append(_h(
            "neutral", "✋", "Snap asymmetry",
            f"{leader} snaps {abs(snap_gap):.2f} more times per game than {follower} "
            f"({s['avg_snaps_smart']:.2f} vs {s['avg_snaps_random']:.2f})."
        ))
    if s["max_length"] >= 2 * s["avg_length"] and s["avg_length"] > 0:
        out.append(_h(
            "neutral", "📏", "Wide game-length spread",
            f"Games run {s['min_length']}–{s['max_length']} turns (avg {s['avg_length']:.1f}); "
            f"the longest is over twice the average."
        ))
    # Most-used special ability, if any fired
    specials = s.get("smart_specials") or {}
    _SPECIAL_NAMES = {
        "peek_own": "Peek own (7/8)", "peek_opponent": "Peek opponent (9/10)",
        "blind_switch": "Blind switch (J/Q)", "looking_switch": "Looking switch (K)",
    }
    if specials and sum(specials.values()) > 0:
        key = max(specials, key=lambda k: specials[k])
        per_game = specials[key] / n
        out.append(_h(
            "neutral", "✨", "Favourite special",
            f"{name}'s most-used power is {_SPECIAL_NAMES.get(key, key)} "
            f"({per_game:.2f}/game)."
        ))

    # (c) First-move / fairness
    if config.get("show_first_move", True):
        starter = s["starter_winrate_decisive"]
        delta = starter - 50.0
        ci = _wilson_ci(s.get("starter_wins_decisive"), s.get("decisive_n"))
        if ci is None:                      # no counts — legacy point-estimate rule
            real, negligible, band = abs(delta) >= STARTER_EDGE, abs(delta) < STARTER_NEGLIGIBLE, ""
        else:
            lo, hi = ci
            real = lo > 50.0 + STARTER_NEGLIGIBLE or hi < 50.0 - STARTER_NEGLIGIBLE
            negligible = 50.0 - STARTER_NEGLIGIBLE < lo and hi < 50.0 + STARTER_NEGLIGIBLE
            band = f" (95% CI {lo:.1f}–{hi:.1f}%)"
        if real:
            out.append(_h(
                "warn", "🔀", "First move matters",
                f"The starting seat wins {starter:.1f}% of decisive games{band} "
                f"({delta:+.1f} pts vs even) — a real first-move advantage baked into "
                f"these numbers."
            ))
        elif negligible:
            out.append(_h(
                "good", "⚖️", "Fair start",
                f"The starting seat wins {starter:.1f}% of decisive games{band} — "
                f"first-move advantage is negligible, so the result reflects strategy, "
                f"not seat."
            ))
        elif ci is not None:                # silent on the legacy path, which has no interval
            out.append(_h(
                "neutral", "🎲", "First move: not enough games",
                f"The starting seat wins {starter:.1f}% of decisive games{band} — that "
                f"interval covers both 'negligible' and 'real', so this batch can't "
                f"settle it. Pinning it to ±{STARTER_NEGLIGIBLE:.0f} pts needs about "
                f"{_games_for(STARTER_NEGLIGIBLE):,} decisive games."
            ))

        first, second = s["smart_first_winrate"], s["smart_second_winrate"]
        seat_gap = first - second
        gap_ci = _diff_ci(s.get("smart_first_wins"), s.get("smart_first_n"),
                          s.get("smart_second_wins"), s.get("smart_second_n"))
        if gap_ci is None:
            lean, gap_band = abs(seat_gap) >= SEAT_LEAN, ""
        else:
            glo, ghi = gap_ci
            lean = glo > 0.0 or ghi < 0.0   # interval excludes zero
            gap_band = f" (95% CI {glo:+.1f} to {ghi:+.1f})"
        if lean:
            out.append(_h(
                "neutral", "🔀", "Leans on moving first",
                f"{name} wins {first:.1f}% moving first vs {second:.1f}% moving second "
                f"— a {seat_gap:+.1f}-pt swing{gap_band} from turn order alone."
            ))

    return out


# ── Tournament ───────────────────────────────────────────────────────────────

def _share(pr, of_index):
    """Win share (ties = ½), as a percentage, of `of_index` in this PairResult."""
    k = pr.a_wins + pr.b_wins + pr.ties
    if not k:
        return 0.0
    if of_index == pr.i:
        return 100.0 * (pr.a_wins + 0.5 * pr.ties) / k
    return 100.0 * (pr.b_wins + 0.5 * pr.ties) / k


def tournament_highlights(result, rows):
    """Highlights for a round-robin tournament report. `rows` = rankings(result)."""
    out = []
    n = len(rows)
    if n < 2:
        return [_h("neutral", "📊", "Not enough entrants",
                   "A ranking needs at least two strategies.")]

    best, worst = rows[0], rows[-1]
    anchored = any(r["key"] == "random" for r in rows)

    # (a) Headline verdict
    text = f"{best['name']} tops the field at {best['rating']:.0f} Elo " \
           f"({best['win_pct']:.1f}% wins across {best['games']:,} games)."
    if anchored:
        rnd = next(r for r in rows if r["key"] == "random")
        text += f" Random anchors the scale at 1500 (rank {rnd['rank']}/{n})."
    out.append(_h("good", "🏆", "Champion", text))

    # (b) Worst
    out.append(_h(
        "bad", "🔻", "Cellar dweller",
        f"{worst['name']} sits last at {worst['rating']:.0f} Elo "
        f"({worst['win_pct']:.1f}% wins)."
    ))

    # (c) Skill spread, expressed as an expected win ratio (400 Elo ≈ 10:1)
    spread = best["rating"] - worst["rating"]
    ratio = 10 ** (spread / ELO_PER_DECADE)
    spread_tone = "warn" if spread < 250 else "neutral"
    out.append(_h(
        spread_tone, "📏", "Skill spread",
        f"{spread:.0f} Elo separates first from last (~{ratio:.0f}:1 expected wins). "
        + ("A narrow ladder — the bots are closely matched, hinting at a low skill ceiling."
           if spread < 250 else
           "A wide ladder — clear separation between the strategies.")
    ))

    rank_by_index = {r["index"]: r["rank"] for r in rows}
    name_by_index = {r["index"]: r["name"] for r in rows}

    # (d) Most dominant matchup
    dom = None  # (share, winner_idx, loser_idx, pr)
    for (i, j), pr in result.pairs.items():
        si, sj = _share(pr, i), _share(pr, j)
        share, win_i, lose_i = (si, i, j) if si >= sj else (sj, j, i)
        if dom is None or share > dom[0]:
            dom = (share, win_i, lose_i, pr)
    if dom:
        share, wi, li, pr = dom
        rw, rl, ti = (pr.a_wins, pr.b_wins, pr.ties) if wi == pr.i else (pr.b_wins, pr.a_wins, pr.ties)
        tone = "warn" if share >= 95.0 else "neutral"
        out.append(_h(
            tone, "💥", "Most dominant matchup",
            f"{name_by_index[wi]} owns {name_by_index[li]}, winning {share:.0f}% "
            f"of their games ({rw}–{rl}–{ti})."
        ))

    # (e) Biggest upset: a lower-ranked entrant beating a higher-ranked one head-to-head
    if n >= 3:
        upset = None  # (rank_gap, share, low_idx, high_idx)
        for (i, j), pr in result.pairs.items():
            ri, rj = rank_by_index[i], rank_by_index[j]
            low, high = (i, j) if ri > rj else (j, i)   # higher rank number = weaker
            share_low = _share(pr, low)
            if share_low > 50.0:
                gap = abs(rank_by_index[low] - rank_by_index[high])
                key = (gap, share_low)
                if upset is None or key > upset[:2]:
                    upset = (gap, share_low, low, high)
        if upset:
            gap, share_low, low, high = upset
            out.append(_h(
                "neutral", "😮", "Biggest upset",
                f"{name_by_index[low]} (rank {rank_by_index[low]}) takes the head-to-head "
                f"from {name_by_index[high]} (rank {rank_by_index[high]}) at "
                f"{share_low:.0f}% — a {gap}-rung upset despite ranking lower overall."
            ))
        else:
            out.append(_h(
                "neutral", "✅", "Consistent ranking",
                "No upsets — every head-to-head agrees with the overall ranking order."
            ))

    return out
