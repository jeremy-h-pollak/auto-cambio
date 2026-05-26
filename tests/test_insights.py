"""Unit tests for the auto-generated highlights engine (game/insights.py)."""

from collections import Counter

from game.insights import self_play_highlights, tournament_highlights


# ── helpers ───────────────────────────────────────────────────────────────────

def _stats(**over):
    """A full self-play stats dict with neutral defaults, overridable per test."""
    base = {
        "n": 1000,
        "smart_winrate": 55.0, "random_winrate": 42.0, "tie_rate": 3.0,
        "tiebreak_rate": 1.0,
        "endings": Counter({"cambio": 980, "empty": 20, "capped": 0}),
        "cambio_games": 980, "cambio_success": 60.0,
        "avg_margin": 3.0,
        "avg_snaps_smart": 1.0, "avg_snaps_random": 1.0,
        "avg_length": 14.0, "min_length": 4, "max_length": 24,
        "smart_specials": Counter(),
        "starter_winrate_decisive": 50.5,
        "smart_first_winrate": 56.0, "smart_second_winrate": 54.0,
    }
    base.update(over)
    return base


def _titles(items):
    return [it["title"] for it in items]


def _verdict(items):
    """The first item is always the headline verdict."""
    return items[0]


# ── self-play: headline verdict buckets ──────────────────────────────────────

def test_verdict_near_ceiling_is_good():
    v = _verdict(self_play_highlights(_stats(smart_winrate=75.0), {"strategy_name": "X"}))
    assert v["tone"] == "good"
    assert "ceiling" in v["text"]


def test_verdict_indistinguishable_from_random_warns():
    v = _verdict(self_play_highlights(_stats(smart_winrate=50.0, random_winrate=47.0), {}))
    assert v["tone"] == "warn"


def test_verdict_losing_to_random_is_bad():
    v = _verdict(self_play_highlights(_stats(smart_winrate=40.0, random_winrate=57.0), {}))
    assert v["tone"] == "bad"


def test_verdict_clear_edge_is_good():
    v = _verdict(self_play_highlights(_stats(smart_winrate=65.0), {"strategy_name": "X"}))
    assert v["tone"] == "good"
    assert "ceiling" in v["text"]  # references the gap to the ceiling


def test_baseline_branch_flags_asymmetry():
    items = self_play_highlights(
        _stats(smart_winrate=58.0, random_winrate=39.0),
        {"a_is_random": True, "label_a": "Random A", "label_b": "Random B"},
    )
    v = _verdict(items)
    assert v["tone"] == "warn"  # 19-pt split on a baseline is suspicious
    assert "Baseline" in v["title"]


def test_balanced_baseline_is_neutral():
    items = self_play_highlights(
        _stats(smart_winrate=49.0, random_winrate=48.0), {"a_is_random": True})
    assert _verdict(items)["tone"] == "neutral"


# ── self-play: outliers fire only past their thresholds ──────────────────────

def test_high_tie_rate_flagged():
    items = self_play_highlights(_stats(tie_rate=20.0), {})
    assert any("ties" in t.lower() for t in _titles(items))


def test_capped_games_flagged():
    items = self_play_highlights(
        _stats(endings=Counter({"cambio": 900, "empty": 50, "capped": 50})), {})
    assert any("cap" in t.lower() for t in _titles(items))


def test_early_cambio_warns():
    items = self_play_highlights(_stats(cambio_success=45.0), {})
    early = [it for it in items if "Cambio" in it["title"]]
    assert early and early[0]["tone"] == "warn"


def test_most_used_special_reported():
    items = self_play_highlights(
        _stats(smart_specials=Counter({"peek_own": 10, "looking_switch": 40})),
        {"strategy_name": "X"})
    fav = [it for it in items if it["title"] == "Favourite special"]
    assert fav and "Looking switch" in fav[0]["text"]


def test_no_specials_no_favourite_highlight():
    items = self_play_highlights(_stats(smart_specials=Counter()), {})
    assert not any(it["title"] == "Favourite special" for it in items)


# ── self-play: first-move / fairness ─────────────────────────────────────────

def test_fair_start_when_starter_near_even():
    items = self_play_highlights(_stats(starter_winrate_decisive=50.5), {})
    assert any(it["title"] == "Fair start" for it in items)


