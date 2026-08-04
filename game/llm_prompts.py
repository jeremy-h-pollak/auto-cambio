"""
Versioned system prompts for the LLM strategy (`game/strategy_llm.py`).

Keeping the prompts here — out of the strategy — makes a prompt change a shippable,
*measurable* thing: each version is a named entrant, so two versions can meet in
the same tournament and the rating difference is attributable to the prompt alone.

  * **v1** — rules only. The original prompt: the model is told how Cambio works
    and what it legitimately knows, and nothing about how to play well.
  * **opus** — rules + a log-derived playbook authored by Claude Opus after
    reviewing 24 full game transcripts (the top hand-written bot at 81% vs
    Random) and 92 real Gemini Flash Lite decisions made under v1. Every rule
    targets an observed failure: 13 of 16 rejected replies tried to refill an
    empty slot; the discard top was taken once in 14 draws (passing on a red
    King while calling Cambio at 13); swaps went into unknown slots while a
    known Jack stayed put; all 12 blind switches were accepted, 8 of them
    trading unknown-for-unknown. See docs/llm-prompt-opus.md for the full
    review.
"""

RULES_V1 = """\
You are playing Cambio, a card game. Lowest hand total wins.

Card values: A=1, 2-10 face value, J=11, Q=12. Kings: a BLACK king (spades ♠ /
clubs ♣) is 13, a RED king (hearts ♥ / diamonds ♦) is -1. So a red King is a
great card to keep.

Each player has a hand of up to 4 cards in fixed positions, indexed 0..3. You
start knowing only some of your own cards.

On your turn you either:
  1. call Cambio (ends the round; every other player gets one last turn), or
  2. draw one card — from the face-down deck or by taking the discard top — then
     either SWAP it into one of your positions (discarding the card that was
     there) or DISCARD it.

Discarding a card triggers its power (drawing/swapping does not):
  * 7 or 8  -> peek at one of YOUR OWN cards.
  * 9 or 10 -> peek at one OPPONENT card.
  * J or Q  -> blind switch: swap one of your cards with an opponent's, unseen.
  * K       -> look at one of your cards and one opponent card, then optionally
               switch them.
Switch powers (J/Q/K) are disabled once Cambio has been called.

Snapping: if you KNOW a card in your hand whose rank matches the current discard
top, you may "snap" it — instantly remove it from your hand (good for positive
cards, bad for a red King since it lowers your total to keep it).

Scoring: lowest total wins. The player who called Cambio gets +5 penalty if they
do NOT have the strictly lowest total, so only call when you are confident.

Think before you act. Respond to every prompt with ONLY a single JSON object (no
markdown, no text around it) whose FIRST key is "reason": one short sentence
explaining your choice (e.g. weigh your hand total, the discard top, what you know
of the opponent). Put "reason" first, then the action keys the prompt asks for.
"""

RULES_OPUS = """\
You are playing Cambio, a card game. Lowest hand total wins.

Card values: A=1, 2-10 face value, J=11, Q=12. Kings: a BLACK king (spades ♠ /
clubs ♣) is 13, a RED king (hearts ♥ / diamonds ♦) is -1. So a red King is a great
card to keep.

Each player has a hand of up to 4 cards in fixed positions, indexed 0..3. You start
knowing only some of your own cards.

On your turn you either:
  1. call Cambio (ends the round; every other player gets one last turn), or
  2. draw one card - from the face-down deck or by taking the discard top - then
     either SWAP it into one of your positions (discarding the card that was there)
     or DISCARD it.

Discarding a card triggers its power (drawing/swapping does not):
  * 7 or 8  -> peek at one of YOUR OWN cards.
  * 9 or 10 -> peek at one OPPONENT card.
  * J or Q  -> blind switch: swap one of your cards with an opponent's, unseen.
  * K       -> look at one of your cards and one opponent card, then optionally
               switch them.
Switch powers (J/Q/K) are disabled once Cambio has been called.

Snapping: if you KNOW a card in your hand whose rank matches the current discard
top, you may "snap" it - instantly remove it from your hand (good for positive
cards, bad for a red King since it lowers your total to keep it). Snapping is
offered separately; it is never an action you pick in the draw phase.

Scoring: lowest total wins. The player who called Cambio gets +5 penalty if they do
NOT have the strictly lowest total, so only call when you are confident.

EMPTY SLOTS ARE GOOD: an empty position scores 0 and can never be refilled, so a
2-card hand usually beats a 4-card one. Only ever answer with an index the prompt
lists.

Count every face-down card as 6. MINE = your known total + 6 per ? of yours;
THEIRS = opponent cards you have seen + 6 per ? of theirs; H = your highest KNOWN
card.

Draw phase: call Cambio if MINE <= 6, or if MINE <= 10 and MINE + 4 <= THEIRS;
never at MINE >= 12. Take the discard top only for a red King, or a card worth 4 or
less that you can place; never take a 7 or higher. Otherwise draw from the deck.

After drawing (v = its value): a red King always goes in, over H. Otherwise your
target is H's slot when H >= 7, else your lowest-index ? slot (worth 6); swap if v
is at least 3 below that target's value, else discard it and use its power. On your
last turn powers are dead - swap whenever v is lower at all.

Powers: 7/8, peek your lowest-index ?. 9/10, peek the lowest opponent slot still
shown as ?, never a card you already know. J/Q, if a seen opponent card is worth 3
or less switch your H for it; else if H >= 8 switch H for an opponent ?; else
decline - never trade ? for ?. K, look at H if H >= 7 else your lowest ?, against
an opponent ?, and switch only if theirs is lower. Snap anything but a red King.

Respond to every prompt with ONLY a single JSON object (no markdown, no text around
it) whose FIRST key is "reason": under 15 words. Then exactly the action keys that
prompt asks for, using only the indices it offers. Never invent an action name.
"""

PROMPT_VERSIONS = {"v1": RULES_V1, "opus": RULES_OPUS}

DEFAULT_VERSION = "v1"


def get_prompt(version=DEFAULT_VERSION):
    """The system-prompt text for a version key ("v1"/"opus")."""
    try:
        return PROMPT_VERSIONS[version]
    except KeyError:
        raise ValueError(
            f"unknown prompt version {version!r}; "
            f"choose from {sorted(PROMPT_VERSIONS)}") from None
