"""Unit tests for duplicate deals (game/deals.py + the duplicate schedule)."""

import random

import pytest

from game import strategies
from game.deals import make_deals
from game.rules import create_initial_state, RANKS, SUITS
from game.simulator import play_game
from game.tournament import (
    Entrant, _schedule, _pair_deals, run_tournament, bootstrap_ratings)
import game.strategy as random_strategy


def _field():
    return [
        Entrant("greedy", "Greedy", strategies.get("greedy")),
        Entrant("minimalist", "Minimalist", strategies.get("minimalist")),
        Entrant("random", "Random", random_strategy),
    ]


# ── Deal generation ──────────────────────────────────────────────────────────

def test_make_deals_is_a_full_deck_in_random_order():
    (deal,) = make_deals(1, seed=1)
    assert len(deal.deck) == 52
    assert {(c["suit"], c["rank"]) for c in deal.deck} == {
        (s, r) for s in SUITS for r in RANKS}


def test_make_deals_is_reproducible_and_distinct_per_index():
    a = make_deals(4, seed=7)
    b = make_deals(4, seed=7)
    assert [d.deck for d in a] == [d.deck for d in b]
    assert [d.seed for d in a] == [d.seed for d in b]
    orders = {tuple((c["suit"], c["rank"]) for c in d.deck) for d in a}
    assert len(orders) == 4                       # no repeated shuffles
    assert [d.index for d in a] == [0, 1, 2, 3]


def test_make_deals_ignores_the_global_random_stream():
    random.seed(1)
    a = make_deals(2, seed=99)
    random.seed(2)
    [random.random() for _ in range(50)]
    b = make_deals(2, seed=99)
    assert [d.deck for d in a] == [d.deck for d in b]


# ── Fixed decks in create_initial_state ──────────────────────────────────────

def test_create_initial_state_honours_a_supplied_deck():
    (deal,) = make_deals(1, seed=3)
    s = create_initial_state("player", deck=deal.deck, deal_seed=deal.seed)
    assert s["player_hand"] == list(deal.deck[:4])
    assert s["computer_hand"] == list(deal.deck[4:8])
    assert s["discard_pile"] == [deal.deck[8]]
    assert len(s["deck"]) == 43
    assert s["deal_seed"] == deal.seed


def test_supplied_deck_is_copied_not_aliased():
    (deal,) = make_deals(1, seed=3)
    s = create_initial_state("player", deck=deal.deck)
    s["player_hand"][0]["rank"] = "MUTATED"
    assert deal.deck[0]["rank"] != "MUTATED"


def test_default_state_still_shuffles_from_the_global_stream():
    random.seed(11)
    a = create_initial_state("player")
    random.seed(11)
    b = create_initial_state("player")
    assert a["player_hand"] == b["player_hand"]
    assert a["deal_seed"] is None


# ── Playing a fixed deal ─────────────────────────────────────────────────────

def test_same_deal_and_seats_replays_identically():
    """A deal fixes the deck *and* the in-game RNG, so the result is a function of
    (deal, seats, strategies) — the property the mirrored pair relies on."""
    (deal,) = make_deals(1, seed=5)
    strat = {"player": strategies.get("greedy"), "computer": random_strategy}
    outs = []
    for t in range(3):
        random.seed(1234 + t)                     # different global stream each time
        rec = play_game(strat, "player", "player",
                        {"player": "a", "computer": "b"}, 300, deal=deal)
        outs.append((rec.winner_seat, rec.player_score, rec.computer_score, rec.length))
    assert len(set(outs)) == 1


def test_play_game_records_the_deal_index():
    deals_ = make_deals(2, seed=5)
    strat = {"player": strategies.get("greedy"), "computer": random_strategy}
    rec = play_game(strat, "player", "player", {"player": "a", "computer": "b"},
                    300, deal=deals_[1])
    assert rec.deal_index == 1
    plain = play_game(strat, "player", "player", {"player": "a", "computer": "b"}, 300)
    assert plain.deal_index is None


# ── The duplicate schedule ───────────────────────────────────────────────────

def test_schedule_without_deals_is_the_original_independent_one():
    sched = _schedule(4, ())
    assert [(a, s) for a, s, _, _ in sched] == [
        ("player", "player"), ("computer", "player"),
        ("player", "computer"), ("computer", "computer")]
    assert all(d is None and m is None for _, _, d, m in sched)


