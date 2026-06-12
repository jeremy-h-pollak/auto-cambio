"""
LLM-in-the-loop Cambio strategy (OpenRouter).

Unlike every other bot — which is a hand-written heuristic — this strategy is
given only the rules and the *legitimately visible* game state each turn and
asked to pick a move. One running conversation per game: a system message states
the rules and which seat the model is, then each decision is appended as a new
user/assistant exchange (so the model accumulates its own peeks and the public
table history). A single model drives moves *and* special abilities through that
one conversation.

Fair information only — mirrors `strategies_advanced.py`: the model is told a
card's value solely where this seat legitimately knows it (its own `*_known`
slots and opponent slots it has peeked, tracked in per-game memory at
`state["_lmem"][seat]`). Unknown slots render as `?`.

Cost/robustness:
  * Off by default everywhere; only constructed behind an explicit opt-in.
  * Snaps use a cheap built-in heuristic by default (the frequent snap checks
    would otherwise dominate API cost); `llm_snaps=True` hands them to the model.
  * Every API/parse/illegal-move failure retries once, then **falls back to the
    greedy heuristic** so games always finish — and each fallback is announced
    loudly (stderr + game log + a counter surfaced in the run summary).

Interface (duck-typed, as the simulator/tournament/engine expect):
    choose_move(state, known_indices)     -> move dict
    should_snap(state, hand_index, seat)  -> bool
    apply_special(state, seat, stype)     -> state   (seat-general; mutates)
    apply_computer_special(state, stype)  -> state   (engine entry point)
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

from . import llm_client, strategies
from .rules import card_value, special_type


def _other(seat):
    return "computer" if seat == "player" else "player"


def _card_str(c):
    return f"{c['rank']}{c['suit']}({card_value(c)})" if c is not None else "empty"


def _extract_json(text):
    """Pull the first JSON object out of a model reply (tolerates fences/prose)."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    break
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except (ValueError, TypeError):
        return None


_RULES = """\
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

Respond to every prompt with ONLY a single JSON object — no prose, no markdown.
"""


