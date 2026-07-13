"""
Free-text companion routing — makes the bot feel conversational, not menu-only.

When the LLM is configured, greetings and emotional openers get warm, contextual
replies in the same voice as /vent. Otherwise, curated fallbacks keep things human.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from bot_reply import BotReply, Button

GREETING_RE = re.compile(
    r"^(hi+|hello+|hey+|hiya|yo+|sup|good\s+(morning|afternoon|evening|night)|"
    r"howdy|what'?s\s+up|gm+|gn+)\b",
    re.I,
)
THANKS_RE = re.compile(r"^(thanks?|thank\s+you|thx|ty|appreciate)\b", re.I)
GOODBYE_RE = re.compile(
    r"^(bye+|good\s?bye|see\s+ya|good\s?night|gn+|later|cya)\b", re.I
)
MOOD_HINT_RE = re.compile(
    r"\b(feeling|mood|rate|scale|today\s+i'?m|i'?m\s+a\s+\d)\b", re.I
)
VENT_HINTS = (
    "anxious",
    "anxiety",
    "stressed",
    "stress",
    "overwhelmed",
    "sad",
    "depressed",
    "lonely",
    "alone",
    "can't sleep",
    "cant sleep",
    "insomnia",
    "exhausted",
    "burned out",
    "burnt out",
    "panic",
    "worried",
    "scared",
    "heartbroken",
    "crying",
    "rough day",
    "bad day",
    "hard day",
    "need to talk",
    "need someone",
    "vent",
    "struggling",
    "miserable",
    "hopeless",
    "numb",
)

COMPANION_BUTTONS: list[Button] = [
    ("cmd_vent", "Talk it out"),
    ("cmd_checkin", "Check-in"),
    ("cmd_breathe", "Breathe"),
]


def classify_free_text(text: str) -> str:
    """Return intent label for non-command inbound text."""
    t = (text or "").strip()
    if not t:
        return "empty"
    if GREETING_RE.match(t):
        return "greeting"
    if THANKS_RE.match(t):
        return "thanks"
    if GOODBYE_RE.match(t):
        return "goodbye"
    lowered = t.lower()
    if any(h in lowered for h in VENT_HINTS):
        return "vent_hint"
    if MOOD_HINT_RE.search(t) and len(t.split()) <= 12:
        return "mood_hint"
    if len(t.split()) >= 8:
        return "open_share"
    return "unknown"


def _fallback_reply(intent: str, text: str) -> str:
    if intent == "greeting":
        return (
            "Hey — good to hear from you. How are you really doing right now?\n\n"
            "You can vent, do a quick check-in, or just pick something from the menu."
        )
    if intent == "thanks":
        return "You're welcome. I'm here whenever you need me."
    if intent == "goodbye":
        return "Take care of yourself. I'll be here when you want to check back in."
    if intent == "vent_hint":
        return (
            "That sounds like a lot to carry. Want to talk it through?\n\n"
            "Type /vent — or just keep typing here and I'll listen."
        )
    if intent == "mood_hint":
        return (
            "Want to log how you're feeling? Try /checkin for a guided one, "
            "or /mood 6 with a short note."
        )
    if intent == "open_share":
        return (
            "I'm listening. If you want a back-and-forth space to unpack this, "
            "/vent is the best fit — no scripts, just conversation."
        )
    return (
        "I'm here with you. Tell me how you're doing, or open the menu "
        "for check-ins, breathing, and meditation."
    )


def companion_reply(user_phone: str, text: str, intent: str) -> str:
    """Warm reply for free-text messages outside an active flow."""
    try:
        from llm_wellness import companion_chat

        llm = companion_chat(user_phone, text, intent)
        if llm:
            return llm
    except Exception:
        pass
    return _fallback_reply(intent, text)


def handle_free_text(user_phone: str, text: str) -> BotReply:
    """Route casual inbound text to a companion-style reply."""
    intent = classify_free_text(text)
    if intent == "empty":
        return BotReply(
            "I'm here — what's on your mind?",
            list_button_label="Wellness menu",
            list_sections=_menu_sections(),
        )

    msg = companion_reply(user_phone, text, intent)

    if intent == "vent_hint":
        return BotReply(
            msg,
            buttons=[
                ("cmd_vent", "Start vent"),
                ("cmd_breathe", "Breathe"),
                ("cmd_checkin", "Check-in"),
            ],
        )
    if intent == "open_share":
        return BotReply(
            msg,
            buttons=[
                ("cmd_vent", "Talk it out"),
                ("cmd_checkin", "Check-in"),
                ("cmd_breathe", "Breathe"),
            ],
        )
    if intent in ("greeting", "unknown", "mood_hint"):
        return BotReply(
            msg,
            list_button_label="Wellness menu",
            list_sections=_menu_sections(),
        )
    return BotReply(msg)


def _menu_sections():
    from interactive_maps import MAIN_MENU_LIST_SECTIONS

    return MAIN_MENU_LIST_SECTIONS


def should_offer_vent(intent: str) -> bool:
    return intent in ("vent_hint", "open_share")
