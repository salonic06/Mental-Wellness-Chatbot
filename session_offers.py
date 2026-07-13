"""Short-lived offers the bot makes — fulfilled when the user says yes."""

from __future__ import annotations

import re
from typing import Optional

from bot_reply import BotReply
from state_store import clear_user_state, get_user_state, set_user_state

AFFIRMATIVE_RE = re.compile(
    r"^(yes|yeah|yea|yep|yup|sure|ok|okay|please|definitely|absolutely|"
    r"do it|go ahead|sounds good|why not|let'?s do it|let's do it)\b",
    re.I,
)
NEGATIVE_RE = re.compile(r"^(no|nah|nope|not now|later|skip|cancel)\b", re.I)


def set_pending_offer(user_phone: str, command: str, *, keep_state: bool = True) -> None:
    """Remember a suggested next step (e.g. /affirmation) until accepted or declined."""
    session = get_user_state(user_phone)
    data = dict(session.get("data") or {})
    data["pending_offer"] = command.strip()
    state = session["state"] if keep_state else session["state"]
    set_user_state(user_phone, state, data)


def clear_pending_offer(user_phone: str) -> None:
    session = get_user_state(user_phone)
    data = dict(session.get("data") or {})
    data.pop("pending_offer", None)
    set_user_state(user_phone, session["state"], data)


def get_pending_offer(user_phone: str) -> Optional[str]:
    return (get_user_state(user_phone).get("data") or {}).get("pending_offer")


def is_affirmative(text: str) -> bool:
    return bool(AFFIRMATIVE_RE.match((text or "").strip()))


def is_negative(text: str) -> bool:
    return bool(NEGATIVE_RE.match((text or "").strip()))


def try_fulfill_offer(
    user_phone: str,
    text: str,
    dispatch_fn,
) -> Optional[BotReply]:
    """
    If the user accepts a pending offer ('sure', 'yes', …), run that command.
    dispatch_fn(command, args) -> BotReply
    """
    offer = get_pending_offer(user_phone)
    if not offer:
        return None

    if is_negative(text):
        clear_pending_offer(user_phone)
        return BotReply("No problem — we can skip that. What's on your mind?")

    if not is_affirmative(text):
        return None

    clear_pending_offer(user_phone)
    parts = offer.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return dispatch_fn(command, args)