def test_schedule_plays_each_deal_twice_with_the_entrants_swapped():
    deals_ = make_deals(3, seed=1)
    sched = _schedule(6, deals_)
    assert len(sched) == 6
    for m in range(3):
        games = [g for g in sched if g[3] == m]
        assert len(games) == 2
        # identical deal and starting seat; A takes each physical seat once
        assert games[0][2] is games[1][2] is deals_[m]
        assert games[0][1] == games[1][1]
        assert {games[0][0], games[1][0]} == {"player", "computer"}


def test_duplicate_schedule_keeps_sides_balanced():
    deals_ = make_deals(2, seed=1)
    sched = _schedule(4, deals_)
    a_starts = sum(1 for a_seat, starting, _, _ in sched if a_seat == starting)
    assert a_starts == 2                          # A moves first in half the games


# ── run_tournament in duplicate mode ─────────────────────────────────────────

def test_duplicate_tournament_bookkeeping_and_deal_scores():
    k = 8
    res = run_tournament(_field(), k, seed=1, max_turns=300, duplicate=True)
    assert res.duplicate is True
    assert res.n_deals == k // 2
    assert res.total_games == 3 * k
    for pr in res.pairs.values():
        assert pr.a_wins + pr.b_wins + pr.ties == k
        assert pr.a_starts == k // 2
        assert len(pr.deal_scores) == k // 2
        # each deal contributes two games, so A's per-deal score lies in [0, 2]
        assert all(0.0 <= s <= 2.0 for s in pr.deal_scores)
        assert sum(pr.deal_scores) == pytest.approx(pr.a_wins + 0.5 * pr.ties)


def test_each_pairing_draws_an_independent_deal_set():
    """Sharing one deal set field-wide correlates every pairing in a run, which
    measured ~3x *worse* run-to-run rating variance — so deals are per-pairing."""
    a = _pair_deals(6, True, 1, 0)
    b = _pair_deals(6, True, 1, 1)
    assert len(a) == len(b) == 3
    assert [d.deck for d in a] != [d.deck for d in b]
    # ...but reproducible for a given (seed, pairing index)
    assert [d.deck for d in _pair_deals(6, True, 1, 0)] == [d.deck for d in a]


def test_pair_deals_is_empty_outside_duplicate_mode():
    assert _pair_deals(6, False, 1, 0) == ()


def test_duplicate_rejects_an_odd_game_count():
    with pytest.raises(ValueError, match="even"):
        run_tournament(_field(), 5, seed=1, max_turns=300, duplicate=True)


def test_duplicate_tournament_is_reproducible():
    a = run_tournament(_field(), 8, seed=42, max_turns=300, duplicate=True)
    b = run_tournament(_field(), 8, seed=42, max_turns=300, duplicate=True)
    assert a.wins == b.wins and a.losses == b.losses and a.ties == b.ties
    assert [p.deal_scores for p in a.pairs.values()] == \
           [p.deal_scores for p in b.pairs.values()]


def test_non_duplicate_tournament_records_no_deal_scores():
    res = run_tournament(_field(), 8, seed=1, max_turns=300)
    assert res.duplicate is False and res.n_deals == 0
    assert all(pr.deal_scores == [] for pr in res.pairs.values())


# ── Block bootstrap ──────────────────────────────────────────────────────────

def test_bootstrap_blocks_on_deals_when_present():
    """With deal pairs recorded the resampling unit is the deal, so a replicate's
    total games stays 2 x n_deals and A's score stays on the deal-score lattice."""
    res = run_tournament(_field(), 8, seed=1, max_turns=300, duplicate=True)
    cis = bootstrap_ratings(res, n_boot=50, seed=3)
    assert set(cis) == {0, 1, 2}
    for i, band in cis.items():
        assert band["lo"] <= band["median"] <= band["hi"]


def test_bootstrap_still_works_without_deal_scores():
    res = run_tournament(_field(), 8, seed=1, max_turns=300)
    cis = bootstrap_ratings(res, n_boot=50, seed=3)
    for band in cis.values():
        assert band["lo"] <= band["median"] <= band["hi"]
