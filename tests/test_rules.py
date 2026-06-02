"""Unit tests for the pure game-logic layer (game/rules.py)."""

import copy

import pytest

from game import rules
from game.rules import (
    apply_move,
    card_value,
    create_initial_state,
    get_scores,
    get_winner,
    hand_size,
    hand_value,
    is_red,
    opp_snap_eligible_indices,
    snap_eligible_indices,
    special_message,
    special_type,
    COMPUTER_TURN,
    PHASE_GAME_OVER,
    PHASE_PEEK,
    PHASE_PLAYER_ACTION,
    PHASE_PLAYER_DRAW,
    PHASE_PLAYER_SPECIAL,
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


# ── hand_size / get_winner ──────────────────────────────────────────────────


def test_hand_size_skips_none_slots():
    # None slots are emptied positions left behind after a snap.
    assert hand_size([card("5"), None, card("3"), None]) == 2


def test_get_winner_lower_score_wins():
    assert get_winner(_scoring_state([card("2")], [card("9")], None)) == "player"
    assert get_winner(_scoring_state([card("9")], [card("2")], None)) == "computer"


def test_get_winner_tie_broken_by_more_cards():
    # Equal sums (2+2+1 == 5); the hand holding more cards wins.
    state = _scoring_state([card("2"), card("2"), card("A")], [card("5")], None)
    assert get_winner(state) == "player"


def test_get_winner_fewer_cards_loses_tiebreak():
    # Mirror case, and None slots must not count toward the card total.
    state = _scoring_state(
        [card("5"), None, None, None], [card("2"), card("2"), card("A")], None
    )
    assert get_winner(state) == "computer"


def test_get_winner_true_tie_equal_score_and_cards():
    state = _scoring_state([card("5")], [card("5")], None)
    assert get_winner(state) is None


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


# ── opp_snap_eligible_indices ────────────────────────────────────────────────

def test_opp_snap_eligible_empty_discard_or_hand():
    assert opp_snap_eligible_indices([], [True], [card("5")]) == []
    assert opp_snap_eligible_indices([card("5")], [True], []) == []


def test_opp_snap_eligible_matches_rank_and_known_filter():
    comp_hand = [card("5"), card("9"), card("5"), card("J")]
    discard   = [card("5", "♥")]
    known     = [True, False, False, True]
    # Only idx 0 — idx 2 matches rank but the player doesn't know it.
    assert opp_snap_eligible_indices(comp_hand, known, discard) == [0]


# ── special_message ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "stype,step,expected_phrase",
    [
        ("peek_own", 1, "peek at it"),
        ("peek_opponent", 1, "peek at it"),
        ("blind_switch", 1, "swap blindly"),
        ("blind_switch", 2, "swap with"),
        ("looking_switch", 1, "peek at"),
        ("looking_switch", 2, "COMPUTER's cards"),
        ("looking_switch", 3, "Switch these"),
        ("give_card", 1, "give to the computer"),
    ],
)
def test_special_message_returns_phrase(stype, step, expected_phrase):
    assert expected_phrase in special_message(stype, step)


def test_special_message_unknown_stype_returns_empty():
    assert special_message("nonsense", 1) == ""


# ── apply_move: draw_discard edge cases ──────────────────────────────────────

def _player_action_state():
    """Helper: a state mid-turn with phase=player_draw and a known fixed top card."""
    state = apply_move(create_initial_state("player"), {"action": "start"})
    return state


def test_draw_discard_with_empty_pile_does_nothing():
    state = _player_action_state()
    state["discard_pile"] = []
    new_state = apply_move(state, {"action": "draw_discard"})
    assert new_state["drawn_card"] is None
    assert "empty" in new_state["message"].lower()


# ── apply_move: swap onto None slot (placed-card phrasing) ───────────────────

def test_swap_onto_none_slot_player_says_placed():
    state = _player_action_state()
    state["player_hand"][0] = None
    state["drawn_card"] = card("4")
    state["phase"] = PHASE_PLAYER_ACTION
    new_state = apply_move(state, {"action": "swap", "hand_index": 0})
    assert new_state["player_hand"][0] == {"rank": "4", "suit": "♠"}
    assert "placed drawn card" in new_state["message"]


def test_swap_onto_none_slot_computer_says_placed():
    state = _player_action_state()
    state["current_turn"] = "computer"
    state["computer_hand"][0] = None
    state["drawn_card"] = card("4")
    new_state = apply_move(state, {"action": "swap", "hand_index": 0})
    assert new_state["computer_hand"][0] == {"rank": "4", "suit": "♠"}
    # `_advance_turn` overwrites `message` for the next turn; the swap message
    # is preserved in the log.
    assert any("Computer placed drawn card" in entry for entry in new_state["log"])


