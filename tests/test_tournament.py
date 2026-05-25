"""Unit tests for the round-robin tournament (game/tournament.py)."""

import math

import pytest

from game import strategies
from game import strategy as random_strategy
from game.tournament import (
    Entrant,
    bradley_terry,
    entrants,
    rankings,
    run_tournament,
    to_elo,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _round_robin(n, k, a_wins):
    """Build (win, ngames) for n players, k games/pair. a_wins[(i,j)] = i's wins
    over j for i < j; ties = 0 (decisive)."""
    win = [[0.0] * n for _ in range(n)]
    ng = [[0] * n for _ in range(n)]
    for (i, j), w in a_wins.items():
        win[i][j] = w
        win[j][i] = k - w
        ng[i][j] = ng[j][i] = k
    return win, ng


# ── bradley_terry ──────────────────────────────────────────────────────────────


def test_bt_strict_dominance_is_monotone_and_finite():
    # 0 sweeps everyone; 2 loses everything — exercises the smoothing guard too.
    k = 10
    win, ng = _round_robin(3, k, {(0, 1): k, (0, 2): k, (1, 2): k})
    s = bradley_terry(win, ng)
    assert s[0] > s[1] > s[2]
    assert all(math.isfinite(v) and v > 0 for v in s.values())


def test_bt_balanced_field_is_uniform():
    k = 10
    win, ng = _round_robin(4, k, {(i, j): k // 2 for i in range(4) for j in range(i + 1, 4)})
    s = bradley_terry(win, ng)
    vals = list(s.values())
    assert max(vals) - min(vals) < 1e-6


def test_bt_all_ties_is_uniform():
    # Every game a tie → 0.5*k wins each direction, same as a balanced field.
    k = 8
    win, ng = _round_robin(3, k, {(i, j): k / 2 for i in range(3) for j in range(i + 1, 3)})
    s = bradley_terry(win, ng)
    vals = list(s.values())
    assert max(vals) - min(vals) < 1e-6


def test_bt_normalized_to_unit_geometric_mean():
    win, ng = _round_robin(3, 10, {(0, 1): 8, (0, 2): 7, (1, 2): 6})
    s = bradley_terry(win, ng)
    gm = math.exp(sum(math.log(v) for v in s.values()) / len(s))
    assert gm == pytest.approx(1.0, abs=1e-6)


# ── to_elo ─────────────────────────────────────────────────────────────────────


def test_to_elo_anchor_is_exact_and_monotone():
    s = {0: 2.0, 1: 1.0, 2: 0.5}
    r = to_elo(s, anchor_index=2, anchor_rating=1500.0)
    assert r[2] == pytest.approx(1500.0)
    assert r[0] > r[1] > r[2]
    # 400 * log10(strength ratio) above the anchor.
    assert r[0] == pytest.approx(1500.0 + 400.0 * math.log10(2.0 / 0.5))


def test_to_elo_unanchored_centers_field_mean():
    s = {0: 2.0, 1: 1.0, 2: 0.5}
    r = to_elo(s, anchor_index=None, anchor_rating=1500.0)
    assert sum(r.values()) / len(r) == pytest.approx(1500.0)


# ── entrants ─────────────────────────────────────────────────────────────────


def test_entrants_include_and_exclude_random():
    full = entrants(include_random=True)
    profiles_only = entrants(include_random=False)
    assert len(full) == len(strategies.PROFILES) + 1
    assert len(profiles_only) == len(strategies.PROFILES)
    assert full[-1].key == "random"
    assert all(e.key != "random" for e in profiles_only)


# ── run_tournament ─────────────────────────────────────────────────────────────


def _small_field():
    return [
        Entrant("greedy", "Greedy", strategies.get("greedy")),
        Entrant("minimalist", "Minimalist", strategies.get("minimalist")),
        Entrant("random", "Random", random_strategy),
    ]


def test_run_tournament_structure_and_bookkeeping():
    field_ = _small_field()
    k = 8
    res = run_tournament(field_, k, seed=1, max_turns=300)

    # C(3,2) = 3 pairings, each k games.
    assert len(res.pairs) == 3
    assert res.total_games == 3 * k
    for (i, j), pr in res.pairs.items():
        assert pr.a_wins + pr.b_wins + pr.ties == k
        assert pr.a_starts == k // 2            # balanced sides (k % 4 == 0)
        assert res.ngames[i][j] == res.ngames[j][i] == k
        # win matrix mirrors the record, ties split as halves
        assert res.win[i][j] == pytest.approx(pr.a_wins + 0.5 * pr.ties)
        assert res.win[j][i] == pytest.approx(pr.b_wins + 0.5 * pr.ties)

    for idx in range(len(field_)):
        assert res.wins[idx] + res.losses[idx] + res.ties[idx] == res.games[idx]
        assert res.games[idx] == (len(field_) - 1) * k
        assert idx in res.ratings and idx in res.strengths


def test_run_tournament_anchors_random_at_1500():
    res = run_tournament(_small_field(), 8, seed=1, max_turns=300)
    random_idx = next(i for i, e in enumerate(res.entrants) if e.key == "random")
    assert res.ratings[random_idx] == pytest.approx(1500.0)


def test_run_tournament_is_reproducible():
    a = run_tournament(_small_field(), 8, seed=42, max_turns=300)
    b = run_tournament(_small_field(), 8, seed=42, max_turns=300)
    assert a.wins == b.wins and a.losses == b.losses and a.ties == b.ties


def test_rankings_sorted_and_ranked():
    res = run_tournament(_small_field(), 8, seed=1, max_turns=300)
    rows = rankings(res)
    assert [r["rank"] for r in rows] == [1, 2, 3]
    ratings = [r["rating"] for r in rows]
    assert ratings == sorted(ratings, reverse=True)
