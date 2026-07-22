"""Unit tests for the self-play simulator (game/simulator.py)."""

from game.simulator import GameRecord


def _record(winner_seat, player_score, computer_score):
    return GameRecord(
        starting_seat="player",
        smart_seat="player",
        seat_strategy={"player": "smart", "computer": "random"},
        winner_seat=winner_seat,
        player_score=player_score,
        computer_score=computer_score,
        length=10,
        ending="cambio",
        cambio_caller=None,
    )


def test_decided_on_cards_true_for_equal_score_win():
    # Decisive game where both hands tied on score → the card-count tie-break decided it.
    assert _record("player", 5, 5).decided_on_cards is True


def test_decided_on_cards_false_for_normal_win():
    # A win on a strictly lower score is not a tie-break.
    assert _record("player", 4, 9).decided_on_cards is False


def test_decided_on_cards_false_for_true_tie():
    # Equal score with no winner is a genuine tie, not a tie-break win.
    assert _record(None, 5, 5).decided_on_cards is False


# ── seat / first-move balancing ──────────────────────────────────────────────

def test_balanced_sides_cycles_all_four_cells():
    from game.simulator import balanced_sides
    assert [balanced_sides(g) for g in range(4)] == [
        ("player", "player"), ("computer", "player"),
        ("player", "computer"), ("computer", "computer"),
    ]
    assert balanced_sides(4) == balanced_sides(0)


def test_run_simulation_stratifies_seat_and_starter_exactly():
    """The four (smart seat x who starts) cells must be exactly even, not even
    in expectation — sampling them left the smallest cell ~10% short at n=500."""
    from collections import Counter
    from game import strategy as random_strategy
    from game.simulator import run_simulation

    recs, _ = run_simulation(200, random_strategy, opponent=random_strategy, seed=3)
    cells = Counter((r.smart_seat, r.starting_seat) for r in recs)
    assert len(cells) == 4 and set(cells.values()) == {50}


def test_tournament_and_simulator_share_one_balancer():
    from game.simulator import balanced_sides
    from game.tournament import _sides
    assert [_sides(g) for g in range(8)] == [balanced_sides(g) for g in range(8)]