def test_real_first_move_advantage_flagged():
    items = self_play_highlights(_stats(starter_winrate_decisive=58.0), {})
    fm = [it for it in items if it["title"] == "First move matters"]
    assert fm and fm[0]["tone"] == "warn"


def test_first_move_suppressed_when_disabled():
    items = self_play_highlights(
        _stats(starter_winrate_decisive=50.5), {"show_first_move": False})
    assert not any(it["title"] in ("Fair start", "First move matters") for it in items)


# ── self-play: guards ────────────────────────────────────────────────────────

def test_empty_batch_returns_one_neutral_item():
    items = self_play_highlights(_stats(n=0), {})
    assert len(items) == 1 and items[0]["tone"] == "neutral"


# ── tournament ───────────────────────────────────────────────────────────────

class _Pair:
    def __init__(self, i, j, a_wins, b_wins, ties):
        self.i, self.j = i, j
        self.a_wins, self.b_wins, self.ties = a_wins, b_wins, ties


class _Result:
    def __init__(self, pairs):
        self.pairs = pairs


def _rows(specs):
    """specs: list of (index, key, name, rating, win_pct). Sorted+ranked by rating."""
    rows = [{"index": i, "key": k, "name": nm, "rating": r, "win_pct": wp,
             "games": 20, "wins": 0, "losses": 0, "ties": 0} for i, k, nm, r, wp in specs]
    rows.sort(key=lambda x: x["rating"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def _scenario():
    # 0 strongest, 2 weakest by rating; but 2 upsets 0 head-to-head.
    rows = _rows([(0, "a", "Alpha", 1700.0, 70.0),
                  (1, "b", "Beta", 1600.0, 55.0),
                  (2, "c", "Gamma", 1500.0, 40.0)])
    pairs = {
        (0, 1): _Pair(0, 1, 8, 2, 0),   # Alpha dominates Beta 80%
        (0, 2): _Pair(0, 2, 3, 7, 0),   # Gamma upsets Alpha 70%
        (1, 2): _Pair(1, 2, 6, 4, 0),   # Beta beats Gamma 60%
    }
    return _Result(pairs), rows


def test_tournament_champion_and_cellar():
    items = tournament_highlights(*_scenario())
    titles = _titles(items)
    assert "Champion" in titles and "Cellar dweller" in titles
    champ = next(it for it in items if it["title"] == "Champion")
    cellar = next(it for it in items if it["title"] == "Cellar dweller")
    assert "Alpha" in champ["text"] and "Gamma" in cellar["text"]


def test_tournament_skill_spread_ratio():
    items = tournament_highlights(*_scenario())
    spread = next(it for it in items if it["title"] == "Skill spread")
    # 1700-1500 = 200 Elo → 10**(200/400) ≈ 3.16 → "~3:1"
    assert "200" in spread["text"] and "3:1" in spread["text"]


def test_tournament_dominant_matchup():
    items = tournament_highlights(*_scenario())
    dom = next(it for it in items if it["title"] == "Most dominant matchup")
    assert "Alpha" in dom["text"] and "80%" in dom["text"]


def test_tournament_detects_upset():
    items = tournament_highlights(*_scenario())
    upset = next(it for it in items if it["title"] == "Biggest upset")
    assert "Gamma" in upset["text"] and "Alpha" in upset["text"] and "70%" in upset["text"]


def test_tournament_consistent_ranking_when_no_upset():
    rows = _rows([(0, "a", "Alpha", 1700.0, 70.0),
                  (1, "b", "Beta", 1600.0, 50.0),
                  (2, "c", "Gamma", 1500.0, 30.0)])
    pairs = {
        (0, 1): _Pair(0, 1, 7, 3, 0),
        (0, 2): _Pair(0, 2, 8, 2, 0),
        (1, 2): _Pair(1, 2, 6, 4, 0),
    }
    items = tournament_highlights(_Result(pairs), rows)
    assert any(it["title"] == "Consistent ranking" for it in items)


def test_tournament_guards_single_entrant():
    rows = _rows([(0, "a", "Alpha", 1500.0, 50.0)])
    items = tournament_highlights(_Result({}), rows)
    assert len(items) == 1 and items[0]["tone"] == "neutral"
