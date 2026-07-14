"""
Soft, human opt-in hints for morning notes / care pings.

Appended after mood, affirmation, summary, or check-in when the user has not
already opted in — never technical host/WhatsApp jargon.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from checkin_nudge_scheduler import get_reminder_status
from session_offers import get_pending_offer, set_pending_offer
from state_store import get_user_state, set_user_state

MORNING_HINT = (
    "\n\nIf you'd like, I can send a short morning note each day — "
    "just a little check-in when you wake. Want that? Reply **yes**."
)

CARE_HINT = (
    "\n\nIf things feel heavy for a few days, I can gently check in on my own "
    "(not often). Want me to look out for you like that? Reply **yes**."
)


def _already_suggested_today(user_phone: str) -> bool:
    data = get_user_state(user_phone).get("data") or {}
    return data.get("companion_optin_suggest_date") == date.today().isoformat()


def _mark_suggested(user_phone: str) -> None:
    session = get_user_state(user_phone)
    data = dict(session.get("data") or {})
    data["companion_optin_suggest_date"] = date.today().isoformat()
    set_user_state(user_phone, session["state"], data)


def soft_opt_in_suggestion(
    user_phone: str,
    *,
    prefer: str = "auto",
    intensity: Optional[int] = None,
) -> str:
    """
    Return a trailing hint (or '') and set pending_offer to /remind on or /care on.

    prefer: 'morning' | 'care' | 'auto'
    Skips if already opted in, already suggested today, or another offer is pending.
    """
    if get_pending_offer(user_phone):
        return ""
    if _already_suggested_today(user_phone):
        return ""

    status = get_reminder_status(user_phone)
    morning_on = bool(status.get("enabled"))
    care_on = bool(status.get("care_enabled"))

    choice: Optional[str] = None
    if prefer == "morning" and not morning_on:
        choice = "morning"
    elif prefer == "care" and not care_on:
        choice = "care"
    elif prefer == "auto":
        reason = None
        try:
            from patterns import care_ping_reason

            reason = care_ping_reason(user_phone)
        except Exception:
            reason = None
        low = intensity is not None and intensity <= 4
        if not care_on and (reason or low):
            choice = "care"
        elif not morning_on:
            choice = "morning"
        elif not care_on:
            choice = "care"

    if choice == "morning":
        set_pending_offer(user_phone, "/remind on", keep_state=True)
        _mark_suggested(user_phone)
        return MORNING_HINT
    if choice == "care":
        set_pending_offer(user_phone, "/care on", keep_state=True)
        _mark_suggested(user_phone)
        return CARE_HINT
    return ""
