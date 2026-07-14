"""
Unified companion chat mode — one persona, open conversation.

Optional pre/post mood (1–10) captures session impact for the dashboard.
"""

from typing import Optional

from languages import t
from patterns import CHAT_STATE, CHAT_STATES, LEGACY_VENT_STATE
from sentiment_nlp import (
    analyze_sentiment,
    handle_crisis,
    log_vent_event,
    response_for_bucket,
)
from session_outcomes import (
    abandon_chat_outcome,
    close_chat_outcome,
    open_chat_outcome,
    parse_mood_reply,
    set_pre_mood,
)
from state_store import clear_user_state, get_user_state, set_user_state

HISTORY_KEY = "chat_history"
OUTCOME_KEY = "outcome_id"
MAX_STORED_TURNS = 16

PRE_MOOD_STATE = "chat_pre_mood"
POST_MOOD_STATE = "chat_post_mood"
IMPACT_STATES = frozenset({PRE_MOOD_STATE, POST_MOOD_STATE})


def _normalize_state(user_phone: str) -> dict:
    session = get_user_state(user_phone)
    if session["state"] == LEGACY_VENT_STATE:
        data = dict(session.get("data") or {})
        if "vent_history" in data and HISTORY_KEY not in data:
            data[HISTORY_KEY] = data.pop("vent_history")
        set_user_state(user_phone, CHAT_STATE, data)
        session = get_user_state(user_phone)
    return session


def is_chatting(user_phone: str) -> bool:
    return get_user_state(user_phone)["state"] in CHAT_STATES


def is_impact_prompt(user_phone: str) -> bool:
    return get_user_state(user_phone)["state"] in IMPACT_STATES


def enter_chat(user_phone: str, data: Optional[dict] = None) -> None:
    """Enter chatting; open an outcome row if one is not already attached."""
    payload = dict(data or {})
    if OUTCOME_KEY not in payload:
        oid = open_chat_outcome(user_phone, source="chat")
        if oid:
            payload[OUTCOME_KEY] = oid
    set_user_state(user_phone, CHAT_STATE, payload)


def start_chat(user_phone: str) -> str:
    """
    Start Talk-it-out: warm open + ask optional pre mood (impact metric).
    """
    opening = None
    try:
        from llm_wellness import chat_open_reply

        opening = chat_open_reply(user_phone)
    except Exception:
        opening = None
    if not opening:
        opening = t(user_phone, "chat_intro")

    oid = open_chat_outcome(user_phone, source="chat")
    data = {OUTCOME_KEY: oid} if oid else {}
    set_user_state(user_phone, PRE_MOOD_STATE, data)
    return (
        f"{opening}\n\n"
        f"{t(user_phone, 'chat_pre_mood_ask')}\n"
        f"{t(user_phone, 'chat_mood_skip_hint')}"
    )


def enter_chat_with_context(
    user_phone: str,
    assistant_message: str,
    pending_offer: Optional[str] = None,
    pre_intensity: Optional[int] = None,
) -> None:
    """Open chat mode and seed history so follow-ups like 'sure' have context."""
    data: dict = {
        HISTORY_KEY: [{"role": "assistant", "content": assistant_message}],
    }
    if pending_offer:
        data["pending_offer"] = pending_offer
    oid = open_chat_outcome(user_phone, source="checkin_offer")
    if oid:
        data[OUTCOME_KEY] = oid
        if pre_intensity is not None:
            set_pre_mood(oid, pre_intensity, skipped=False)
    set_user_state(user_phone, CHAT_STATE, data)


def try_fulfill_in_chat(user_phone: str, text: str) -> Optional[str]:
    from session_offers import clear_pending_offer, get_pending_offer, is_affirmative

    offer = get_pending_offer(user_phone)
    if not offer or not is_affirmative(text):
        return None
    clear_pending_offer(user_phone)
    return f"__OFFER__:{offer}"


