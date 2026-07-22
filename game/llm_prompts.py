"""
Versioned system prompts for the LLM strategy (`game/strategy_llm.py`).

Keeping the prompts here — out of the strategy — makes a prompt change a shippable,
*measurable* thing: each version is a named entrant, so V1 and V2 can meet in the
same tournament and the rating difference is attributable to the prompt alone.

  * **v1** — rules only. The original prompt: the model is told how Cambio works
    and what it legitimately knows, and nothing about how to play well.
  * **v2** — rules + the playbook of the strongest hand-written bot in this repo
    (The Cartographer, #1 in tournament reports 6994 and 6414). Report 06ce put
    the LLM entrants ~80–105 Elo *below* it, so v2 tests whether that gap is
    withheld strategy knowledge rather than model capability.

The v2 playbook is generated from the bot's own `rules` bullets rather than
hand-copied prose, so retuning the Cartographer updates the prompt with it.
"""

from .strategies_advanced import ADVANCED

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

# The bot whose playbook v2 hands over: the highest-rated entrant on the ladder.
PLAYBOOK_BOT = ADVANCED["cartographer"]

PLAYBOOK = (
    f"Strategy guidance — how the strongest player in this game plays:\n\n"
    f"The best-performing opponent in this system is a hand-written bot called "
    f"\"{PLAYBOOK_BOT.name}\". It out-scores general-purpose reasoning, and its "
    f"playbook is:\n"
    + "".join(f"  * {rule}\n" for rule in PLAYBOOK_BOT.rules)
    + "\nTreat that as your default policy: gather information early with the peek "
      "powers, keep your total low, and only call Cambio once you both know your "
      "hand and believe you are ahead. Deviate when the specific state on the "
      "table clearly calls for it.\n"
)

RULES_V2 = RULES_V1 + "\n" + PLAYBOOK

PROMPT_VERSIONS = {"v1": RULES_V1, "v2": RULES_V2}

DEFAULT_VERSION = "v1"


def get_prompt(version=DEFAULT_VERSION):
    """The system-prompt text for a version key ("v1"/"v2")."""
    try:
        return PROMPT_VERSIONS[version]
    except KeyError:
        raise ValueError(
            f"unknown prompt version {version!r}; "
            f"choose from {sorted(PROMPT_VERSIONS)}") from None
