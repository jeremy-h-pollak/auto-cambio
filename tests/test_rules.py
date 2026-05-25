"""Unit tests for the pure game-logic layer (game/rules.py)."""

import copy

import pytest

from game import rules
from game.rules import (
    apply_move,
    card_value,
    create_initial_state,
    get_scores,
    hand_value,
    is_red,
    snap_eligible_indices,
    special_type,
    PHASE_PEEK,
    PHASE_PLAYER_ACTION,
    PHASE_PLAYER_DRAW,
)


def card(rank, suit="♠"):
    return {"rank": rank, "suit": suit}


# ── card_value ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rank,suit,expected",
    [
        ("A", "♠", 1),
        ("5", "♠", 5),
        ("10", "♦", 10),
        ("J", "♣", 11),
        ("Q", "♥", 12),
        ("K", "♠", 13),   # black king
        ("K", "♣", 13),   # black king
        ("K", "♥", -1),   # red king — the special negative case
        ("K", "♦", -1),   # red king
    ],
)
def test_card_value(rank, suit, expected):
    assert card_value(card(rank, suit)) == expected


# ── hand_value ──────────────────────────────────────────────────────────────


def test_hand_value_sums_cards():
    hand = [card("A"), card("5"), card("K", "♠")]  # 1 + 5 + 13
    assert hand_value(hand) == 19


def test_hand_value_skips_none_slots():
    # None slots appear after a card is snapped away.
    hand = [card("5"), None, card("3"), None]
    assert hand_value(hand) == 8


def test_hand_value_includes_negative_red_king():
    hand = [card("K", "♥"), card("2")]  # -1 + 2
    assert hand_value(hand) == 1


# ── is_red ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("suit,expected", [("♥", True), ("♦", True), ("♠", False), ("♣", False)])
def test_is_red(suit, expected):
    assert is_red(card("7", suit)) is expected


# ── snap_eligible_indices ─────────────────────────────────────────────────────


def test_snap_eligible_matches_top_rank():
    hand = [card("7"), card("3"), card("7"), card("Q")]
    discard = [card("7", "♥")]
    assert snap_eligible_indices(hand, discard) == [0, 2]


def test_snap_eligible_excludes_none_slots():
    hand = [None, card("3"), card("3")]
    discard = [card("3", "♦")]
    assert snap_eligible_indices(hand, discard) == [1, 2]


def test_snap_eligible_respects_known_filter():
    hand = [card("4"), card("4"), card("4")]
    discard = [card("4")]
    known = [True, False, True]
    # Only positions the owner actually knows are eligible.
    assert snap_eligible_indices(hand, discard, known) == [0, 2]


def test_snap_eligible_empty_inputs():
    assert snap_eligible_indices([], [card("4")]) == []
    assert snap_eligible_indices([card("4")], []) == []


# ── special_type ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rank,expected",
    [
        ("7", "peek_own"),
        ("8", "peek_own"),
        ("9", "peek_opponent"),
        ("10", "peek_opponent"),
        ("J", "blind_switch"),
        ("Q", "blind_switch"),
        ("K", "looking_switch"),
        ("A", None),
        ("2", None),
        ("6", None),
    ],
)
def test_special_type(rank, expected):
    assert special_type(card(rank)) == expected


# ── create_initial_state ──────────────────────────────────────────────────────


def test_create_initial_state_shape():
    state = create_initial_state()
    assert len(state["player_hand"]) == 4
    assert len(state["computer_hand"]) == 4
    assert len(state["discard_pile"]) == 1
    assert len(state["deck"]) == 43  # 52 - 4 - 4 - 1
    assert state["phase"] == PHASE_PEEK
    assert state["player_known"] == [False, False, True, True]
    assert state["computer_known"] == [False, False, True, True]
    assert state["cambio_called_by"] is None


def test_create_initial_state_honors_starting_turn():
    assert create_initial_state("player")["current_turn"] == "player"
    assert create_initial_state("computer")["current_turn"] == "computer"


# ── get_scores ────────────────────────────────────────────────────────────────


def _scoring_state(player_hand, computer_hand, caller):
    return {
        "player_hand": player_hand,
        "computer_hand": computer_hand,
        "cambio_called_by": caller,
    }


def test_get_scores_no_caller():
    state = _scoring_state([card("2")], [card("9")], None)
    assert get_scores(state) == (2, 9)


def test_get_scores_penalizes_caller_who_is_not_lowest():
    # Player calls Cambio but has the higher (worse) score -> +5 penalty.
    state = _scoring_state([card("9")], [card("2")], "player")
    assert get_scores(state) == (9 + 5, 2)


def test_get_scores_no_penalty_when_caller_is_lowest():
    # Player calls Cambio and is genuinely lowest -> no penalty.
    state = _scoring_state([card("2")], [card("9")], "player")
    assert get_scores(state) == (2, 9)


def test_get_scores_tie_has_no_penalty():
    # Penalty only applies when caller score is strictly greater than opponent's.
    state = _scoring_state([card("5")], [card("5")], "player")
    assert get_scores(state) == (5, 5)


# ── apply_move immutability ────────────────────────────────────────────────────


def test_apply_move_does_not_mutate_input():
    state = create_initial_state("player")
    state = apply_move(state, {"action": "start"})  # leave PEEK -> player_draw
    before = copy.deepcopy(state)

    new_state = apply_move(state, {"action": "draw_deck"})

    # Input is untouched...
    assert state == before
    # ...while the returned state reflects the move.
    assert new_state is not state
    assert new_state["phase"] == PHASE_PLAYER_ACTION
    assert new_state["drawn_card"] is not None
    assert len(new_state["deck"]) == len(state["deck"]) - 1


def test_apply_move_draw_deck_transitions_phase():
    state = apply_move(create_initial_state("player"), {"action": "start"})
    assert state["phase"] == PHASE_PLAYER_DRAW

    state = apply_move(state, {"action": "draw_deck"})
    assert state["phase"] == PHASE_PLAYER_ACTION
    assert state["drawn_card"] is not None
