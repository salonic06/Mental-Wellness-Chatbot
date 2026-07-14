"""
Unified companion chat mode — one persona, open conversation.

/vent explicitly enters this mode; emotional free-text auto-enters it too.
Replaces the old vent-only silo with ambient, multi-turn chat.
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
from state_store import clear_user_state, get_user_state, set_user_state

HISTORY_KEY = "chat_history"
MAX_STORED_TURNS = 16


def _normalize_state(user_phone: str) -> dict:
    session = get_user_state(user_phone)
    if session["state"] == LEGACY_VENT_STATE:
        data = dict(session.get("data") or {})
        # migrate vent_history → chat_history
        if "vent_history" in data and HISTORY_KEY not in data:
            data[HISTORY_KEY] = data.pop("vent_history")
        set_user_state(user_phone, CHAT_STATE, data)
        session = get_user_state(user_phone)
    return session


def is_chatting(user_phone: str) -> bool:
    return get_user_state(user_phone)["state"] in CHAT_STATES


def enter_chat(user_phone: str, data: Optional[dict] = None) -> None:
    set_user_state(user_phone, CHAT_STATE, data or {})


def start_chat(user_phone: str) -> str:
    enter_chat(user_phone)
    try:
        from llm_wellness import chat_open_reply

        opening = chat_open_reply(user_phone)
        if opening:
            return opening
    except Exception:
        pass
    return t(user_phone, "chat_intro")


def enter_chat_with_context(
    user_phone: str,
    assistant_message: str,
    pending_offer: Optional[str] = None,
) -> None:
    """Open chat mode and seed history so follow-ups like 'sure' have context."""
    data: dict = {
        HISTORY_KEY: [{"role": "assistant", "content": assistant_message}],
    }
    if pending_offer:
        data["pending_offer"] = pending_offer
    set_user_state(user_phone, CHAT_STATE, data)


def try_fulfill_in_chat(user_phone: str, text: str) -> Optional[str]:
    """If user accepts a pending offer while chatting, return the action result text."""
    from session_offers import clear_pending_offer, get_pending_offer, is_affirmative

    offer = get_pending_offer(user_phone)
    if not offer or not is_affirmative(text):
        return None
    clear_pending_offer(user_phone)
    return f"__OFFER__:{offer}"


def handle_chat_message(user_phone: str, text: str) -> Optional[str]:
    session = _normalize_state(user_phone)
    if session["state"] not in CHAT_STATES:
        return None

    lowered = text.strip().lower()
    if lowered in ("/done", "done", "vent_done"):
        clear_user_state(user_phone)
        return t(user_phone, "chat_done")

    if lowered in ("/cancel", "cancel"):
        clear_user_state(user_phone)
        return t(user_phone, "chat_cancel")

    offer_hit = try_fulfill_in_chat(user_phone, text)
    if offer_hit and offer_hit.startswith("__OFFER__:"):
        return offer_hit  # router dispatches the command

    bucket, _scores = analyze_sentiment(text)
    log_vent_event(user_phone, bucket, len(text.split()), source="chat")

    session_data = dict(session.get("data") or {})
    history: list = list(session_data.get(HISTORY_KEY) or session_data.get("vent_history") or [])

    try:
        from llm_wellness import CRISIS_SENTINEL, empathetic_vent_reply

        llm_reply = empathetic_vent_reply(
            text, bucket, user_phone, vent_history=history
        )
    except Exception:
        llm_reply, CRISIS_SENTINEL = None, "[[CRISIS]]"

    if llm_reply:
        if CRISIS_SENTINEL in llm_reply:
            clear_user_state(user_phone)
            return handle_crisis(user_phone, text, source="chat")
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": llm_reply})
        session_data[HISTORY_KEY] = history[-MAX_STORED_TURNS:]
        session_data.pop("vent_history", None)
        set_user_state(user_phone, CHAT_STATE, session_data)
        return llm_reply

    reply = response_for_bucket(bucket)
    tone = bucket.replace("_", " ")
    return f"{reply}\n\n(Tone: {tone})\n{t(user_phone, 'chat_keep_going')}"


# Backward-compatible aliases used by /vent and tests
start_vent = start_chat
handle_vent_message = handle_chat_message
