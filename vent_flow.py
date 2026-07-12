"""Multi-turn /vent flow with VADER sentiment (see sentiment_nlp.py)."""

from typing import Optional

from sentiment_nlp import (
    analyze_sentiment,
    handle_crisis,
    log_vent_event,
    response_for_bucket,
    vent_intro,
)
from state_store import clear_user_state, get_user_state, set_user_state


def start_vent(user_phone: str) -> str:
    set_user_state(user_phone, "venting", {})
    intro = vent_intro()
    return f"{intro}\n\nType /done when finished, or /cancel to stop."


def handle_vent_message(user_phone: str, text: str) -> Optional[str]:
    session = get_user_state(user_phone)
    if session["state"] != "venting":
        return None

    lowered = text.strip().lower()
    if lowered in ("/done", "done"):
        clear_user_state(user_phone)
        return "Thank you for sharing with me. Remember, I'm here when you need support. Type /help anytime."

    if lowered in ("/cancel", "cancel"):
        clear_user_state(user_phone)
        return "Vent session ended. Type /help for commands."

    bucket, _scores = analyze_sentiment(text)
    log_vent_event(user_phone, bucket, len(text.split()), source="vent")

    # Preferred path: a warm, context-aware LLM reply (only if configured).
    try:
        from llm_wellness import CRISIS_SENTINEL, empathetic_vent_reply

        llm_reply = empathetic_vent_reply(text, bucket, user_phone)
    except Exception:  # never let the LLM layer break venting
        llm_reply, CRISIS_SENTINEL = None, "[[CRISIS]]"

    if llm_reply:
        # Second safety layer: the model flags risk the phrase list didn't catch.
        if CRISIS_SENTINEL in llm_reply:
            clear_user_state(user_phone)
            return handle_crisis(user_phone, text, source="vent")
        return f"{llm_reply}\n\nShare more, or type /done to finish."

    # Fallback: deterministic sentiment-bucket response.
    reply = response_for_bucket(bucket)
    tone = bucket.replace("_", " ")
    return (
        f"{reply}\n\n"
        "—\n"
        f"(Detected tone: {tone})\n"
        "Share more, or type /done to finish."
    )
