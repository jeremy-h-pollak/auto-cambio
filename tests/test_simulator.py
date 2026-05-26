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