# ── apply_move: snap guards (return s on invalid input) ──────────────────────

def test_snap_opponent_returns_state_when_invalid():
    """Player-snap-computer with mismatched rank: short-circuit, no mutation."""
    state = _player_action_state()
    state["discard_pile"] = [card("5", "♥")]
    state["computer_hand"] = [card("9"), None, None, None]   # rank mismatch
    state["player_opponent_known"] = [True, False, False, False]
    before = copy.deepcopy(state)
    new_state = apply_move(state, {"action": "snap", "by": "player", "target": "computer", "hand_index": 0})
    # Nothing should have moved.
    assert new_state["computer_hand"] == before["computer_hand"]
    assert new_state["discard_pile"] == before["discard_pile"]


def test_snap_own_hand_returns_state_on_none_slot():
    state = _player_action_state()
    state["discard_pile"] = [card("5", "♥")]
    state["player_hand"] = [None, None, None, None]
    state["player_known"] = [True, True, True, True]
    new_state = apply_move(state, {"action": "snap", "by": "player", "hand_index": 0})
    assert new_state["player_hand"] == [None, None, None, None]


def test_snap_own_hand_returns_state_on_rank_mismatch():
    state = _player_action_state()
    state["discard_pile"] = [card("5", "♥")]
    state["player_hand"] = [card("9"), None, None, None]
    state["player_known"] = [True, True, True, True]
    new_state = apply_move(state, {"action": "snap", "by": "player", "hand_index": 0})
    # 9 doesn't match the 5 on top — return unchanged.
    assert new_state["player_hand"][0] == {"rank": "9", "suit": "♠"}


def test_snap_own_hand_returns_state_when_not_known():
    state = _player_action_state()
    state["discard_pile"] = [card("5", "♥")]
    state["player_hand"] = [card("5"), None, None, None]
    state["player_known"] = [False, True, True, True]   # rank matches, but unknown
    new_state = apply_move(state, {"action": "snap", "by": "player", "hand_index": 0})
    assert new_state["player_hand"][0] == {"rank": "5", "suit": "♠"}


# ── apply_move: pick_card branches (all 4 stypes) ────────────────────────────

def _special_state(stype, step=1, picks=None):
    """A minimal state in player_special, ready for pick_card."""
    state = apply_move(create_initial_state("player"), {"action": "start"})
    state["phase"] = PHASE_PLAYER_SPECIAL
    state["special_action"] = {"type": stype, "step": step, "picks": list(picks or [])}
    state["player_reveal"] = []
    state["player_opponent_reveal"] = []
    return state


def test_pick_card_on_none_slot_returns_state():
    state = _special_state("peek_own")
    state["player_hand"][0] = None
    new_state = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 0})
    # special_action unchanged — the early return guards an empty slot.
    assert new_state["special_action"] == {"type": "peek_own", "step": 1, "picks": []}


def test_pick_card_peek_own_reveals_and_advances_turn():
    state = _special_state("peek_own")
    state["player_hand"][2] = card("8", "♥")
    new_state = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 2})
    assert new_state["player_known"][2] is True
    assert 2 in new_state["player_reveal"]
    assert new_state["special_action"] is None
    # Turn advanced to computer.
    assert new_state["phase"] == COMPUTER_TURN


def test_pick_card_peek_opponent_reveals_and_advances():
    state = _special_state("peek_opponent")
    state["computer_hand"][1] = card("J", "♥")
    new_state = apply_move(state, {"action": "pick_card", "owner": "computer", "hand_index": 1})
    assert new_state["player_opponent_known"][1] is True
    assert 1 in new_state["player_opponent_reveal"]
    assert new_state["special_action"] is None
    assert new_state["phase"] == COMPUTER_TURN


def test_pick_card_blind_switch_two_steps_swaps_cards():
    state = _special_state("blind_switch")
    state["player_hand"][1] = card("5", "♠")
    state["computer_hand"][2] = card("9", "♥")
    state["player_known"][1] = True
    state["computer_known"][2] = True
    # Step 1: pick our card.
    s1 = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 1})
    assert s1["special_action"]["step"] == 2
    assert s1["special_action"]["picks"] == [{"owner": "player", "index": 1}]
    # Step 2: pick opponent's card; they swap blindly.
    s2 = apply_move(s1, {"action": "pick_card", "owner": "computer", "hand_index": 2})
    assert s2["player_hand"][1] == {"rank": "9", "suit": "♥"}
    assert s2["computer_hand"][2] == {"rank": "5", "suit": "♠"}
    # Blind swap clears all known flags involved.
    assert s2["player_known"][1] is False
    assert s2["computer_known"][2] is False
    assert s2["player_opponent_known"][2] is False
    assert s2["special_action"] is None


