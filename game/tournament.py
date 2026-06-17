"""
Round-robin tournament across every Cambio strategy.

Each unordered pair of entrants plays `k` games with balanced sides (each
entrant starts half the games and occupies each physical seat half the time),
driven at the rules level through `simulator.play_game` so both seats get the
symmetric snap handling self-play needs. Only the win/loss/tie outcome is kept —
margins are ignored.

Outcomes are fit to a Bradley-Terry model (the maximum-likelihood pairwise-
comparison model, the principled choice for a complete round-robin) via the
Hunter (2004) minorization-maximization iteration, then mapped onto an Elo-style
scale. Ties count as half a win to each side. A small symmetric prior (`alpha`
pseudo wins+losses per played pair) keeps every strength finite even if a
strategy sweeps or never wins.
"""

import itertools
import math
import time
from dataclasses import dataclass, field

from . import strategies
from . import strategy as random_strategy
from .strategies_advanced import ADVANCED, get_advanced
from .simulator import play_game

OTHER = {"player": "computer", "computer": "player"}

RANDOM_KEY = "random"
ELO_SCALE = 400.0          # rating points per decade of strength ratio (Elo convention)
ANCHOR_RATING = 1500.0     # Random (or the field mean, if absent) sits here
BT_ALPHA = 0.5             # smoothing: pseudo wins+losses added to each played pair


@dataclass
class Entrant:
    key: str
    name: str
    strat: object          # exposes choose_move / should_snap / apply_special


@dataclass
class PairResult:
    i: int                 # index of entrant A
    j: int                 # index of entrant B
    a_wins: int
    b_wins: int
    ties: int
    a_starts: int          # games in which A moved first (balance check)


@dataclass
class TournamentResult:
    entrants: list
    k: int
    seed: int | None
    max_turns: int
    win: list                       # win[i][j] = fractional wins of i over j (tie = 0.5)
    ngames: list                    # ngames[i][j] = games played between i and j
    pairs: dict                     # (i, j) -> PairResult, i < j
    wins: list                      # per-entrant decisive wins
    losses: list                    # per-entrant decisive losses
    ties: list                      # per-entrant ties
    games: list                     # per-entrant total games
    strengths: dict = field(default_factory=dict)   # index -> BT strength
    ratings: dict = field(default_factory=dict)      # index -> Elo-style rating
    total_games: int = 0
    total_ties: int = 0
    mean_length: float = 0.0
    timing: dict = field(default_factory=dict)


# ── Entrants ─────────────────────────────────────────────────────────────────

def _catalog():
    """All non-LLM entrants keyed by their key (profiles, advanced, Random)."""
    cat = {key: Entrant(key, strategies.PROFILES[key].name, strategies.get(key))
           for key in strategies.PROFILES}
    cat.update({key: Entrant(key, ADVANCED[key].name, get_advanced(key))
                for key in ADVANCED})
    cat[RANDOM_KEY] = Entrant(RANDOM_KEY, "Random", random_strategy)
    return cat


def entrants(include_random=True, include_llm=False, llm_model=None, llm_snaps=False,
             llm_keys=(), keys=None):
    """All competitors: the 15 named profiles, the 5 advanced strategies, plus
    Random. Pass `keys` (a list of entrant keys, including "random") to use a
    specific subset of those in that order instead of the full field. OpenRouter
    LLM competitors are opt-in (each makes a live API call per decision):
    `include_llm` adds the generic LLM entrant, and `llm_keys` adds the named ones
    (e.g. "kimi", "haiku" from game/llm_opponents.NAMED_LLM_OPPONENTS), each as a
    distinct entrant with its own model."""
    if keys is not None:
        cat = _catalog()
        field_ = []
        for k in keys:
            if k not in cat:
                raise ValueError(
                    f"unknown strategy key {k!r}; choose from {sorted(cat)}")
            field_.append(cat[k])
    else:
        field_ = [
            Entrant(key, strategies.PROFILES[key].name, strategies.get(key))
            for key in strategies.PROFILES
        ]
        field_ += [
            Entrant(key, ADVANCED[key].name, get_advanced(key))
            for key in ADVANCED
        ]
        if include_random:
            field_.append(Entrant(RANDOM_KEY, "Random", random_strategy))
    if include_llm:
        from .strategy_llm import get_llm_strategy, LLMStrategy
        field_.append(Entrant(LLMStrategy.key, LLMStrategy.name,
                              get_llm_strategy(model=llm_model, llm_snaps=llm_snaps)))
    if llm_keys:
        from .strategy_llm import get_llm_strategy
        from .llm_opponents import NAMED_LLM_OPPONENTS, llm_model as named_model
        for key in llm_keys:
            field_.append(Entrant(key, NAMED_LLM_OPPONENTS[key]["name"],
                                  get_llm_strategy(model=named_model(key), llm_snaps=llm_snaps)))
    return field_


# ── Round-robin ──────────────────────────────────────────────────────────────

