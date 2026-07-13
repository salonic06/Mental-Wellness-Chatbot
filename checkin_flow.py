import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from db_paths import connect
from recommender import recommend_intervention
from sentiment_nlp import detect_crisis, handle_crisis
from state_store import clear_user_state, get_user_state, set_user_state

CHECKIN_CATEGORIES = {
    "1": "work",
    "2": "health",
    "3": "relationships",
    "4": "studies",
    "5": "other",
    "work": "work",
    "health": "health",
    "relationships": "relationships",
    "studies": "studies",
    "other": "other",
}


def start_checkin(user_phone: str) -> str:
    set_user_state(user_phone, "checkin_mood", {})
    return (
        "Quick check-in — no wrong answers.\n\n"
        "How are you right now? Reply 1 (really low) to 10 (great).\n\n"
        "/cancel anytime."
    )


def _save_checkin(user_phone: str, data: Dict[str, Any]) -> None:
    intensity = int(data["intensity"])
    category = data.get("category", "other")
    note = data.get("note", "")

    conn = connect()
    c = conn.cursor()
    c.execute(
        """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (user_phone, "checkin", intensity, datetime.now(), f"[{category}] {note}".strip()),
    )
    c.execute(
        """INSERT INTO checkins (user_phone, intensity, category, note, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_phone, intensity, category, note, datetime.now()),
    )
    conn.commit()
    conn.close()


def handle_checkin_message(user_phone: str, text: str) -> Optional[str]:
    """
    Process a message while user is in a check-in state.
    Returns reply text, or None if not in a check-in state.
    """
    session = get_user_state(user_phone)
    state = session["state"]
    data = session["data"]

    if state == "initial" or state == "meditating":
        return None

    lowered = text.lower()
    if lowered in ("/cancel", "cancel"):
        clear_user_state(user_phone)
        return "Check-in cancelled. Type /help whenever you need support."

    if state == "checkin_mood":
        try:
            intensity = int(lowered.split()[0])
        except ValueError:
            return "Please reply with a whole number from 1 to 10."

        if not 1 <= intensity <= 10:
            return "Please use a number between 1 and 10."

        data["intensity"] = intensity
        set_user_state(user_phone, "checkin_category", data)
        return (
            "Got it. What area is this mostly about?\n\n"
            "1) work  2) health  3) relationships  4) studies  5) other\n\n"
            "Reply with a number or name."
        )

    if state == "checkin_category":
        key = lowered.strip()
        category = CHECKIN_CATEGORIES.get(key)
        if not category:
            return "Please choose: work, health, relationships, studies, or other (1-5)."

        data["category"] = category
        set_user_state(user_phone, "checkin_note", data)
        return "Any short note you want to add? (Optional — reply 'skip' to continue.)"

    if state == "checkin_note":
        data["note"] = "" if lowered in ("skip", "no", "none", "-") else text.strip()
        if data["note"] and detect_crisis(data["note"]):
            clear_user_state(user_phone)
            return handle_crisis(
                user_phone,
                data["note"],
                source="checkin",
                intensity=int(data["intensity"]),
                category=data.get("category", "other"),
            )

        _save_checkin(user_phone, data)
        clear_user_state(user_phone)

        intensity = int(data["intensity"])
        category = data.get("category", "other")
        note = data.get("note", "")
        tip, cmd, source = recommend_intervention(
            intensity, category, hour_of_day=datetime.now().hour
        )

        try:
            from llm_wellness import checkin_closing_reply

            closing = checkin_closing_reply(
                user_phone, intensity, category, note, tip, cmd
            )
            if closing:
                from chat_flow import enter_chat_with_context

                enter_chat_with_context(user_phone, closing, pending_offer=cmd)
                return closing
        except Exception:
            pass

        label = "For you" if source == "ml" else "Suggestion"
        plain = (
            f"Check-in saved — {intensity}/10, mostly about {category}.\n\n"
            f"{label}: {tip}\n\n"
            f"When you're ready: {cmd}"
        )
        try:
            from chat_flow import enter_chat_with_context

            enter_chat_with_context(user_phone, plain, pending_offer=cmd)
        except Exception:
            pass
        return plain

    clear_user_state(user_phone)
    return "Something went wrong during check-in. Type /checkin to start again."
