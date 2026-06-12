import random
import copy

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RED_SUITS = {"♥", "♦"}

PHASE_PEEK = "peek"
PHASE_PLAYER_DRAW = "player_draw"
PHASE_PLAYER_ACTION = "player_action"
PHASE_PLAYER_SPECIAL = "player_special"
PHASE_GAME_OVER = "game_over"
COMPUTER_TURN = "computer_turn"


def card_value(card):
    rank = card["rank"]
    if rank == "A": return 1
    if rank == "J": return 11
    if rank == "Q": return 12
    if rank == "K": return -1 if card["suit"] in RED_SUITS else 13
    return int(rank)


def hand_value(hand):
    return sum(card_value(c) for c in hand if c is not None)


def hand_size(hand):
    """Cards still held; None slots are emptied positions (after a snap)."""
    return sum(1 for c in hand if c is not None)


def is_red(card):
    return card["suit"] in RED_SUITS


def snap_eligible_indices(hand, discard_pile, known=None):
    """Indices of hand cards whose rank matches the top of the discard pile.
    If known is provided, only includes positions the owner actually knows."""
    if not discard_pile or not hand:
        return []
    top_rank = discard_pile[-1]["rank"]
    return [
        i for i, c in enumerate(hand)
        if c is not None
        and c["rank"] == top_rank
        and (known is None or (i < len(known) and known[i]))
    ]


def opp_snap_eligible_indices(computer_hand, player_opponent_known, discard_pile):
    """Indices of computer hand cards the player knows and that match the discard top."""
    if not discard_pile or not computer_hand:
        return []
    top_rank = discard_pile[-1]["rank"]
    return [
        i for i, c in enumerate(computer_hand)
        if c is not None
        and c["rank"] == top_rank
        and i < len(player_opponent_known)
        and player_opponent_known[i]
    ]


def special_type(card):
    r = card["rank"]
    if r in ("7", "8"):   return "peek_own"
    if r in ("9", "10"):  return "peek_opponent"
    if r in ("J", "Q"):   return "blind_switch"
    if r == "K":          return "looking_switch"
    return None


def special_message(stype, step):
    if stype == "peek_own":
        return "Special (7/8): Click one of your cards to peek at it."
    if stype == "peek_opponent":
        return "Special (9/10): Click one of the computer's cards to peek at it."
    if stype == "blind_switch":
        if step == 1: return "Special (J/Q): Click one of YOUR cards to swap blindly."
        if step == 2: return "Special (J/Q): Now click one of the COMPUTER's cards to swap with."
    if stype == "looking_switch":
        if step == 1: return "Special (K): Click one of YOUR cards to peek at."
        if step == 2: return "Special (K): Now click one of the COMPUTER's cards to peek at."
        if step == 3: return "Special (K): Switch these two cards?"
    if stype == "give_card":
        return "Snap! Click one of YOUR cards to give to the computer."
    return ""