def _sides(g):
    """Balanced (a_seat, starting_seat) for game `g` of a pairing.

    Cycles the four (which seat A takes) x (who starts) combinations, so over any
    multiple of 4 games each entrant starts half the time and sits in each seat
    half the time. Seat is symmetric at the rules level; the starting-player
    balance is the one that materially removes first-move bias.
    """
    a_seat = "player" if g % 2 == 0 else "computer"
    starting_seat = "player" if (g // 2) % 2 == 0 else "computer"
    return a_seat, starting_seat


def run_tournament(field_, k, seed=None, max_turns=1000, on_pair=None):
    """Play every pairing `k` times; return a fully-rated TournamentResult."""
    if seed is not None:
        import random
        random.seed(seed)

    n = len(field_)
    win = [[0.0] * n for _ in range(n)]
    ngames = [[0] * n for _ in range(n)]
    wins = [0] * n
    losses = [0] * n
    ties = [0] * n
    games = [0] * n
    pairs = {}
    length_sum = 0

    pair_list = list(itertools.combinations(range(n), 2))
    t0 = time.perf_counter()
    for idx, (i, j) in enumerate(pair_list):
        a_wins = b_wins = tie = a_starts = 0
        for g in range(k):
            a_seat, starting_seat = _sides(g)
            b_seat = OTHER[a_seat]
            if starting_seat == a_seat:
                a_starts += 1
            strat_by_seat = {a_seat: field_[i].strat, b_seat: field_[j].strat}
            seat_strategy = {a_seat: field_[i].key, b_seat: field_[j].key}
            rec = play_game(strat_by_seat, starting_seat, a_seat, seat_strategy, max_turns)
            length_sum += rec.length
            if rec.winner_seat is None:
                tie += 1
            elif rec.winner_seat == a_seat:
                a_wins += 1
            else:
                b_wins += 1

        win[i][j] = a_wins + 0.5 * tie
        win[j][i] = b_wins + 0.5 * tie
        ngames[i][j] = ngames[j][i] = k
        pairs[(i, j)] = PairResult(i, j, a_wins, b_wins, tie, a_starts)
        wins[i] += a_wins; losses[i] += b_wins; ties[i] += tie; games[i] += k
        wins[j] += b_wins; losses[j] += a_wins; ties[j] += tie; games[j] += k
        if on_pair is not None:
            on_pair(idx, len(pair_list), field_[i], field_[j])
    elapsed = time.perf_counter() - t0

    strengths = bradley_terry(win, ngames)
    anchor = next((m for m, e in enumerate(field_) if e.key == RANDOM_KEY), None)
    ratings = to_elo(strengths, anchor_index=anchor)

    total_games = len(pair_list) * k
    total_ties = sum(ties) // 2          # each tie is double-counted across the pair
    return TournamentResult(
        entrants=field_, k=k, seed=seed, max_turns=max_turns,
        win=win, ngames=ngames, pairs=pairs,
        wins=wins, losses=losses, ties=ties, games=games,
        strengths=strengths, ratings=ratings,
        total_games=total_games, total_ties=total_ties,
        mean_length=(length_sum / total_games if total_games else 0.0),
        timing={
            "total_s": elapsed,
            "games_per_s": (total_games / elapsed) if elapsed else 0.0,
            "pairs": len(pair_list),
        },
    )


# ── Rating ───────────────────────────────────────────────────────────────────

def bradley_terry(win, ngames, alpha=BT_ALPHA, max_iter=1000, tol=1e-10):
    """Bradley-Terry strengths from a win matrix via the Hunter (2004) MM update.

    `win[i][j]` is i's fractional wins over j (ties counted as 0.5); `ngames[i][j]`
    is the number of games the pair played. A symmetric prior of `alpha` pseudo
    wins and `alpha` pseudo losses is added to every *played* pair so that no
    strength runs to 0 or infinity. Returns {index: strength}, normalized to a
    geometric mean of 1.
    """
    n = len(win)
    wins_total = [0.0] * n                 # regularized win totals W_i
    npair = [[0.0] * n for _ in range(n)]  # regularized games per pair
    for i in range(n):
        for j in range(n):
            if i != j and ngames[i][j] > 0:
                wins_total[i] += win[i][j] + alpha
                npair[i][j] = ngames[i][j] + 2 * alpha

    p = [1.0] * n
    for _ in range(max_iter):
        nxt = [0.0] * n
        for i in range(n):
            denom = 0.0
            for j in range(n):
                if i != j and npair[i][j]:
                    denom += npair[i][j] / (p[i] + p[j])
            nxt[i] = wins_total[i] / denom if denom else p[i]
        gm = math.exp(sum(math.log(x) for x in nxt) / n)   # fix scale: geo-mean = 1
        nxt = [x / gm for x in nxt]
        diff = max(abs(a - b) for a, b in zip(nxt, p))
        p = nxt
        if diff < tol:
            break
    return {i: p[i] for i in range(n)}


def to_elo(strengths, anchor_index=None, anchor_rating=ANCHOR_RATING, scale=ELO_SCALE):
    """Map BT strengths onto an Elo-style scale.

    `rating_i = anchor_rating + scale * log10(p_i / p_ref)`. With `anchor_index`
    set, that entrant lands exactly at `anchor_rating`; otherwise the field's
    geometric-mean strength is the reference, centering the field at `anchor_rating`.
    """
    if anchor_index is not None and anchor_index in strengths:
        ref = strengths[anchor_index]
    else:
        ref = math.exp(sum(math.log(p) for p in strengths.values()) / len(strengths))
    return {i: anchor_rating + scale * math.log10(p / ref) for i, p in strengths.items()}


def rankings(result):
    """Per-entrant rows sorted by rating (descending), each tagged with `rank`."""
    rows = []
    for i, e in enumerate(result.entrants):
        g = result.games[i]
        rows.append({
            "index": i,
            "key": e.key,
            "name": e.name,
            "rating": result.ratings[i],
            "strength": result.strengths[i],
            "win_pct": (100.0 * result.wins[i] / g) if g else 0.0,
            "score_pct": (100.0 * (result.wins[i] + 0.5 * result.ties[i]) / g) if g else 0.0,
            "wins": result.wins[i],
            "losses": result.losses[i],
            "ties": result.ties[i],
            "games": g,
        })
    rows.sort(key=lambda r: r["rating"], reverse=True)
    for rank, r in enumerate(rows, 1):
        r["rank"] = rank
    return rows
