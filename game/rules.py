import random
import copy

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RED_SUITS = {"♥", "♦"}

PHASE_PEEK = "peek"
PHASE_PLAYER_DRAW = "player_draw"
PHASE_PLAYER_ACTION = "player_action"
PHASE_GAME_OVER = "game_over"


def card_value(card):
    rank = card["rank"]
    suit = card["suit"]
    if rank == "A":
        return 1
    if rank in ("J",):
        return 11
    if rank == "Q":
        return 12
    if rank == "K":
        return -1 if suit in RED_SUITS else 13
    return int(rank)


def hand_value(hand):
    return sum(card_value(c) for c in hand)


def is_red(card):
    return card["suit"] in RED_SUITS


def _make_deck():
    deck = [{"suit": s, "rank": r} for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def create_initial_state():
    deck = _make_deck()
    player_hand = deck[:4]
    computer_hand = deck[4:8]
    discard_pile = [deck[8]]
    remaining = deck[9:]

    return {
        "phase": PHASE_PEEK,
        "deck": remaining,
        "discard_pile": discard_pile,
        "player_hand": player_hand,
        "computer_hand": computer_hand,
        "drawn_card": None,
        # list of bools: True if player has seen that position
        "player_known": [False, False, True, True],
        "computer_known": [False, False, True, True],
        "cambio_called_by": None,
        "current_turn": "player",
        "message": "Peek at your last 2 cards, then press Start.",
        "log": [],
    }


def _clone(state):
    return copy.deepcopy(state)


def _reshuffle_if_needed(state):
    if not state["deck"]:
        top = state["discard_pile"].pop()
        random.shuffle(state["discard_pile"])
        state["deck"] = state["discard_pile"]
        state["discard_pile"] = [top]


def _advance_turn(state):
    """Called after a swap or discard_drawn to move to next phase."""
    if state["cambio_called_by"] is not None:
        state["phase"] = PHASE_GAME_OVER
        state["message"] = "Game over! Revealing all cards…"
        state["log"].append("Game over!")
        return state

    if state["current_turn"] == "player":
        state["current_turn"] = "computer"
        # engine.py will drive the computer turn; phase stays as signal
        state["phase"] = "computer_turn"
    else:
        state["current_turn"] = "player"
        state["phase"] = PHASE_PLAYER_DRAW
        state["message"] = "Your turn: draw a card or call Cambio."

    return state


def apply_move(state, move):
    """Pure function: returns new state after applying move."""
    s = _clone(state)
    action = move["action"]

    if action == "start":
        s["phase"] = PHASE_PLAYER_DRAW
        s["message"] = "Your turn: draw a card or call Cambio."
        return s

    if action == "call_cambio":
        s["cambio_called_by"] = s["current_turn"]
        who = "You" if s["current_turn"] == "player" else "Computer"
        msg = f"{who} called Cambio! The other player gets one last turn."
        s["message"] = msg
        s["log"].append(msg)
        # Give OTHER player their last turn
        if s["current_turn"] == "player":
            s["current_turn"] = "computer"
            s["phase"] = "computer_turn"
        else:
            s["current_turn"] = "player"
            s["phase"] = PHASE_PLAYER_DRAW
            s["message"] = "Computer called Cambio! This is your last turn."
        return s

    if action in ("draw_deck", "draw_discard"):
        _reshuffle_if_needed(s)
        if action == "draw_deck":
            s["drawn_card"] = s["deck"].pop()
        else:
            if not s["discard_pile"]:
                s["message"] = "Discard pile is empty."
                return s
            s["drawn_card"] = s["discard_pile"].pop()

        card = s["drawn_card"]
        src = "the deck" if action == "draw_deck" else "the discard pile"
        if s["current_turn"] == "player":
            s["phase"] = PHASE_PLAYER_ACTION
            s["message"] = (
                f"You drew {card['rank']}{card['suit']} from {src}. "
                "Click a hand card to swap, or discard it."
            )
        return s

    if action == "swap":
        idx = move["hand_index"]
        hand_key = "player_hand" if s["current_turn"] == "player" else "computer_hand"
        known_key = "player_known" if s["current_turn"] == "player" else "computer_known"
        old_card = s[hand_key][idx]
        s[hand_key][idx] = s["drawn_card"]
        s["discard_pile"].append(old_card)
        s[known_key][idx] = True
        s["drawn_card"] = None

        if s["current_turn"] == "player":
            msg = (
                f"You swapped position {idx + 1} "
                f"(discarded {old_card['rank']}{old_card['suit']})."
            )
            s["message"] = msg
            s["log"].append(msg)
        else:
            msg = f"Computer swapped position {idx + 1} (discarded {old_card['rank']}{old_card['suit']})."
            s["message"] = msg
            s["log"].append(msg)

        return _advance_turn(s)

    if action == "discard_drawn":
        card = s["drawn_card"]
        s["discard_pile"].append(card)
        s["drawn_card"] = None

        if s["current_turn"] == "player":
            msg = f"You discarded {card['rank']}{card['suit']}."
            s["message"] = msg
            s["log"].append(msg)
        else:
            msg = f"Computer discarded {card['rank']}{card['suit']}."
            s["message"] = msg
            s["log"].append(msg)

        return _advance_turn(s)

    return s


def get_scores(state):
    player_score = hand_value(state["player_hand"])
    computer_score = hand_value(state["computer_hand"])
    caller = state["cambio_called_by"]
    penalty = 5

    if caller == "player" and player_score > computer_score:
        player_score += penalty
    elif caller == "computer" and computer_score > player_score:
        computer_score += penalty

    return player_score, computer_score