def _make_deck():
    deck = [{"suit": s, "rank": r} for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def create_initial_state(starting_turn="player"):
    deck = _make_deck()
    player_hand   = deck[:4]
    computer_hand = deck[4:8]
    discard_pile  = [deck[8]]
    remaining     = deck[9:]
    who_first = "You go first." if starting_turn == "player" else "Computer goes first."
    return {
        "phase":                PHASE_PEEK,
        "deck":                 remaining,
        "discard_pile":         discard_pile,
        "player_hand":          player_hand,
        "computer_hand":        computer_hand,
        "drawn_card":           None,
        "player_known":         [False, False, True, True],
        "computer_known":       [False, False, True, True],
        "player_opponent_known":[False, False, False, False],
        # Transient reveal: indices shown face-up for exactly one response cycle,
        # then cleared at the start of the next apply_move call.
        "player_reveal":        [],
        "player_opponent_reveal":[],
        "computer_acted":       [],  # computer hand positions acted on this turn
        "player_touched":       [],  # player hand positions computer affected this turn
        "special_action":       None,   # {"type", "step", "picks"} during player_special
        "cambio_called_by":     None,
        "current_turn":         starting_turn,
        "message":              f"Peek at your last 2 cards, then press Start. ({who_first})",
        "log":                  [],
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
    """Called after a full turn action (swap / discard / special resolved)."""
    if state["cambio_called_by"] is not None:
        state["phase"] = PHASE_GAME_OVER
        state["message"] = "Game over! Revealing all cards…"
        state["log"].append("Game over!")
        return state

    if state["current_turn"] == "player":
        state["current_turn"] = "computer"
        state["phase"] = COMPUTER_TURN
    else:
        state["current_turn"] = "player"
        state["phase"] = PHASE_PLAYER_DRAW
        state["message"] = "Your turn: draw a card or call Cambio."
    return state


def _trigger_player_special(s, card):
    """Enter player_special phase if the discarded card has a power."""
    stype = special_type(card)
    if not stype:
        return None
    # Switch powers blocked after cambio
    if stype in ("blind_switch", "looking_switch") and s["cambio_called_by"] is not None:
        return None
    s["special_action"] = {"type": stype, "step": 1, "picks": []}
    s["phase"] = PHASE_PLAYER_SPECIAL
    s["message"] = special_message(stype, 1)
    return s


# ── Move handlers ─────────────────────────────────────────────────────────────

# Actions that mark the start of a new player turn — the only moment reveals clear.
# Computer actions must NOT clear reveals so the player sees their card for the
# full turn cycle (their action + computer's response + until they draw again).
_CLEAR_REVEAL_ON = {"start", "draw_deck", "draw_discard", "call_cambio"}


def apply_move(state, move):
    """Pure function: returns new state after applying move. Never mutates input."""
    s = _clone(state)
    action = move["action"]
    if action in _CLEAR_REVEAL_ON and state["current_turn"] == "player":
        s["player_reveal"] = []
        s["player_opponent_reveal"] = []
        s["computer_acted"] = []
        s["player_touched"] = []

    if action == "start":
        s["player_known"] = [False] * len(s["player_hand"])
        if s["current_turn"] == "computer":
            s["phase"] = COMPUTER_TURN
            s["message"] = "Computer goes first."
        else:
            s["phase"] = PHASE_PLAYER_DRAW
            s["message"] = "Your turn: draw a card or call Cambio."
        return s

    if action == "call_cambio":
        s["cambio_called_by"] = s["current_turn"]
        who = "You" if s["current_turn"] == "player" else "Computer"
        msg = f"{who} called Cambio! The other player gets one last turn."
        s["message"] = msg
        s["log"].append(msg)
        if s["current_turn"] == "player":
            s["current_turn"] = "computer"
            s["phase"] = COMPUTER_TURN
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
        if s["drawn_card"] is None:
            return s  # no drawn card to swap in (stale/double click) — ignore safely
        idx = move["hand_index"]
        hk  = "player_hand"   if s["current_turn"] == "player" else "computer_hand"
        kk  = "player_known"  if s["current_turn"] == "player" else "computer_known"
        old = s[hk][idx]
        s[hk][idx] = s["drawn_card"]
        if old is not None:
            s["discard_pile"].append(old)
        s[kk][idx] = True
        s["drawn_card"] = None
        if s["current_turn"] == "player":
            if old is not None:
                msg = f"You swapped position {idx+1} (discarded {old['rank']}{old['suit']})."
            else:
                msg = f"You placed drawn card at position {idx+1}."
        else:
            s["computer_acted"] = [idx]
            if old is not None:
                msg = f"Computer swapped position {idx+1} (discarded {old['rank']}{old['suit']})."
            else:
                msg = f"Computer placed drawn card at position {idx+1}."
        s["message"] = msg
        s["log"].append(msg)
        return _advance_turn(s)

    if action == "discard_drawn":
        card = s["drawn_card"]
        if card is None:
            return s  # no drawn card to discard (stale/double click) — ignore safely
        s["discard_pile"].append(card)
        s["drawn_card"] = None
        if s["current_turn"] == "player":
            msg = f"You discarded {card['rank']}{card['suit']}."
            s["message"] = msg
            s["log"].append(msg)
            result = _trigger_player_special(s, card)
            if result is not None:
                return result
        else:
            msg = f"Computer discarded {card['rank']}{card['suit']}."
            s["message"] = msg
            s["log"].append(msg)
        return _advance_turn(s)

    # ── Snap: discard a matching hand card (no turn used) ────────────────────
    if action == "snap":
        by     = move.get("by", "player")
        target = move.get("target", by)  # who owns the card being snapped
        idx    = move["hand_index"]

        if by == "player" and target == "computer":
            # Player snaps a card from computer's hand (must know it)
            comp_hand = s["computer_hand"]
            if (not s["discard_pile"]
                    or comp_hand[idx] is None
                    or comp_hand[idx]["rank"] != s["discard_pile"][-1]["rank"]
                    or idx >= len(s["player_opponent_known"])
                    or not s["player_opponent_known"][idx]):
                return s
            card = comp_hand[idx]
            comp_hand[idx] = None
            s["computer_known"][idx] = False
            s["player_opponent_known"][idx] = False
            s["discard_pile"].append(card)
            msg = (f"You snapped computer's position {idx+1} "
                   f"({card['rank']}{card['suit']})! Give one of your cards to the computer.")
            s["message"] = msg
            s["log"].append(msg)
            s["special_action"] = {"type": "give_card", "step": 1, "picks": []}
            s["phase"] = PHASE_PLAYER_SPECIAL
            s["message"] = special_message("give_card", 1)
            s["log"][-1] = msg  # keep the snap message; message bar shows give_card prompt
            return s

        # Normal snap: `by` sets their own card to None (position preserved)
        hk  = f"{by}_hand"
        kk  = f"{by}_known"
        hand = s[hk]
        if hand[idx] is None:
            return s
        if not s["discard_pile"] or hand[idx]["rank"] != s["discard_pile"][-1]["rank"]:
            return s
        if idx >= len(s[kk]) or not s[kk][idx]:
            return s  # must know the card to snap it
        card = hand[idx]
        hand[idx] = None
        s[kk][idx] = False
        if by == "computer":
            s["player_opponent_known"][idx] = False
        s["discard_pile"].append(card)
        msg = f"{'You snapped' if by == 'player' else 'Computer snapped'} {card['rank']}{card['suit']}!"
        s["message"] = msg
        s["log"].append(msg)
        # Empty hand → last turn for the other player
        if all(c is None for c in s[hk]):
            s["cambio_called_by"] = f"{by}_empty"
            whose = "Your" if by == "player" else "Computer's"
            end_msg = f"{whose} hand is empty! The other player gets one last turn."
            s["message"] = end_msg
            s["log"].append(end_msg)
            other = "computer" if by == "player" else "player"
            if other == "computer":
                s["current_turn"] = "computer"
                s["phase"] = COMPUTER_TURN
            else:
                s["current_turn"] = "player"
                s["phase"] = PHASE_PLAYER_DRAW
        return s

    # ── Special ability: player picks a card ─────────────────────────────────
    if action == "pick_card":
        sa    = s["special_action"]
        if sa is None:
            return s  # no special in progress (stale/double click) — ignore safely
        owner = move["owner"]
        idx   = move["hand_index"]
        card  = s["player_hand"][idx] if owner == "player" else s["computer_hand"][idx]
        if card is None:
            return s  # can't act on an empty slot
        stype = sa["type"]
        step  = sa["step"]

        if stype == "peek_own":
            s["player_known"][idx] = True
            s["player_reveal"].append(idx)
            msg = f"You peeked at your position {idx+1}: {card['rank']}{card['suit']}."
            s["message"] = msg; s["log"].append(msg)
            s["special_action"] = None
            return _advance_turn(s)

        if stype == "peek_opponent":
            s["player_opponent_known"][idx] = True
            s["player_opponent_reveal"].append(idx)
            msg = f"You peeked at computer's position {idx+1}: {card['rank']}{card['suit']}."
            s["message"] = msg; s["log"].append(msg)
            s["special_action"] = None
            return _advance_turn(s)

        if stype == "blind_switch":
            if step == 1:
                sa["picks"].append({"owner": "player", "index": idx})
                sa["step"] = 2
                s["message"] = special_message("blind_switch", 2)
                return s
            if step == 2:
                my_idx   = sa["picks"][0]["index"]
                my_card  = s["player_hand"][my_idx]
                opp_card = s["computer_hand"][idx]
                s["player_hand"][my_idx]   = opp_card
                s["computer_hand"][idx]    = my_card
                s["player_known"][my_idx]  = False  # blind: don't know new card
                s["computer_known"][idx]   = False
                s["player_opponent_known"][idx] = False
                msg = f"You blind-switched your position {my_idx+1} with computer's position {idx+1}."
                s["message"] = msg; s["log"].append(msg)
                s["special_action"] = None
                return _advance_turn(s)

        if stype == "looking_switch":
            if step == 1:
                s["player_known"][idx] = True
                s["player_reveal"].append(idx)
                sa["picks"].append({"owner": "player", "index": idx})
                sa["step"] = 2
                s["message"] = special_message("looking_switch", 2)
                return s
            if step == 2:
                s["player_opponent_known"][idx] = True
                s["player_opponent_reveal"].append(idx)
                sa["picks"].append({"owner": "computer", "index": idx})
                sa["step"] = 3
                s["message"] = special_message("looking_switch", 3)
                return s

        if stype == "give_card":
            card = s["player_hand"][idx]
            s["player_hand"][idx] = None
            s["player_known"][idx] = False
            s["computer_hand"].append(card)
            s["computer_known"].append(False)
            s["player_opponent_known"].append(True)
            msg = f"You gave position {idx+1} ({card['rank']}{card['suit']}) to the computer."
            s["message"] = msg
            s["log"].append(msg)
            s["special_action"] = None
            if all(c is None for c in s["player_hand"]):
                s["cambio_called_by"] = "player_empty"
                end_msg = "Your hand is empty! The computer gets one last turn."
                s["message"] = end_msg
                s["log"].append(end_msg)
                s["current_turn"] = "computer"
                s["phase"] = COMPUTER_TURN
            else:
                s["phase"] = PHASE_PLAYER_DRAW
            return s

        return s

    # ── Special ability: decide whether to switch (K) ────────────────────────
    if action == "decide_switch":
        sa        = s["special_action"]
        if sa is None:
            return s  # no special in progress (stale/double click) — ignore safely
        do_switch = move["do_switch"]
        my_idx    = sa["picks"][0]["index"]
        their_idx = sa["picks"][1]["index"]
        if do_switch:
            my_card  = s["player_hand"][my_idx]
            opp_card = s["computer_hand"][their_idx]
            s["player_hand"][my_idx]              = opp_card
            s["computer_hand"][their_idx]         = my_card
            s["player_known"][my_idx]             = True
            s["player_opponent_known"][their_idx] = True
            msg = f"You switched your position {my_idx+1} with computer's position {their_idx+1}."
        else:
            msg = "You chose not to switch."
        s["message"] = msg; s["log"].append(msg)
        s["special_action"] = None
        return _advance_turn(s)

    # ── Skip special ability ─────────────────────────────────────────────────
    if action == "skip_special":
        if s["special_action"] is None:
            return s  # nothing to skip (stale/double click) — ignore safely
        s["special_action"] = None
        return _advance_turn(s)

    return s


def get_scores(state):
    player_score   = hand_value(state["player_hand"])
    computer_score = hand_value(state["computer_hand"])
    caller = state["cambio_called_by"]
    penalty = 5
    if caller == "player" and player_score > computer_score:
        player_score += penalty
    elif caller == "computer" and computer_score > player_score:
        computer_score += penalty
    return player_score, computer_score


def get_winner(state):
    """Winning seat ("player"/"computer") or None for a true tie.

    Lowest score wins. A tie on score is broken in favour of the hand holding
    MORE cards; only an equal score AND equal card count is a true tie.
    """
    player_score, computer_score = get_scores(state)
    if player_score != computer_score:
        return "player" if player_score < computer_score else "computer"
    p, c = hand_size(state["player_hand"]), hand_size(state["computer_hand"])
    if p != c:
        return "player" if p > c else "computer"
    return None