def handle_pre_mood(user_phone: str, text: str) -> str:
    session = get_user_state(user_phone)
    data = dict(session.get("data") or {})
    oid = data.get(OUTCOME_KEY)

    lowered = text.strip().lower()
    if lowered in ("/cancel", "cancel"):
        abandon_chat_outcome(oid)
        clear_user_state(user_phone)
        return t(user_phone, "chat_cancel")

    intensity, skipped = parse_mood_reply(text)
    if intensity is None and not skipped:
        return t(user_phone, "chat_mood_invalid")

    if oid:
        set_pre_mood(oid, intensity, skipped=skipped)

    set_user_state(user_phone, CHAT_STATE, data)
    return t(user_phone, "chat_pre_mood_ack")


def handle_post_mood(user_phone: str, text: str) -> str:
    session = get_user_state(user_phone)
    data = dict(session.get("data") or {})
    oid = data.get(OUTCOME_KEY)

    lowered = text.strip().lower()
    if lowered in ("/cancel", "cancel", "skip", "s", "-"):
        if oid:
            close_chat_outcome(oid, post_intensity=None, skipped_post=True)
        clear_user_state(user_phone)
        return t(user_phone, "chat_done")

    intensity, skipped = parse_mood_reply(text)
    if intensity is None and not skipped:
        return t(user_phone, "chat_mood_invalid")

    summary = None
    if oid:
        summary = close_chat_outcome(
            oid, post_intensity=intensity if not skipped else None, skipped_post=skipped
        )
    clear_user_state(user_phone)

    base = t(user_phone, "chat_done")
    if summary and summary.get("mood_delta") is not None:
        delta = summary["mood_delta"]
        if delta > 0:
            return f"{base}\n\n{t(user_phone, 'chat_impact_up', delta=str(delta))}"
        if delta < 0:
            return f"{base}\n\n{t(user_phone, 'chat_impact_down', delta=str(abs(delta)))}"
        return f"{base}\n\n{t(user_phone, 'chat_impact_same')}"
    return base


def _begin_post_mood(user_phone: str, data: dict) -> str:
    set_user_state(user_phone, POST_MOOD_STATE, data)
    return (
        f"{t(user_phone, 'chat_post_mood_ask')}\n"
        f"{t(user_phone, 'chat_mood_skip_hint')}"
    )


def handle_chat_message(user_phone: str, text: str) -> Optional[str]:
    session = _normalize_state(user_phone)
    state = session["state"]

    if state == PRE_MOOD_STATE:
        return handle_pre_mood(user_phone, text)
    if state == POST_MOOD_STATE:
        return handle_post_mood(user_phone, text)

    if state not in CHAT_STATES:
        return None

    data = dict(session.get("data") or {})
    lowered = text.strip().lower()
    if lowered in ("/done", "done", "vent_done"):
        return _begin_post_mood(user_phone, data)

    if lowered in ("/cancel", "cancel"):
        abandon_chat_outcome(data.get(OUTCOME_KEY))
        clear_user_state(user_phone)
        return t(user_phone, "chat_cancel")

    offer_hit = try_fulfill_in_chat(user_phone, text)
    if offer_hit and offer_hit.startswith("__OFFER__:"):
        return offer_hit

    bucket, _scores = analyze_sentiment(text)
    log_vent_event(user_phone, bucket, len(text.split()), source="chat")

    history: list = list(data.get(HISTORY_KEY) or data.get("vent_history") or [])

    try:
        from llm_wellness import CRISIS_SENTINEL, empathetic_vent_reply

        llm_reply = empathetic_vent_reply(
            text, bucket, user_phone, vent_history=history
        )
    except Exception:
        llm_reply, CRISIS_SENTINEL = None, "[[CRISIS]]"

    if llm_reply:
        if CRISIS_SENTINEL in llm_reply:
            abandon_chat_outcome(data.get(OUTCOME_KEY))
            clear_user_state(user_phone)
            return handle_crisis(user_phone, text, source="chat")
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": llm_reply})
        data[HISTORY_KEY] = history[-MAX_STORED_TURNS:]
        data.pop("vent_history", None)
        set_user_state(user_phone, CHAT_STATE, data)
        return llm_reply

    reply = response_for_bucket(bucket)
    tone = bucket.replace("_", " ")
    return f"{reply}\n\n(Tone: {tone})\n{t(user_phone, 'chat_keep_going')}"


start_vent = start_chat
handle_vent_message = handle_chat_message
