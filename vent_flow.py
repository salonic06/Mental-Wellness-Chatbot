"""Multi-turn /vent flow with VADER sentiment (see sentiment_nlp.py)."""

from typing import Optional

from sentiment_nlp import (
    analyze_sentiment,
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
    reply = response_for_bucket(bucket)
    tone = bucket.replace("_", " ")
    return (
        f"{reply}\n\n"
        "—\n"
        f"(Detected tone: {tone})\n"
        "Share more, or type /done to finish."
    )
