# Rules of the game

This is the authoritative rules reference for auto-cambio's Cambio variant. It is
synthesized from the implementation in [`game/rules.py`](../game/rules.py); where the
code and this doc disagree, the code wins — please fix the doc.

It's a two-player game: **you vs. one opponent** (a human seat and an AI seat in the
web app; two AI seats in self-play).

## Goal

Hold the hand with the **lowest total point value**. When you believe you're lowest,
**call Cambio** to end the round. Lowest total wins; equal totals tie.

## The deck and card values

A standard 52-card deck (4 suits × 13 ranks). Each card is worth points by rank,
with one twist — **red Kings are negative**:

| Card | Value |
|---|---|
| Ace (A) | 1 |
| 2–10 | face value |
| Jack (J) | 11 |
| Queen (Q) | 12 |
| Black King (♠ ♣) | 13 |
| **Red King (♥ ♦)** | **−1** |

A hand's value is the sum of its cards (empty slots count as 0). Implemented in
`card_value` and `hand_value`.

## Setup

- Each player is dealt **4 cards**, laid out face-down in a 2×2 grid.
- One card is flipped up to start the **discard pile**; the rest form the **draw deck**
  (43 cards remain after the deal).
- **Peek phase:** at the start, each player may look at **2 of their 4 cards** (the
  bottom row, positions 3 and 4). Memorize them — they flip back face-down when you
  press **Start**.
- A coin flip decides who goes first (the web app alternates the starter between
  games).

> Knowledge matters: throughout the game the engine tracks which cards each player
> *knows*. You can only **snap** or make value-based decisions about cards you know.
> You learn cards by peeking (setup + 7/8/9/10 powers) and by placing a drawn card.

## A turn

On your turn you do **one** of:

### A. Draw and play
1. **Draw** one card, either from the **deck** (unknown) or the **top of the discard
   pile** (known — everyone saw it).
2. Then either:
   - **Swap** it into one of your hand positions. The card that was there goes to the
     discard pile, and you now *know* the card you just placed. (You may also place it
     into an empty slot.) **Swapping never triggers a power.**
   - **Discard** the drawn card straight to the discard pile. If that card has a
     **special rank**, you immediately use its **power** (see below) — this is the only
     way to use a power.

### B. Call Cambio
Instead of drawing, declare **Cambio** to begin the end of the round (see *Ending*).

## Snapping (out of turn)

Whenever there's a discard top, if you have a **card you know** whose **rank matches**
the top of the discard pile, you may **snap** it:

- **Snap your own card** → that card is discarded and its slot becomes empty. Snapping
  does **not** use your turn — it's a free way to shed a card (great for high cards,
  though some strategies deliberately *keep* negative red Kings).
- **Snap an opponent's card** (a card of theirs you know) → it's removed from their
  hand, then you must **give one of your own cards** to them (it's added to their
  hand). This shrinks your hand while burdening theirs.
- **Simultaneous snaps:** if both players could snap the same discard top, the engine
  resolves it with a 50/50 coin flip.

If snapping leaves a player with an **empty hand** (all four slots gone), that triggers
the end of the round — the *other* player gets one last turn, then the game scores.

## Special card powers (discard only)

Powers fire **only when you discard a drawn card** of that rank (never on a swap, and
never on a snap). You may also choose to **skip** a power.

| Card | Power | Steps |
|---|---|---|
| **7 / 8** | **Peek own** — look at one of your own cards | pick one of your cards |
| **9 / 10** | **Peek opponent** — look at one of the opponent's cards | pick one opponent card |
| **J / Q** | **Blind switch** — swap one of your cards with one of theirs, sight unseen | pick yours, then pick theirs |
| **K** | **Looking switch** — peek one of yours *and* one of theirs, then decide whether to swap them | pick yours, pick theirs, then Switch / Don't Switch |

After a blind/looking switch you (and they) generally no longer *know* the swapped
cards — except the **K** power, where you saw both, so you keep the knowledge if you
switch.

**Switch powers (J / Q / K) are blocked once Cambio has been called.** The peek powers
(7/8/9/10) still work during the final turn.

## Ending the round

The round ends one of two ways:

1. **Cambio is called.** The caller's turn ends and the **other player gets exactly one
   last turn** (they can still draw, snap, and use peek powers, but not switch powers).
   Then the game scores.
2. **A hand empties** via snapping. The other player gets one last turn, then scoring.

(There is also a safety **turn cap** in batch simulation — a game that somehow never
ends is recorded as `capped`. This doesn't happen in normal play.)

## Scoring

- Each player's score is the **sum of their hand** (red Kings subtract).
- **Cambio penalty:** the player who *called* Cambio gets **+5 points** if their total
  is **strictly greater** than the opponent's (i.e., they called without actually being
  lowest). If the caller is lowest, or it's a tie, there is **no penalty**.
- **Lowest score wins.** Equal scores are a **tie**.

Implemented in `get_scores`:

```python
caller = state["cambio_called_by"]
if caller == "player"   and player_score   > computer_score: player_score   += 5
elif caller == "computer" and computer_score > player_score: computer_score += 5
```

## Worked scoring examples

- You call Cambio with **2♠** (2) vs. opponent **9♦** (9): you're lowest, no penalty →
  **2 vs 9, you win**.
- You call Cambio with **9♠** (9) vs. opponent **2♠** (2): you called but you're higher
  → **+5 penalty → 14 vs 2, you lose badly**. Don't call unless you're confident.
- Hands tie at 5 each, you called: **no penalty → 5 vs 5, tie**.
- A red King (**−1**) plus a 2 = **1** total — negative cards are why some strategies
  hoard red Kings instead of snapping them away.

## See also

- [architecture.md](architecture.md) — how phases enforce which of these actions are
  legal when, and the exact state fields that track knowledge and powers.
- [strategies.md](strategies.md) — how the AI bots weigh drawing, snapping, gambling,
  and when to call Cambio.
