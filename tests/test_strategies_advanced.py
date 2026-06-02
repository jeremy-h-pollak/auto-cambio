"""Unit tests for the advanced (EV + memory) strategies in
`game/strategies_advanced.py`. The advanced strategies are deterministic — no
randomness — so each branch is reachable by hand-built states.
"""

import pytest

from game.strategies_advanced import (
    ADVANCED,
    AdvancedStrategy,
    Architect,
    Cartographer,
    EV_UNKNOWN,
    Saboteur,
    Sentinel,
    Sprinter,
    get_advanced,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def card(rank, suit="♠"):
    return {"rank": rank, "suit": suit}


def make_state(
    *,
    seat="computer",
    own_hand=None,
    own_known=None,
    opp_hand=None,
    discard=None,
    drawn=None,
    cambio_called_by=None,
):
    """A minimal state dict sufficient to drive an AdvancedStrategy.

    Only the keys the strategy reads are populated; `_amem` is lazily created
    by `_memory()` so we don't need to seed it.
    """
    own_hand = list(own_hand) if own_hand is not None else [card("5"), card("3"), None, card("Q")]
    own_known = list(own_known) if own_known is not None else [True, True, False, True]
    opp_hand = list(opp_hand) if opp_hand is not None else [card("4"), card("7"), card("9"), card("J")]
    other = "player" if seat == "computer" else "computer"
    return {
        "current_turn": seat,
        f"{seat}_hand": own_hand,
        f"{seat}_known": own_known,
        f"{other}_hand": opp_hand,
        f"{other}_known": [False] * len(opp_hand),
        "drawn_card": drawn,
        "discard_pile": list(discard or []),
        "cambio_called_by": cambio_called_by,
    }


# ── ADVANCED registry + get_advanced ──────────────────────────────────────────

def test_advanced_registry_lists_all_five():
    assert set(ADVANCED) == {"architect", "cartographer", "saboteur", "sprinter", "sentinel"}


@pytest.mark.parametrize("key", list(ADVANCED))
def test_get_advanced_returns_fresh_instance(key):
    a, b = get_advanced(key), get_advanced(key)
    assert a is not b
    assert isinstance(a, AdvancedStrategy)
    assert a.key == key
    # Each subclass overrides `name` and `rules`.
    assert isinstance(a.name, str) and a.name
    assert isinstance(a.rules, list) and a.rules


# ── memory: _remember and _prune_memory ───────────────────────────────────────

def test_remember_then_prune_keeps_unchanged_slot():
    strat = Architect()
    state = make_state()
    strat._remember(state, "computer", 0, card("4", "♣"))  # opp_hand[0] is 4♠ default
    # We remember it as 4♣ but the actual opp_hand[0] is 4♠ — different suit, so prune drops it.
    strat._prune_memory(state, "computer")
    assert 0 not in state["_amem"]["computer"]


def test_prune_drops_remembered_card_that_is_now_none():
    strat = Architect()
    state = make_state(opp_hand=[card("4"), None, card("9"), None])
    strat._remember(state, "computer", 1, card("4"))
    strat._prune_memory(state, "computer")
    assert 1 not in state["_amem"]["computer"]


def test_prune_keeps_matching_remembered_card():
    strat = Architect()
    state = make_state(opp_hand=[card("4", "♣"), card("7"), None, card("J")])
    strat._remember(state, "computer", 0, card("4", "♣"))
    strat._prune_memory(state, "computer")
    assert state["_amem"]["computer"][0] == {"rank": "4", "suit": "♣"}


# ── estimators ────────────────────────────────────────────────────────────────

def test_est_own_total_uses_known_value_else_ev_unknown():
    strat = Architect()
    state = make_state(
        own_hand=[card("2"), card("3"), card("9"), None],
        own_known=[True, True, False, False],
    )
    # Known: 2 + 3 = 5; unknown slot at index 2 -> EV_UNKNOWN; None at index 3 is skipped.
    assert strat._est_own_total(state, "computer") == pytest.approx(5 + EV_UNKNOWN)


def test_est_opp_total_uses_memory_else_ev_unknown():
    strat = Architect()
    state = make_state(opp_hand=[card("2"), card("5"), card("9"), None])
    strat._remember(state, "computer", 1, card("5"))
    # idx 0 unknown -> EV, idx 1 known via memory = 5, idx 2 unknown -> EV, idx 3 None skipped.
    assert strat._est_opp_total(state, "computer") == pytest.approx(EV_UNKNOWN + 5 + EV_UNKNOWN)


# ── choose_move: draw-phase branches ──────────────────────────────────────────

def test_choose_move_calls_cambio_when_ahead_and_under_cap():
    strat = Architect()
    # Own = 1+1+1+1 = 4, well under cap=13; opp all unknown -> ~25.84 estimated, big margin.
    state = make_state(
        own_hand=[card("A"), card("A"), card("A"), card("A")],
        own_known=[True] * 4,
    )
    assert strat.choose_move(state) == {"action": "call_cambio"}


def test_choose_move_does_not_call_cambio_in_last_turn():
    strat = Architect()
    # Same hand as above, but opponent already called Cambio -> never call ours.
    state = make_state(
        own_hand=[card("A"), card("A"), card("A"), card("A")],
        own_known=[True] * 4,
        cambio_called_by="player",
    )
    move = strat.choose_move(state)
    assert move["action"] in ("draw_deck", "draw_discard")


def test_choose_move_draws_discard_when_cheap_top_improves_hand():
    strat = Architect()
    # Own has a known Q (12) on top of hand; discard top is a 3 — clearly improves the Q slot.
    state = make_state(
        own_hand=[card("Q"), card("9"), card("7"), card("5")],
        own_known=[True, True, True, True],
        discard=[card("3", "♥")],
    )
    assert strat.choose_move(state) == {"action": "draw_discard"}


def test_choose_move_draws_deck_when_discard_top_too_high():
    strat = Architect()
    # Discard top is a 10 — above grab_discard_max=4 — so we draw from the deck instead.
    state = make_state(
        own_hand=[card("Q"), card("9"), card("7"), card("5")],
        own_known=[True, True, True, True],
        discard=[card("10", "♦")],
    )
    assert strat.choose_move(state) == {"action": "draw_deck"}


# ── choose_move: action-with-drawn branches ───────────────────────────────────

def test_action_with_drawn_swaps_out_high_known_card():
    strat = Architect()
    # Known Q=12; drew a 2. Bury the queen.
    state = make_state(
        own_hand=[card("Q"), card("9"), card("7"), card("5")],
        own_known=[True, True, True, True],
        drawn=card("2"),
    )
    move = strat.choose_move(state)
    assert move == {"action": "swap", "hand_index": 0}


def test_action_with_drawn_fires_peek_own_for_its_power():
    strat = Architect()
    # We hold a known small hand with an unknown slot — firing the 7 reveals one.
    state = make_state(
        own_hand=[card("2"), card("3"), card("9", "♥"), card("4")],
        own_known=[True, True, False, True],
        drawn=card("7"),
    )
    move = strat.choose_move(state)
    assert move == {"action": "discard_drawn"}


def test_action_with_drawn_fires_peek_opponent_when_want_info():
    strat = Architect()
    # No unknowns of our own, no big card to bury; opponent slots unmapped -> fire 9.
    state = make_state(
        own_hand=[card("2"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        drawn=card("9"),
    )
    assert strat.choose_move(state) == {"action": "discard_drawn"}


def test_action_with_drawn_gambles_below_mean_onto_unknown():
    strat = Architect()
    # No known-high to bury, no special drawn — but drew a 4 (≤ gamble_max=6) and we have an unknown.
    state = make_state(
        own_hand=[card("2"), card("3", "♥"), None, None],
        own_known=[True, False, False, False],
        drawn=card("4"),
    )
    move = strat.choose_move(state)
    assert move == {"action": "swap", "hand_index": 1}


def test_action_with_drawn_discards_when_nothing_useful():
    strat = Architect()
    # All known low, no special-improving draw, no unknowns -> discard.
    state = make_state(
        own_hand=[card("2"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        drawn=card("6"),
    )
    assert strat.choose_move(state) == {"action": "discard_drawn"}


def test_action_with_drawn_buries_big_known_high():
    """Path 1: hi[1] >= 11 takes priority over everything (even firing a power)."""
    strat = Architect()
    state = make_state(
        own_hand=[card("K", "♠"), card("3"), card("4"), card("5")],   # known black K = 13
        own_known=[True, True, True, True],
        drawn=card("7"),  # would normally be discarded for the peek power
    )
    move = strat.choose_move(state)
    assert move == {"action": "swap", "hand_index": 0}


def test_action_with_drawn_last_turn_skips_power_fire():
    """In last_turn, the peek-fire branch is skipped; falls through to plain improvement/gamble."""
    strat = Architect()
    state = make_state(
        own_hand=[card("2"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        drawn=card("9"),     # peek_opponent — would normally be fired
        cambio_called_by="player",
    )
    # No big-bury, no fire, no unknowns to gamble on -> discard.
    assert strat.choose_move(state) == {"action": "discard_drawn"}


# ── should_snap ───────────────────────────────────────────────────────────────

def test_should_snap_accepts_positive_card():
    strat = Architect()
    state = make_state(
        own_hand=[card("5"), card("3"), None, card("Q")],
        own_known=[True, True, False, True],
    )
    assert strat.should_snap(state, 0) is True


def test_should_snap_skips_none_slot():
    strat = Architect()
    state = make_state(
        own_hand=[None, card("3"), None, card("Q")],
        own_known=[False, True, False, True],
    )
    assert strat.should_snap(state, 0) is False


def test_should_snap_refuses_red_king_by_default():
    strat = Architect()  # snap_negatives = False
    state = make_state(
        own_hand=[card("K", "♥"), card("3"), None, card("Q")],
        own_known=[True, True, False, True],
    )
    assert strat.should_snap(state, 0) is False


def test_sprinter_snaps_red_king():
    strat = Sprinter()   # snap_negatives = True
    state = make_state(
        own_hand=[card("K", "♥"), card("3"), None, card("Q")],
        own_known=[True, True, False, True],
    )
    assert strat.should_snap(state, 0) is True


# ── apply_special: peek_own ───────────────────────────────────────────────────

def test_apply_special_peek_own_reveals_first_unknown():
    strat = Architect()
    state = make_state(
        own_hand=[card("5"), card("3"), card("9"), card("Q")],
        own_known=[True, True, False, True],
    )
    strat.apply_special(state, "computer", "peek_own")
    assert state["computer_known"] == [True, True, True, True]


def test_apply_special_peek_own_noop_when_all_known():
    strat = Architect()
    state = make_state(
        own_hand=[card("5"), card("3"), card("9"), card("Q")],
        own_known=[True, True, True, True],
    )
    strat.apply_special(state, "computer", "peek_own")
    assert state["computer_known"] == [True, True, True, True]


# ── apply_special: peek_opponent ──────────────────────────────────────────────

def test_apply_special_peek_opponent_remembers_first_unseen():
    strat = Architect()
    state = make_state(opp_hand=[card("4"), card("7"), card("9"), card("J")])
    strat.apply_special(state, "computer", "peek_opponent")
    # First unseen idx 0 should be remembered.
    assert state["_amem"]["computer"][0] == {"rank": "4", "suit": "♠"}


def test_apply_special_peek_opponent_skips_already_remembered():
    strat = Architect()
    state = make_state(opp_hand=[card("4"), card("7"), card("9"), card("J")])
    strat._remember(state, "computer", 0, card("4"))
    strat.apply_special(state, "computer", "peek_opponent")
    # 0 was already known; the next unseen idx (1) is added.
    assert 1 in state["_amem"]["computer"]


# ── apply_special: blind_switch ───────────────────────────────────────────────

def test_blind_switch_with_remembered_low_steals_it():
    strat = Architect()   # blind_switch_min_give = 9
    state = make_state(
        own_hand=[card("Q", "♠"), card("3"), card("4"), card("5")],   # Q known = 12 worth dumping
        own_known=[True, True, True, True],
        opp_hand=[card("8"), card("2", "♥"), card("9"), card("J")],
    )
    # We've peeked their 2 at idx 1 — that's the low to take.
    strat._remember(state, "computer", 1, card("2", "♥"))
    strat.apply_special(state, "computer", "blind_switch")
    # Our hand idx 0 now holds the 2; opp idx 1 now holds our Q.
    assert state["computer_hand"][0] == {"rank": "2", "suit": "♥"}
    assert state["player_hand"][1] == {"rank": "Q", "suit": "♠"}
    # We knew what we took (it was remembered) -> own_known[0] stays True.
    assert state["computer_known"][0] is True
    # And we now "remember" that opp idx 1 holds our old Q.
    assert state["_amem"]["computer"][1] == {"rank": "Q", "suit": "♠"}


def test_blind_switch_no_op_when_no_high_to_dump():
    strat = Architect()
    state = make_state(
        own_hand=[card("2"), card("3"), card("4"), card("5")],   # no known card ≥ 9
        own_known=[True, True, True, True],
    )
    before_own = list(state["computer_hand"])
    before_opp = list(state["player_hand"])
    strat.apply_special(state, "computer", "blind_switch")
    assert state["computer_hand"] == before_own
    assert state["player_hand"] == before_opp


def test_blind_switch_no_op_when_opp_hand_empty():
    strat = Architect()
    state = make_state(
        own_hand=[card("Q"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[None, None, None, None],
    )
    before_own = list(state["computer_hand"])
    strat.apply_special(state, "computer", "blind_switch")
    assert state["computer_hand"] == before_own


def test_blind_switch_falls_back_to_unseen_when_no_remembered_low():
    strat = Architect()
    state = make_state(
        own_hand=[card("Q"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[card("8"), card("7"), card("9"), card("J")],
    )
    strat.apply_special(state, "computer", "blind_switch")
    # First unseen opp slot is idx 0. Our Q moves there; we take their 8 but don't know it.
    assert state["computer_hand"][0] == {"rank": "8", "suit": "♠"}
    assert state["player_hand"][0] == {"rank": "Q", "suit": "♠"}
    assert state["computer_known"][0] is False
    # And we've remembered that opp idx 0 now holds our Q.
    assert state["_amem"]["computer"][0] == {"rank": "Q", "suit": "♠"}


def test_blind_switch_steals_remembered_low_even_when_all_seen():
    """All opp slots remembered (none unseen); the J@0 is the only one < our Q — steal it."""
    strat = Architect()
    state = make_state(
        own_hand=[card("Q"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[card("J"), card("K", "♠"), card("K", "♠"), card("K", "♠")],
    )
    strat._remember(state, "computer", 0, card("J"))
    strat._remember(state, "computer", 1, card("K", "♠"))
    strat._remember(state, "computer", 2, card("K", "♠"))
    strat._remember(state, "computer", 3, card("K", "♠"))
    strat.apply_special(state, "computer", "blind_switch")
    assert state["computer_hand"][0] == {"rank": "J", "suit": "♠"}


# ── apply_special: looking_switch ─────────────────────────────────────────────

def test_looking_switch_swaps_on_strict_gain():
    strat = Architect()
    state = make_state(
        own_hand=[card("J", "♠"), card("3"), card("4"), card("5")],   # J=11 known
        own_known=[True, True, True, True],
        opp_hand=[card("2", "♥"), card("9"), card("Q"), card("K", "♠")],
    )
    strat._remember(state, "computer", 0, card("2", "♥"))   # remember a known-low
    strat.apply_special(state, "computer", "looking_switch")
    # 2 < 11 -> switch.
    assert state["computer_hand"][0] == {"rank": "2", "suit": "♥"}
    assert state["player_hand"][0] == {"rank": "J", "suit": "♠"}


def test_looking_switch_skips_when_no_gain_available():
    strat = Architect()
    state = make_state(
        own_hand=[card("5"), card("3"), card("4"), card("2")],   # all low
        own_known=[True, True, True, True],
        opp_hand=[card("J"), card("Q"), card("K", "♠"), card("9")],
    )
    before_own = list(state["computer_hand"])
    strat.apply_special(state, "computer", "looking_switch")
    # No gain — own_hand unchanged.
    assert state["computer_hand"] == before_own
    # We did *look* at one of theirs, so memory now has one entry.
    assert state["_amem"]["computer"]


def test_looking_switch_noop_when_either_hand_empty():
    strat = Architect()
    state = make_state(
        own_hand=[None, None, None, None],
        own_known=[False, False, False, False],
    )
    before_opp = list(state["player_hand"])
    strat.apply_special(state, "computer", "looking_switch")
    assert state["player_hand"] == before_opp


def test_looking_switch_chooses_unseen_when_no_remembered_low():
    strat = Architect()
    state = make_state(
        own_hand=[card("Q", "♠"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[card("2"), card("3"), card("4"), card("5")],
    )
    # No memory at all -> picks unseen[0] = 0; opp_hand[0]=2 < Q -> switch.
    strat.apply_special(state, "computer", "looking_switch")
    assert state["computer_hand"][0] == {"rank": "2", "suit": "♠"}


# ── apply_computer_special ────────────────────────────────────────────────────

def test_apply_computer_special_delegates_to_apply_special():
    strat = Architect()
    state = make_state(
        own_hand=[card("5"), card("3"), card("9"), card("Q")],
        own_known=[True, True, False, True],
    )
    strat.apply_computer_special(state, "peek_own")
    assert state["computer_known"][2] is True


# ── Subclass-specific overrides ───────────────────────────────────────────────

def test_cartographer_fires_peek_while_exploring():
    """_still_exploring True -> drawn peek discarded for the power even with a small swap available."""
    strat = Cartographer()
    state = make_state(
        own_hand=[card("Q"), None, None, None],     # plenty of unknowns
        own_known=[True, False, False, False],
        opp_hand=[card("4"), card("7"), card("9"), card("J")],  # opp memory empty -> exploring
        drawn=card("7"),
    )
    assert strat.choose_move(state) == {"action": "discard_drawn"}


def test_cartographer_falls_through_to_super_when_not_exploring():
    """Own hand fully known and opp mapped enough -> base _action_with_drawn governs."""
    strat = Cartographer()
    state = make_state(
        own_hand=[card("K", "♠"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[card("2"), card("3"), card("4"), card("5")],
        drawn=card("7"),
    )
    # Pre-fill opponent memory so we're no longer exploring.
    strat._remember(state, "computer", 0, card("2"))
    strat._remember(state, "computer", 1, card("3"))
    strat._remember(state, "computer", 2, card("4"))
    # Big-bury path: drawn 7 < 13(K) -> swap.
    move = strat.choose_move(state)
    assert move == {"action": "swap", "hand_index": 0}


def test_cartographer_cambio_gated_on_low_memory_unless_tiny_hand():
    """Cartographer's _should_call_cambio refuses with <2 memorized unless own ≤6 + lead."""
    strat = Cartographer()
    # Tiny known hand (sum 3); empty memory -> still callable via the tiny-hand bailout.
    state = make_state(
        own_hand=[card("A"), card("A"), card("A"), None],
        own_known=[True, True, True, False],
        opp_hand=[card("9"), card("9"), card("9"), card("9")],
    )
    assert strat.choose_move(state) == {"action": "call_cambio"}


def test_cartographer_cambio_blocked_with_low_memory_and_average_hand():
    strat = Cartographer()
    # Own ≈ 4 + EV(unknown) ≈ 10.46, above the tiny-hand cutoff of 6 — Cartographer should not
    # call without enough memorized slots.
    state = make_state(
        own_hand=[card("A"), card("A"), card("A"), card("A")],
        own_known=[True, True, True, False],
        opp_hand=[card("9"), card("9"), card("9"), card("9")],
    )
    move = strat.choose_move(state)
    assert move["action"] != "call_cambio"


# ── Each subclass: still works end-to-end on a single move ────────────────────

@pytest.mark.parametrize("key", list(ADVANCED))
def test_each_strategy_chooses_a_legal_looking_move(key):
    strat = get_advanced(key)
    state = make_state(
        own_hand=[card("Q"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
    )
    move = strat.choose_move(state)
    assert move["action"] in {"call_cambio", "draw_deck", "draw_discard"}


# Sentinel never blind-switches (min_give = 99) — confirm the early return.
def test_sentinel_never_blind_switches():
    strat = Sentinel()
    state = make_state(
        own_hand=[card("K", "♠"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
    )
    before_own = list(state["computer_hand"])
    strat.apply_special(state, "computer", "blind_switch")
    assert state["computer_hand"] == before_own


# Saboteur dumps eagerly at min_give=8 — confirm an 8-value card moves.
def test_saboteur_blind_switches_at_eight():
    strat = Saboteur()
    state = make_state(
        own_hand=[card("8", "♠"), card("3"), card("4"), card("5")],
        own_known=[True, True, True, True],
        opp_hand=[card("2"), card("7"), card("9"), card("J")],
    )
    strat._remember(state, "computer", 0, card("2"))
    strat.apply_special(state, "computer", "blind_switch")
    # The known 8 should have moved out; we took back the remembered 2.
    assert state["computer_hand"][0] == {"rank": "2", "suit": "♠"}
