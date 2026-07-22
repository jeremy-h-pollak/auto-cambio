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
import random
import time
from dataclasses import dataclass, field

from . import strategies
from . import strategy as random_strategy
from .strategies_advanced import ADVANCED, get_advanced
from .simulator import play_game, balanced_sides

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
    # Duplicate mode only: A's score (win=1, tie=0.5) summed over the two mirrored
    # games of each deal, so each entry is in [0, 2]. The resampling unit for the
    # bootstrap — a deal pair, not a game.
    deal_scores: list = field(default_factory=list)


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
    duplicate: bool = False         # were games run as mirrored duplicate deals?
    n_deals: int = 0                # deals per pairing (k // 2 in duplicate mode)



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

    Shared with self-play — see `simulator.balanced_sides`. Note the four cells
    only come out exactly even when `k % 4 == 0`; for other `k` the marginals are
    still as balanced as possible (each ceil(k/2)), leaving at most one surplus
    first-move game per pairing — worth ~0.08 pts of score rate, under 1 Elo.
    """
    return balanced_sides(g)


def _schedule(k, deals_):
    """The `k` games of one pairing as (a_seat, starting_seat, deal, deal_index).

    Without deals this is the original independent-shuffle schedule: `_sides(g)`
    cycles the four seat x tempo combinations and every game gets a fresh shuffle.

    With deals it is a **duplicate** schedule: each deal is played twice with the
    deck order *and* the starting seat held fixed and only the entrants swapped, so
    across the pair each entrant plays both sides of the same deal. Whatever that
    deal was worth is handed to both of them and cancels; what survives is the part
    of the result the strategies actually caused. Starting seat alternates by deal,
    which keeps the same seat/tempo balance `_sides` gave.

    Each pairing gets its **own** deal set (see `_pair_deals`). Sharing one set
    field-wide is tempting — every entrant measured on identical hands — but it
    correlates all the pairings in a run, so deal luck no longer averages out across
    them; measured, that inflated run-to-run rating variance ~3x. Independent deal
    sets per pairing keep that averaging and still get the within-pair mirror.
    """
    if not deals_:
        return [(*_sides(g), None, None) for g in range(k)]
    out = []

    for m, deal in enumerate(deals_):
        starting_seat = "player" if m % 2 == 0 else "computer"
        for a_seat in ("player", "computer"):
            out.append((a_seat, starting_seat, deal, m))
    return out


def _pair_deals(k, duplicate, seed, idx):
    """The `k // 2` deals pairing `idx` plays, or `()` outside duplicate mode.

    Derived from `(seed, idx)` so runs stay reproducible while each pairing draws an
    independent deal set.
    """
    if not duplicate:
        return ()
    from .deals import make_deals
    return make_deals(k // 2, None if seed is None else f"{seed}:{idx}")


def run_tournament(field_, k, seed=None, max_turns=1000, on_pair=None, duplicate=False):
    """Play every pairing `k` times; return a fully-rated TournamentResult.

    With `duplicate=True` the `k` games become `k // 2` duplicate-bridge deal pairs
    (see `_schedule`): each deal is played twice with the entrants swapped, so the
    deal is worth the same to both and cancels. `k` must be even.
    """
    if seed is not None:
        random.seed(seed)
    if duplicate and k % 2:
        raise ValueError(f"duplicate mode needs an even -k (got {k}): "
                         "each deal is played twice with the seats swapped")

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
    n_deals = k // 2 if duplicate else 0
    t0 = time.perf_counter()
    for idx, (i, j) in enumerate(pair_list):
        a_wins = b_wins = tie = a_starts = 0
        deal_scores = [0.0] * n_deals
        for a_seat, starting_seat, deal, m in _schedule(k, _pair_deals(k, duplicate, seed, idx)):
            b_seat = OTHER[a_seat]
            if starting_seat == a_seat:
                a_starts += 1
            strat_by_seat = {a_seat: field_[i].strat, b_seat: field_[j].strat}
            seat_strategy = {a_seat: field_[i].key, b_seat: field_[j].key}
            rec = play_game(strat_by_seat, starting_seat, a_seat, seat_strategy,
                            max_turns, deal=deal)
            length_sum += rec.length
            if rec.winner_seat is None:
                tie += 1
                a_score = 0.5
            elif rec.winner_seat == a_seat:
                a_wins += 1
                a_score = 1.0
            else:
                b_wins += 1
                a_score = 0.0
            if m is not None:
                deal_scores[m] += a_score

        win[i][j] = a_wins + 0.5 * tie
        win[j][i] = b_wins + 0.5 * tie
        ngames[i][j] = ngames[j][i] = k
        pairs[(i, j)] = PairResult(i, j, a_wins, b_wins, tie, a_starts, deal_scores)
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
        duplicate=duplicate, n_deals=n_deals,
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


def bootstrap_ratings(result, n_boot=2000, ci=0.95, seed=None):
    """Percentile-bootstrap confidence intervals for each entrant's Elo rating.

    The nonparametric pairwise bootstrap: each replicate resamples every pairing's
    `k` games with replacement — equivalently, draws fresh `(a_wins, b_wins, ties)`
    counts from a multinomial with the observed proportions — then refits
    Bradley-Terry and maps to Elo against the same Random anchor `run_tournament`
    used. No games are re-simulated; only the (cheap, pure) matrix fits re-run.

    For a duplicate-deal tournament the unit is the **deal pair**, not the game: the
    two mirrored games of a deal share a deck and are not independent, so replicates
    resample `PairResult.deal_scores` (a block bootstrap). This is what lets the
    bands actually narrow — the paired design removes deck variance, and the block
    resample is what reports the narrower spread honestly.

    Returns `{index: {"lo", "hi", "median", "samples"}}` where `lo`/`hi` are the
    `(1±ci)/2` percentile bounds of that entrant's rating across replicates. With
    Random anchored, its band is the degenerate `[1500, 1500]` by construction.
    """
    rng = random.Random(seed)
    field_ = result.entrants
    n = len(field_)
    anchor = next((m for m, e in enumerate(field_) if e.key == RANDOM_KEY), None)
    pairs = list(result.pairs.values())

    samples = {i: [] for i in range(n)}
    for _ in range(n_boot):
        win = [[0.0] * n for _ in range(n)]
        ngames = [[0] * n for _ in range(n)]
        for pr in pairs:
            total = pr.a_wins + pr.b_wins + pr.ties
            if total <= 0:
                continue
            if pr.deal_scores:
                # Duplicate mode: games within a deal are *not* independent — the two
                # mirrored halves share a deck — so resample whole deals (a block
                # bootstrap). Resampling games instead would treat the paired design
                # as if it were independent and overstate the precision.
                d = pr.deal_scores
                a_score = sum(d[rng.randrange(len(d))] for _ in range(len(d)))
                win[pr.i][pr.j] = a_score
                win[pr.j][pr.i] = total - a_score
            else:
                draws = rng.choices((0, 1, 2),
                                    weights=(pr.a_wins, pr.b_wins, pr.ties), k=total)
                a = draws.count(0)
                b = draws.count(1)
                t = total - a - b
                win[pr.i][pr.j] = a + 0.5 * t
                win[pr.j][pr.i] = b + 0.5 * t
            ngames[pr.i][pr.j] = ngames[pr.j][pr.i] = total
        ratings = to_elo(bradley_terry(win, ngames), anchor_index=anchor)
        for i in range(n):
            samples[i].append(ratings[i])

    lo_q = (1.0 - ci) / 2.0
    hi_q = (1.0 + ci) / 2.0
    out = {}
    for i in range(n):
        s = sorted(samples[i])
        out[i] = {
            "lo": _quantile(s, lo_q),
            "hi": _quantile(s, hi_q),
            "median": _quantile(s, 0.5),
            "samples": s,
        }
    return out


def _quantile(sorted_vals, q):
    """Linear-interpolated quantile of an already-sorted list (empty -> 0.0)."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


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
