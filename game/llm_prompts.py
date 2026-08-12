"""
Versioned system prompts for the LLM strategy (`game/strategy_llm.py`).

Keeping the prompts here — out of the strategy — makes a prompt change a shippable,
*measurable* thing: each version is a named entrant, so V1 and V2 can meet in the
same tournament and the rating difference is attributable to the prompt alone.

  * **v1** — rules only. The original prompt: the model is told how Cambio works
    and what it legitimately knows, and nothing about how to play well.
  * **v2** — rules + the playbook of the strongest hand-written bot in this repo
    (The Cartographer, #1 in tournament reports 6994 and 6414), as *prose*. Report
    06ce put the LLM entrants ~80–105 Elo below it; report 6efc then measured v2 vs
    v1 at 52–47–1 over 100 games (p=0.62) — a **null**. Describing the playbook did
    not change how the model played.
  * **v3** — the same playbook made **operational**: an ordered, numeric decision
    procedure the model executes each turn, plus a worked example, instead of a
    description of how a good player thinks. 6efc's read was "it wasn't the content,
    it was the format", so v3 tests exactly that — same source bot, imperative form.

The v2/v3 playbooks are generated from the bot's own `rules` bullets and threshold
attributes rather than hand-copied numbers, so retuning the Cartographer updates the
prompts with it — there is no second copy of a threshold to drift.
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


def _operational_playbook(bot):
    """The same bot as an *imperative decision procedure* — v2's content, v3's form.

    Thresholds are interpolated from the bot's own attributes (not re-typed), so v3
    tracks a retuned Cartographer exactly as v2 does. The ordering/structure is the
    part v3 adds: a good player's policy stated as steps the model runs, plus one
    worked example to anchor the arithmetic it tends to fumble.
    """
    return (
        f"Strategy — play by this exact procedure each turn. It is how the strongest "
        f"player in this game, the hand-written bot \"{bot.name}\", plays; it beats "
        f"general-purpose reasoning, so follow it as your default policy and deviate "
        f"only when the specific table clearly demands it.\n\n"
        f"DRAW PHASE — take the FIRST option that applies:\n"
        f"  1. Call Cambio ONLY if you already know (almost) all of your own cards, "
        f"your estimated total is ≤ {bot.cambio_abs_cap}, AND you believe you lead by "
        f"≥ {bot.cambio_margin}. If any of those is false, do NOT call.\n"
        f"  2. If you can still learn cheaply — you hold any face-down card of your "
        f"own, or you have seen fewer than 3 of the opponent's cards — draw from the "
        f"deck (a fresh card can be a peek/switch power).\n"
        f"  3. Take the discard top instead only if it is worth ≤ {bot.grab_discard_max}; "
        f"otherwise draw from the deck.\n\n"
        f"AFTER DRAWING — take the FIRST that applies:\n"
        f"  4. If the card is a 7/8/9/10 and you still have unknowns to map (your own "
        f"or the opponent's), DISCARD it to fire the peek — mapping the table beats a "
        f"small swap.\n"
        f"  5. If it is lower than your highest KNOWN card, swap it into that slot "
        f"(dumping the high card).\n"
        f"  6. Else, if it is worth ≤ {bot.gamble_max}, gamble it onto one of your "
        f"unknown slots.\n"
        f"  7. Otherwise discard it (firing any power it has).\n\n"
        f"POWERS:\n"
        f"  - 7/8 → peek your own unknowns; 9/10 → peek the opponent's — always map.\n"
        f"  - K → look, then switch ONLY if the opponent's card is lower than yours.\n"
        f"  - J/Q → blind-switch ONLY to dump a known card worth ≥ "
        f"{bot.blind_switch_min_give}.\n\n"
        f"SNAP / KEEP:\n"
        f"  - Snap a known card matching the discard top when it is POSITIVE. NEVER "
        f"snap a red King — it is worth -1, so keeping it lowers your total.\n\n"
        f"Worked example: your hand is [7, ?, K♥(-1), 9] — known cards total 15 with "
        f"one slot unknown — and you draw a 4. Your highest known is the 9; the 4 is "
        f"lower, so by step 5 you swap the 4 into the 9's slot (known total drops to "
        f"10). You would NOT call Cambio yet: a slot is still unknown.\n"
    )


PLAYBOOK_OPERATIONAL = _operational_playbook(PLAYBOOK_BOT)

RULES_V3 = RULES_V1 + "\n" + PLAYBOOK_OPERATIONAL

PROMPT_VERSIONS = {"v1": RULES_V1, "v2": RULES_V2, "v3": RULES_V3}

DEFAULT_VERSION = "v1"


def get_prompt(version=DEFAULT_VERSION):
    """The system-prompt text for a version key ("v1"/"v2")."""
    try:
        return PROMPT_VERSIONS[version]
    except KeyError:
        raise ValueError(
            f"unknown prompt version {version!r}; "
            f"choose from {sorted(PROMPT_VERSIONS)}") from None
