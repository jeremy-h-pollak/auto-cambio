"""
Self-play simulator: runs many computer-vs-computer Cambio games and returns
per-game records for analysis.

Drives both sides directly on `rules.apply_move` rather than through
`GameEngine`. The engine runs a computer snap-check after *every* internal
`apply_move`, which gives a bot ~3x the snap opportunities a turn-boundary
player gets and skews self-play results. Here both seats get a single,
symmetric snap sweep at each turn boundary, and we skip the "start" action
(which would wipe only `player_known`) so both seats keep the symmetric
opening knowledge `[F, F, T, T]` that `create_initial_state` grants.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass, field

from . import strategy as random_strategy
from .rules import (
    create_initial_state, apply_move, get_scores, special_type,
    snap_eligible_indices,
    PHASE_GAME_OVER, PHASE_PLAYER_DRAW, COMPUTER_TURN,
)

SEATS = ("player", "computer")


def _other(seat):
    return "computer" if seat == "player" else "player"


@dataclass
class GameRecord:
    starting_seat: str
    smart_seat: str
    seat_strategy: dict           # {"player": name, "computer": name}
    winner_seat: str | None       # "player" | "computer" | None (tie)
    player_score: int
    computer_score: int
    length: int                   # turns taken
    ending: str                   # "cambio" | "empty" | "capped"
    cambio_caller: str | None     # raw state["cambio_called_by"]
    snaps: dict = field(default_factory=dict)
    specials: dict = field(default_factory=dict)     # {seat: Counter(stype -> count)}
    actions: dict = field(default_factory=dict)      # {seat: Counter(action -> count)}
    log: list = field(default_factory=list)

    @property
    def smart_won(self):
        return self.winner_seat == self.smart_seat

    @property
    def random_won(self):
        return self.winner_seat is not None and self.winner_seat != self.smart_seat

    @property
    def is_tie(self):
        return self.winner_seat is None

    @property
    def starter_won(self):
        return self.winner_seat == self.starting_seat


# ── Turn flow ──────────────────────────────────────────────────────────────

def _advance(state, seat):
    """Mirror rules._advance_turn for the manual discard path."""
    if state["cambio_called_by"] is not None:
        state["phase"] = PHASE_GAME_OVER
        state["log"].append("Game over!")
        return state
    other = _other(seat)
    state["current_turn"] = other
    state["phase"] = COMPUTER_TURN if other == "computer" else PHASE_PLAYER_DRAW
    return state


def _discard_and_resolve(state, seat, drawn, strat, specials):
    """Discard the drawn card and resolve its power uniformly for either seat."""
    state["discard_pile"].append(drawn)
    state["drawn_card"] = None
    state["log"].append(f"{seat} discarded {drawn['rank']}{drawn['suit']}.")
    stype = special_type(drawn)
    blocked = (
        stype in ("blind_switch", "looking_switch")
        and state["cambio_called_by"] is not None
    )
    if stype and not blocked:
        strat.apply_special(state, seat, stype)
        specials[seat][stype] += 1
    return _advance(state, seat)


def _take_turn(state, seat, strat, specials, actions):
    """Run one full turn for `seat`; returns the (new) state.

    Records the strategy's draw-phase choice (move1) and action-phase choice
    (move2) in `actions[seat]`. Counting only — no RNG is consumed here, so
    seeded runs stay bit-for-bit reproducible.
    """
    state["current_turn"] = seat
    move1 = strat.choose_move(state, state[f"{seat}_known"])
    actions[seat][move1["action"]] += 1
    if move1["action"] == "call_cambio":
        return apply_move(state, {"action": "call_cambio"})

    state = apply_move(state, move1)               # draw_deck / draw_discard
    if state["drawn_card"] is None:                # discard pile was empty
        state = apply_move(state, {"action": "draw_deck"})

    state["current_turn"] = seat
    drawn = state["drawn_card"]
    move2 = strat.choose_move(state, state[f"{seat}_known"])
    actions[seat][move2["action"]] += 1
    if move2["action"] == "swap":
        return apply_move(state, move2)            # apply_move advances the turn
    return _discard_and_resolve(state, seat, drawn, strat, specials)


def _snap_sweep(state, strat_by_seat, snaps):
    """Symmetric snap resolution: both seats react to the current discard top."""
    while state["phase"] != PHASE_GAME_OVER:
        eligible = {}
        for seat in SEATS:
            idxs = snap_eligible_indices(
                state[f"{seat}_hand"], state["discard_pile"], state[f"{seat}_known"],
            )
            idxs = [i for i in idxs if strat_by_seat[seat].should_snap(state, i, seat)]
            if idxs:
                eligible[seat] = idxs
        if not eligible:
            break
        if len(eligible) == 2:                     # simultaneous → coin flip
            seat = random.choice(SEATS)
        else:
            seat = next(iter(eligible))
        idx = eligible[seat][0]
        state = apply_move(
            state, {"action": "snap", "by": seat, "target": seat, "hand_index": idx}
        )
        snaps[seat] += 1
        if state["cambio_called_by"] is not None:  # a hand emptied → last turn
            break
    return state


# ── Game / batch ───────────────────────────────────────────────────────────

def play_game(strat_by_seat, starting_seat, smart_seat, seat_strategy, max_turns=1000):
    state = create_initial_state(starting_turn=starting_seat)
    snaps = {"player": 0, "computer": 0}
    specials = {"player": Counter(), "computer": Counter()}
    actions = {"player": Counter(), "computer": Counter()}

    state = _snap_sweep(state, strat_by_seat, snaps)   # opening snaps
    turns = 0
    while state["phase"] != PHASE_GAME_OVER and turns < max_turns:
        seat = state["current_turn"]
        state = _take_turn(state, seat, strat_by_seat[seat], specials, actions)
        turns += 1
        state = _snap_sweep(state, strat_by_seat, snaps)

    player_score, computer_score = get_scores(state)
    if player_score < computer_score:
        winner = "player"
    elif computer_score < player_score:
        winner = "computer"
    else:
        winner = None

    caller = state["cambio_called_by"]
    if state["phase"] != PHASE_GAME_OVER:
        ending = "capped"
    elif caller in ("player", "computer"):
        ending = "cambio"
    else:
        ending = "empty"

    return GameRecord(
        starting_seat=starting_seat,
        smart_seat=smart_seat,
        seat_strategy=seat_strategy,
        winner_seat=winner,
        player_score=player_score,
        computer_score=computer_score,
        length=turns,
        ending=ending,
        cambio_caller=caller,
        snaps=snaps,
        specials=specials,
        actions=actions,
        log=state["log"],
    )


def run_simulation(n, smart, opponent=None, seed=None, max_turns=1000, on_game=None,
                   smart_label="smart", opponent_label="random"):
    """Play `n` games of `smart` vs `opponent`; return (records, timing).

    `smart` and `opponent` are strategy objects/modules exposing
    choose_move / should_snap / apply_special. `opponent` defaults to the
    random strategy module.
    """
    if opponent is None:
        opponent = random_strategy
    if seed is not None:
        random.seed(seed)

    records = []
    t0 = time.perf_counter()
    for g in range(n):
        smart_seat = random.choice(SEATS)            # balance which seat is smart
        other = _other(smart_seat)
        strat_by_seat = {smart_seat: smart, other: opponent}
        seat_strategy = {smart_seat: smart_label, other: opponent_label}
        starting_seat = random.choice(SEATS)         # balance who moves first

        rec = play_game(strat_by_seat, starting_seat, smart_seat, seat_strategy, max_turns)
        records.append(rec)
        if on_game is not None:
            on_game(g, rec)
    elapsed = time.perf_counter() - t0

    timing = {
        "total_s": elapsed,
        "n": n,
        "per_game_ms": (elapsed / n * 1000) if n else 0.0,
        "games_per_s": (n / elapsed) if elapsed else 0.0,
    }
    return records, timing