def test_pick_card_looking_switch_three_steps_records_picks():
    state = _special_state("looking_switch")
    state["player_hand"][0] = card("J", "♠")
    state["computer_hand"][3] = card("3", "♥")
    # Step 1: peek own.
    s1 = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 0})
    assert s1["player_known"][0] is True
    assert 0 in s1["player_reveal"]
    assert s1["special_action"]["step"] == 2
    # Step 2: peek opponent.
    s2 = apply_move(s1, {"action": "pick_card", "owner": "computer", "hand_index": 3})
    assert s2["player_opponent_known"][3] is True
    assert 3 in s2["player_opponent_reveal"]
    assert s2["special_action"]["step"] == 3
    assert s2["special_action"]["picks"] == [
        {"owner": "player", "index": 0},
        {"owner": "computer", "index": 3},
    ]
    # decide_switch follows — see test_decide_switch tests below.


def test_pick_card_give_card_transfers_and_keeps_player_turn():
    state = _special_state("give_card")
    state["player_hand"][1] = card("4", "♠")
    new_state = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 1})
    assert new_state["player_hand"][1] is None
    assert new_state["player_known"][1] is False
    # The 4 should now be at the end of the computer's hand.
    assert new_state["computer_hand"][-1] == {"rank": "4", "suit": "♠"}
    assert new_state["computer_known"][-1] is False
    assert new_state["player_opponent_known"][-1] is True
    # Player still has cards -> phase reverts to player_draw, no game-end.
    assert new_state["phase"] == PHASE_PLAYER_DRAW
    assert new_state["cambio_called_by"] is None


def test_pick_card_give_card_emptying_hand_triggers_last_turn():
    state = _special_state("give_card")
    # Only one card left — giving it empties the player's hand.
    state["player_hand"] = [None, None, card("4", "♠"), None]
    state["player_known"] = [False, False, True, False]
    new_state = apply_move(state, {"action": "pick_card", "owner": "player", "hand_index": 2})
    assert all(c is None for c in new_state["player_hand"])
    assert new_state["cambio_called_by"] == "player_empty"
    assert new_state["phase"] == COMPUTER_TURN


# ── apply_move: decide_switch (K's optional swap) ────────────────────────────

def test_decide_switch_true_swaps_picked_pair():
    state = _special_state("looking_switch", step=3,
                           picks=[{"owner": "player", "index": 0},
                                  {"owner": "computer", "index": 2}])
    state["player_hand"][0] = card("J", "♠")
    state["computer_hand"][2] = card("3", "♥")
    new_state = apply_move(state, {"action": "decide_switch", "do_switch": True})
    assert new_state["player_hand"][0] == {"rank": "3", "suit": "♥"}
    assert new_state["computer_hand"][2] == {"rank": "J", "suit": "♠"}
    assert new_state["player_known"][0] is True
    assert new_state["player_opponent_known"][2] is True
    assert new_state["special_action"] is None
    assert new_state["phase"] == COMPUTER_TURN


def test_decide_switch_false_keeps_hands_and_advances():
    state = _special_state("looking_switch", step=3,
                           picks=[{"owner": "player", "index": 0},
                                  {"owner": "computer", "index": 2}])
    state["player_hand"][0] = card("J", "♠")
    state["computer_hand"][2] = card("3", "♥")
    new_state = apply_move(state, {"action": "decide_switch", "do_switch": False})
    assert new_state["player_hand"][0] == {"rank": "J", "suit": "♠"}
    assert new_state["computer_hand"][2] == {"rank": "3", "suit": "♥"}
    assert "not to switch" in new_state["message"]
    assert new_state["special_action"] is None


# ── apply_move: skip_special and unknown action fall-through ─────────────────

def test_skip_special_clears_and_advances():
    state = _special_state("peek_own")
    new_state = apply_move(state, {"action": "skip_special"})
    assert new_state["special_action"] is None
    assert new_state["phase"] == COMPUTER_TURN


def test_unknown_action_returns_unmodified_state():
    """Final fallback: an unrecognized action just returns the cloned state."""
    state = _player_action_state()
    new_state = apply_move(state, {"action": "no_such_action"})
    # phase didn't change (no handler matched).
    assert new_state["phase"] == state["phase"]