class LLMStrategy:
    key = "llm"
    name = "OpenRouter LLM"
    rules = [
        "An LLM (via OpenRouter) is given only the rules and the cards it "
        "legitimately knows, then asked to choose each move — no hard-coded "
        "Cambio tactics.",
        "One running conversation per game: it is told which seat it is and who "
        "moves first, then each turn's fair-information state as the game unfolds.",
        "Tracks its own peeks across turns; snaps use a built-in heuristic by "
        "default to keep API cost down.",
        "On any API error or illegal reply it falls back to the Greedy Minimizer "
        "(announced in the log).",
    ]

    def __init__(self, model=None, llm_snaps=False):
        self.model = model
        self.llm_snaps = llm_snaps
        self._fallback = strategies.get("greedy")
        self.call_count = 0
        self.fallback_count = 0
        # A fresh strategy is built per game, so this groups one game's JSONL
        # lines (and distinguishes interleaved games in a shared log file).
        self.session_id = uuid.uuid4().hex[:8]
        # Where the prompt/response transcript is appended; override with
        # CAMBIO_LLM_LOG. Default: llm_logs/prompts.jsonl under the repo root.
        self.log_path = os.environ.get("CAMBIO_LLM_LOG") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "llm_logs", "prompts.jsonl")

    # ── Conversation / memory in state ───────────────────────────────────────
    def _conv(self, state, seat):
        store = state.setdefault("_llm", {})
        if seat not in store:
            first = "You move first this game." if not state["log"] \
                else "Your opponent moved first this game."
            store[seat] = {
                "messages": [
                    {"role": "system", "content": f"{_RULES}\nYou are the "
                     f"'{seat}' player. {first}"}
                ],
                "log_shown": len(state["log"]),
            }
        return store[seat]

    def _memory(self, state, seat):
        return state.setdefault("_lmem", {}).setdefault(seat, {})

    def _prune_memory(self, state, seat):
        """Forget remembered opponent cards that are gone or have changed."""
        mem = self._memory(state, seat)
        opp_hand = state[f"{_other(seat)}_hand"]
        for i in list(mem):
            c = opp_hand[i] if i < len(opp_hand) else None
            if c is None or c["rank"] != mem[i]["rank"] or c["suit"] != mem[i]["suit"]:
                del mem[i]

    def _remember(self, state, seat, idx, card):
        self._memory(state, seat)[idx] = {"rank": card["rank"], "suit": card["suit"]}

    # ── Fair-information snapshot ─────────────────────────────────────────────
    def _render_snapshot(self, state, seat):
        conv = self._conv(state, seat)
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        mem = self._memory(state, seat)
        opp_hand = state[f"{_other(seat)}_hand"]

        my_slots = []
        for i, c in enumerate(hand):
            if c is None:
                my_slots.append(f"[{i}]=empty")
            elif i < len(known) and known[i]:
                my_slots.append(f"[{i}]={_card_str(c)}")
            else:
                my_slots.append(f"[{i}]=?")

        opp_slots = []
        for i, c in enumerate(opp_hand):
            if c is None:
                opp_slots.append(f"[{i}]=empty")
            elif i in mem:
                opp_slots.append(f"[{i}]={_card_str(mem[i])}")
            else:
                opp_slots.append(f"[{i}]=?")

        discard = state["discard_pile"]
        top = _card_str(discard[-1]) if discard else "none"
        cambio = state["cambio_called_by"]
        if cambio is None:
            cstat = "not called"
        elif cambio.startswith(seat):
            cstat = "YOU called Cambio"
        else:
            cstat = "OPPONENT ended the round — this is your LAST turn"

        new_log = state["log"][conv["log_shown"]:]
        conv["log_shown"] = len(state["log"])
        events = ("\nRecent table events:\n  " + "\n  ".join(new_log)) if new_log else ""

        return (
            f"Your hand:     {' '.join(my_slots)}\n"
            f"Opponent hand: {' '.join(opp_slots)}  (? = not yet seen)\n"
            f"Discard top:   {top}\n"
            f"Deck left:     {len(state['deck'])} cards\n"
            f"Cambio:        {cstat}"
            f"{events}"
        )

    # ── One validated model request, with one retry ──────────────────────────
    def _ask(self, state, seat, prompt, validate, *, include_snapshot=True, kind="move"):
        """Append `prompt` to the conversation, query the model, and return the
        validated parsed object — or None to signal the caller to fall back.

        Every attempt (the snapshot+prompt that went out, GSi, the raw reply, and
        the parsed move) is captured into `state["llm_trace"]` and the JSONL log so
        the web UI / a transcript can show exactly what the model saw and answered.
        """
        conv = self._conv(state, seat)
        snapshot = self._render_snapshot(state, seat) if include_snapshot else None
        content = (snapshot + "\n\n" + prompt) if snapshot is not None else prompt

        last_reason = "no reply"
        for attempt in range(2):
            # Only the first attempt carries the fair-info GSi; the retry is just a
            # "that was invalid, resend JSON" nudge, so GSi is None there.
            gsi = snapshot if attempt == 0 else None
            conv["messages"].append({"role": "user", "content": content})
            try:
                self.call_count += 1
                # Don't request response_format JSON mode: some models have no
                # provider that supports it (e.g. moonshotai/kimi-k2 is served by
                # Novita, which 400-rejects the flag, and require_parameters routing
                # 404s — no Kimi provider offers it). The prompt already demands a
                # JSON object, `_extract_json` parses leniently (tolerates fences/
                # prose), and the retry below nudges stragglers, so the flag only
                # added a provider-compatibility failure mode for no real benefit.
                reply = llm_client.chat(conv["messages"], model=self.model,
                                        force_json=False)
            except llm_client.LLMError as e:
                self._record(state, seat, kind, gsi, prompt, content,
                             response=None, parsed=None, error=f"API error: {e}")
                self._notice(state, f"API error: {e}")
                return None
            conv["messages"].append({"role": "assistant", "content": reply})
            obj = _extract_json(reply)
            ok, result = validate(obj) if obj is not None else (False, "not JSON")
            self._record(state, seat, kind, gsi, prompt, content, response=reply,
                         parsed=(result if ok else None),
                         error=(None if ok else result))
            if ok:
                return result
            last_reason = result
            content = (f"That reply was invalid ({result}). Respond with ONLY a "
                       f"single valid JSON object as instructed.")
        # Exhausted retries on an unparseable / illegal reply — count it as a
        # fallback too, so every fallback is announced (not just API errors).
        self._notice(state, f"illegal reply: {last_reason}")
        return None

    # ── Prompt/response trace (in-state for the UI + JSONL on disk) ────────────
    def _record(self, state, seat, kind, gsi, prompt, full_prompt, *,
                response, parsed, error):
        """Append one prompt/response entry to the live trace and the log file."""
        trace = state.setdefault("llm_trace", [])
        entry = {
            "n": len(trace) + 1,
            "seat": seat,
            "kind": kind,
            "model": self.model or llm_client.model_name(),
            "state": gsi,            # GSi — the fair-info snapshot the model saw
            "prompt": prompt,        # Pi — the instruction/MOVES text (or retry nudge)
            "full_prompt": full_prompt,  # exactly what was sent to the API
            "response": response,    # Mi — raw model reply (None on API error)
            "parsed": parsed,        # the validated move (None if illegal/failed)
            "error": error,          # reason when invalid / API error, else None
        }
        trace.append(entry)
        self._write_log_line(entry)

    def _write_log_line(self, entry):
        """Append the entry as one JSON line. Logging must never break a game, so
        any I/O error is swallowed (after a one-time stderr warning)."""
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            line = {"ts": datetime.now(timezone.utc).isoformat(),
                    "session": self.session_id, **entry}
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as e:
            if not getattr(self, "_log_warned", False):
                print(f"  ⚠ LLM log write failed ({e}); continuing without it.",
                      file=sys.stderr)
                self._log_warned = True

    def _notice(self, state, reason):
        self.fallback_count += 1
        msg = f"LLM fallback ({self.fallback_count}): {reason} — using greedy heuristic."
        print(f"  ⚠ {msg}", file=sys.stderr)
        state["log"].append(msg)

    # ── choose_move ──────────────────────────────────────────────────────────
    def choose_move(self, state, known_indices=None):
        seat = state["current_turn"]
        self._prune_memory(state, seat)
        drawn = state["drawn_card"]
        if drawn is None:
            return self._draw_phase(state, seat)
        return self._action_phase(state, seat, drawn)

    def _draw_phase(self, state, seat):
        can_cambio = state["cambio_called_by"] is None
        has_discard = bool(state["discard_pile"])
        opts = ['{"action": "draw_deck"}']
        if has_discard:
            opts.append('{"action": "draw_discard"}  (take the discard top)')
        if can_cambio:
            opts.append('{"action": "call_cambio"}  (end the round)')
        prompt = ("It is your turn (draw phase). Choose ONE:\n  - "
                  + "\n  - ".join(opts))

        def validate(obj):
            a = obj.get("action") if isinstance(obj, dict) else None
            if a == "draw_deck":
                return True, {"action": "draw_deck"}
            if a == "draw_discard" and has_discard:
                return True, {"action": "draw_discard"}
            if a == "call_cambio" and can_cambio:
                return True, {"action": "call_cambio"}
            return False, f"action {a!r} not legal now"

        result = self._ask(state, seat, prompt, validate, kind="draw")
        if result is None:
            return self._fallback.choose_move(state, state[f"{seat}_known"])
        return result

    def _action_phase(self, state, seat, drawn):
        hand = state[f"{seat}_hand"]
        held = [i for i, c in enumerate(hand) if c is not None]
        prompt = (
            f"You drew {_card_str(drawn)}. Choose ONE:\n"
            f'  - {{"action": "swap", "hand_index": i}}  where i is one of your '
            f"non-empty positions {held} (replaces that card, discarding it)\n"
            f'  - {{"action": "discard_drawn"}}  (discard the drawn card; if it is '
            f"7/8/9/10/J/Q/K this fires its power)")

        def validate(obj):
            a = obj.get("action") if isinstance(obj, dict) else None
            if a == "discard_drawn":
                return True, {"action": "discard_drawn"}
            if a == "swap":
                idx = obj.get("hand_index")
                if isinstance(idx, int) and idx in held:
                    return True, {"action": "swap", "hand_index": idx}
                return False, f"hand_index must be one of {held}"
            return False, f"action {a!r} not legal now"

        result = self._ask(state, seat, prompt, validate, kind="action")
        if result is None:
            return self._fallback.choose_move(state, state[f"{seat}_known"])
        return result

    # ── Snapping ─────────────────────────────────────────────────────────────
    def should_snap(self, state, hand_index, seat="computer"):
        if not self.llm_snaps:
            return self._fallback.should_snap(state, hand_index, seat)
        card = state[f"{seat}_hand"][hand_index]
        if card is None:
            return False
        prompt = (
            f"You may SNAP your position {hand_index} ({_card_str(card)}) — its "
            f"rank matches the discard top. Snapping removes it from your hand "
            f"(good for positive cards; bad for a red King worth -1). "
            f'Reply {{"snap": true}} or {{"snap": false}}.')

        def validate(obj):
            if isinstance(obj, dict) and isinstance(obj.get("snap"), bool):
                return True, obj["snap"]
            return False, "need {\"snap\": true|false}"

        result = self._ask(state, seat, prompt, validate, kind="snap")
        if result is None:
            return self._fallback.should_snap(state, hand_index, seat)
        return result

    # ── Special abilities ────────────────────────────────────────────────────
    def apply_computer_special(self, state, stype):
        return self.apply_special(state, "computer", stype)

    def apply_special(self, state, seat, stype):
        self._prune_memory(state, seat)
        if stype == "peek_own":
            self._do_peek_own(state, seat)
        elif stype == "peek_opponent":
            self._do_peek_opponent(state, seat)
        elif stype == "blind_switch":
            self._do_blind_switch(state, seat)
        elif stype == "looking_switch":
            self._do_looking_switch(state, seat)
        return state

    def _held(self, hand):
        return [i for i, c in enumerate(hand) if c is not None]

    def _pick_index(self, state, seat, prompt, valid_indices, key="index", kind="move"):
        def validate(obj):
            if isinstance(obj, dict) and obj.get(key) in valid_indices:
                return True, obj[key]
            return False, f"{key} must be one of {valid_indices}"
        return self._ask(state, seat, prompt, validate, kind=kind)

    def _do_peek_own(self, state, seat):
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        unknown = [i for i in self._held(hand) if not (i < len(known) and known[i])]
        if not unknown:
            return
        prompt = (f"You discarded a 7/8. Peek at ONE of your own face-down cards: "
                  f"{unknown}. Reply {{\"index\": i}}.")
        idx = self._pick_index(state, seat, prompt, unknown, kind="peek_own")
        if idx is None:
            self._fallback.apply_special(state, seat, "peek_own")
            return
        known[idx] = True
        if seat == "computer":
            state["computer_acted"] = [idx]
        c = hand[idx]
        msg = f"{seat} used 7/8: peeked at its own position {idx} ({_card_str(c)})."
        state["log"].append(msg)
        self._conv(state, seat)["messages"].append(
            {"role": "user", "content": f"(You peeked your [{idx}]: {_card_str(c)}.)"})

    def _do_peek_opponent(self, state, seat):
        opp_hand = state[f"{_other(seat)}_hand"]
        valid = self._held(opp_hand)
        if not valid:
            return
        prompt = (f"You discarded a 9/10. Peek at ONE opponent card: {valid}. "
                  f"Reply {{\"index\": i}}.")
        idx = self._pick_index(state, seat, prompt, valid, kind="peek_opponent")
        if idx is None:
            self._fallback.apply_special(state, seat, "peek_opponent")
            return
        c = opp_hand[idx]
        self._remember(state, seat, idx, c)
        if seat == "computer":
            state["player_reveal"].append(idx)
        state["log"].append(f"{seat} used 9/10: peeked at opponent position {idx}.")
        self._conv(state, seat)["messages"].append(
            {"role": "user", "content": f"(You peeked opponent [{idx}]: {_card_str(c)}.)"})

    def _forget_opp(self, state, seat, oi):
        opp = _other(seat)
        if oi < len(state[f"{opp}_known"]):
            state[f"{opp}_known"][oi] = False
        if oi < len(state["player_opponent_known"]):
            state["player_opponent_known"][oi] = False

    def _do_blind_switch(self, state, seat):
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        opp_hand = state[f"{_other(seat)}_hand"]
        me_valid, opp_valid = self._held(hand), self._held(opp_hand)
        if not me_valid or not opp_valid:
            return
        prompt = (
            f"You discarded a J/Q (blind switch). Swap one of YOUR cards "
            f"{me_valid} with one OPPONENT card {opp_valid}, sight unseen — useful "
            f"to dump a known-high card. Reply {{\"own\": i, \"opp\": j}} to switch, "
            f"or {{\"switch\": false}} to decline.")

        def validate(obj):
            if not isinstance(obj, dict):
                return False, "need JSON"
            if obj.get("switch") is False:
                return True, "decline"
            o, p = obj.get("own"), obj.get("opp")
            if o in me_valid and p in opp_valid:
                return True, (o, p)
            return False, f"own in {me_valid}, opp in {opp_valid}, or switch:false"

        picks = self._ask(state, seat, prompt, validate, kind="blind_switch")
        if picks is None:                       # API/parse failure → heuristic
            self._fallback.apply_special(state, seat, "blind_switch")
            return
        if picks == "decline":
            state["log"].append(f"{seat} used J/Q: declined to switch.")
            return

        mi, oi = picks
        knew = mi < len(known) and known[mi]
        my_card = dict(hand[mi])
        hand[mi], opp_hand[oi] = opp_hand[oi], hand[mi]
        known[mi] = False
        self._forget_opp(state, seat, oi)
        if seat == "computer":
            state["computer_acted"] = [mi]
            state["player_touched"] = [oi]
        mem = self._memory(state, seat)
        if knew:
            mem[oi] = my_card        # opponent now holds the card we knew
        else:
            mem.pop(oi, None)
        state["log"].append(
            f"{seat} used J/Q: blind-switched its position {mi} with opponent's {oi}.")

    def _do_looking_switch(self, state, seat):
        hand, known = state[f"{seat}_hand"], state[f"{seat}_known"]
        opp_hand = state[f"{_other(seat)}_hand"]
        me_valid, opp_valid = self._held(hand), self._held(opp_hand)
        if not me_valid or not opp_valid:
            return
        prompt = (
            f"You discarded a K (look then optionally switch). Pick one of YOUR "
            f"cards {me_valid} and one OPPONENT card {opp_valid} to look at. "
            f"Reply {{\"own\": i, \"opp\": j}}.")

        def validate(obj):
            if isinstance(obj, dict) and obj.get("own") in me_valid and obj.get("opp") in opp_valid:
                return True, (obj["own"], obj["opp"])
            return False, f"own in {me_valid}, opp in {opp_valid}"

        picks = self._ask(state, seat, prompt, validate, kind="look")
        if picks is None:
            self._fallback.apply_special(state, seat, "looking_switch")
            return
        mi, oi = picks
        known[mi] = True
        self._remember(state, seat, oi, opp_hand[oi])
        if seat == "computer":
            state["player_reveal"].append(oi)
        my_card, opp_card = hand[mi], opp_hand[oi]

        decide_prompt = (
            f"You looked: your [{mi}]={_card_str(my_card)}, opponent "
            f"[{oi}]={_card_str(opp_card)}. Switch them? (Switching is good only if "
            f"the opponent's card is lower than yours.) "
            f"Reply {{\"switch\": true}} or {{\"switch\": false}}.")

        def validate_decide(obj):
            if isinstance(obj, dict) and isinstance(obj.get("switch"), bool):
                return True, obj["switch"]
            return False, "need {\"switch\": true|false}"

        do_switch = self._ask(state, seat, decide_prompt, validate_decide,
                              include_snapshot=False, kind="look_decide")
        if do_switch is None:
            do_switch = card_value(opp_card) < card_value(my_card)  # safe default

        if do_switch:
            mine = dict(hand[mi])
            hand[mi], opp_hand[oi] = opp_hand[oi], hand[mi]
            known[mi] = True
            self._forget_opp(state, seat, oi)
            self._remember(state, seat, oi, mine)
            if seat == "computer":
                state["computer_acted"] = [mi]
                state["player_touched"] = [oi]
            state["log"].append(
                f"{seat} used K: looked and switched its position {mi} with opponent's {oi}.")
        else:
            if seat == "computer":
                state["computer_acted"] = [mi]
            state["log"].append(f"{seat} used K: looked but chose not to switch.")


def get_llm_strategy(model=None, llm_snaps=False):
    return LLMStrategy(model=model, llm_snaps=llm_snaps)
