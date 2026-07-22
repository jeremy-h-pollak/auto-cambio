"""
Duplicate deals — pre-generated shuffles replayed under mirrored seats.

Deck luck is the dominant noise source in Cambio: a bot handed 1-2-A-3 beats a
better bot handed K-Q-J-10 most of the time, and with independent shuffles that
luck is a coin the rating has to average out over thousands of games. This is the
duplicate-bridge fix — the *same* deal is played twice with the two entrants
swapped, so whatever the deal was worth is handed to both sides and cancels in
the pair.

A `Deal` is a frozen 52-card order plus a seed for the randomness a game consumes
*after* the deal (mid-game reshuffles, simultaneous-snap coin flips). Both games
of a mirrored pair get the same `Deal`, so those streams line up too and the only
thing that differs between them is which entrant sat where.

`make_deals(n, seed)` is deterministic given `seed` and independent of the global
`random` stream, so the same deal set can be shared across every pairing of a
tournament — every entrant then faces an identical set of hands.
"""

import random
from dataclasses import dataclass

from .rules import SUITS, RANKS

_SEED_SPACE = 2 ** 32


@dataclass(frozen=True)
class Deal:
    """One fixed shuffle. `deck` is the dealt order; see `rules.create_initial_state`
    for the slicing (hands = deck[:4] / deck[4:8], discard top = deck[8])."""
    index: int
    deck: tuple
    seed: int


def make_deals(n, seed=None):
    """`n` deterministic deals drawn from a local RNG seeded with `seed`."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        deck = [{"suit": s, "rank": r} for s in SUITS for r in RANKS]
        rng.shuffle(deck)
        out.append(Deal(index=i, deck=tuple(deck), seed=rng.randrange(_SEED_SPACE)))
    return out
