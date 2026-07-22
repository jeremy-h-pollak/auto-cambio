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
    create_initial_state, apply_move, get_scores, get_winner, special_type,
    snap_eligible_indices,
    PHASE_GAME_OVER, PHASE_PLAYER_DRAW, COMPUTER_TURN,
)

SEATS = ("player", "computer")


def _other(seat):
    return "computer" if seat == "player" else "player"


def balanced_sides(g):
    """Balanced (a_seat, starting_seat) for game `g` of a batch or pairing.

    Cycles the four (which physical seat entrant A takes) x (who moves first)
    combinations, so over any multiple of 4 games A sits in each seat half the
    time and starts half the time — exactly, rather than in expectation.

    Drawing these from `random.choice` instead leaves the four cells visibly
    uneven at realistic batch sizes: over 200 runs of n=500 the smallest cell
    averaged 113 of the 125 expected (worst case 96). The physical seat itself
    is neutral (measured seat main effect < 0.1 pts), but moving first is worth
    ~1.5-2.7 pts depending on the strategy, so the start column has to balance.

    Consumes no RNG, which also keeps the deck stream independent of the
    seat assignment.
    """
    a_seat = SEATS[g % 2]
    starting_seat = SEATS[(g // 2) % 2]
    return a_seat, starting_seat


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
    deal_index: int | None = None   # index of the fixed deal, if one was used

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
    def decided_on_cards(self):
        """Decisive game where both hands tied on score (won on card count)."""
        return self.winner_seat is not None and self.player_score == self.computer_score

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


def _snap_sweep(state, strat_by_seat, snaps, rng=random):
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
            seat = rng.choice(SEATS)
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

def play_game(strat_by_seat, starting_seat, smart_seat, seat_strategy, max_turns=1000,
              deal=None):
    """Play one game. Pass a `deals.Deal` to fix the shuffle: the deck order, the
    mid-game reshuffles and the simultaneous-snap coin flips all become functions
    of the deal, so replaying it with the seats swapped isolates strategy from
    deck luck. Without one, everything draws from global `random` as before."""
    if deal is None:
        state = create_initial_state(starting_turn=starting_seat)
        rng = random
    else:
        state = create_initial_state(starting_turn=starting_seat,
                                     deck=deal.deck, deal_seed=deal.seed)
        rng = random.Random(deal.seed)
        # Common random numbers for the strategies themselves. Every bot here draws
        # from global `random`, so without this the two mirrored games diverge on the
        # first coin flip and stop being the same deal in any useful sense. Reseeding
        # per game means both halves start from an identical stream; they still
        # diverge once the two strategies make different numbers of draws, but the
        # opening — where deck luck bites hardest — stays matched.
        random.seed(deal.seed)
    snaps = {"player": 0, "computer": 0}
    specials = {"player": Counter(), "computer": Counter()}
    actions = {"player": Counter(), "computer": Counter()}

    state = _snap_sweep(state, strat_by_seat, snaps, rng)   # opening snaps
    turns = 0
    while state["phase"] != PHASE_GAME_OVER and turns < max_turns:
        seat = state["current_turn"]
        state = _take_turn(state, seat, strat_by_seat[seat], specials, actions)
        turns += 1
        state = _snap_sweep(state, strat_by_seat, snaps, rng)

    player_score, computer_score = get_scores(state)
    winner = get_winner(state)

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
        deal_index=(deal.index if deal is not None else None),
    )


def _sim_schedule(n, duplicate, seed):
    """`n` (smart_seat, starting_seat, deal) specs for a smart-vs-opponent run.

    Independent mode walks `balanced_sides(g)`, so the four seat x who-moves-first
    cells come out exactly even rather than even in expectation. Duplicate mode
    generates `n // 2` fixed deals and plays each one twice — same deck, same
    starting seat, `smart` swapped between the two physical seats — so deck luck
    lands on both strategies equally and cancels within the pair; that schedule is
    already exactly balanced (starting seat alternates by deal, both seats emitted
    per deal).

    Neither branch consumes RNG, which keeps the deck stream independent of the
    seat assignment.
    """
    if not duplicate:
        for g in range(n):
            yield (*balanced_sides(g), None)
        return
    from .deals import make_deals
    emitted = 0
    for deal in make_deals((n + 1) // 2, seed):
        starting_seat = "player" if deal.index % 2 == 0 else "computer"
        for smart_seat in SEATS:
            if emitted >= n:
                return
            yield smart_seat, starting_seat, deal
            emitted += 1


def run_simulation(n, smart, opponent=None, seed=None, max_turns=1000, on_game=None,
                   smart_label="smart", opponent_label="random", duplicate=False):
    """Play `n` games of `smart` vs `opponent`; return (records, timing).

    `smart` and `opponent` are strategy objects/modules exposing
    choose_move / should_snap / apply_special. `opponent` defaults to the
    random strategy module.

    With `duplicate=True` the games are run as `n // 2` mirrored deal pairs — see
    `_sim_schedule` — which removes deck luck from the win-rate estimate.
    """
    if opponent is None:
        opponent = random_strategy
    if seed is not None:
        random.seed(seed)

    records = []
    t0 = time.perf_counter()
    for g, (smart_seat, starting_seat, deal) in enumerate(_sim_schedule(n, duplicate, seed)):
        other = _other(smart_seat)
        strat_by_seat = {smart_seat: smart, other: opponent}
        seat_strategy = {smart_seat: smart_label, other: opponent_label}

        rec = play_game(strat_by_seat, starting_seat, smart_seat, seat_strategy,
                        max_turns, deal=deal)
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
