"""
Free-text companion routing — one persona, many modes.

Emotional or open messages auto-enter unified chat mode (same as /vent).
Greetings and sign-offs stay lightweight one-shots.
"""

from __future__ import annotations

import re

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

# Intents that open multi-turn chat automatically
AUTO_CHAT_INTENTS = frozenset({"vent_hint", "open_share", "ambient"})


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
    if len(t.split()) >= 4:
        return "ambient"
    return "unknown"


def _fallback_reply(intent: str, text: str) -> str:
    if intent == "greeting":
        return (
            "Hey — good to hear from you. How are you really doing right now?"
        )
    if intent == "thanks":
        return "You're welcome. I'm here whenever you need me."
    if intent == "goodbye":
        return "Take care of yourself. I'll be here when you want to check back in."
    if intent in AUTO_CHAT_INTENTS:
        return "I'm listening — tell me more."
    if intent == "mood_hint":
        return (
            "Want to log how you're feeling? /checkin walks you through it, "
            "or send /mood 6 with a short note for a quick log."
        )
    return "I'm here with you. What's on your mind?"


def companion_reply(user_phone: str, text: str, intent: str) -> str:
    """Warm one-shot reply when not entering chat mode."""
    try:
        from llm_wellness import companion_chat

        llm = companion_chat(user_phone, text, intent)
        if llm:
            return llm
    except Exception:
        pass
    return _fallback_reply(intent, text)


def _chat_followup_buttons() -> list[Button]:
    from interactive_maps import CHAT_FOLLOWUP_BUTTONS

    return CHAT_FOLLOWUP_BUTTONS


def handle_free_text(user_phone: str, text: str) -> BotReply:
    """Route casual inbound text — auto-enter chat for emotional/open messages."""
    intent = classify_free_text(text)

    if intent == "empty":
        return BotReply(
            "I'm here — what's on your mind?",
            list_button_label="Wellness menu",
            list_sections=_menu_sections(),
        )

    if intent in AUTO_CHAT_INTENTS:
        from chat_flow import enter_chat, handle_chat_message

        enter_chat(user_phone)
        msg = handle_chat_message(user_phone, text) or "Tell me more."
        return BotReply(msg, buttons=_chat_followup_buttons())

    # Short affirmatives without pending offer → enter chat to continue thread
    from session_offers import get_pending_offer, is_affirmative

    if is_affirmative(text) and not get_pending_offer(user_phone):
        from chat_flow import enter_chat, handle_chat_message

        enter_chat(user_phone)
        msg = handle_chat_message(user_phone, text) or "Tell me more."
        return BotReply(msg, buttons=_chat_followup_buttons())

    msg = companion_reply(user_phone, text, intent)

    if intent == "mood_hint":
        return BotReply(
            msg,
            buttons=[
                ("cmd_checkin", "Check-in"),
                ("cmd_breathe", "Breathe"),
                ("cmd_summary", "My week"),
            ],
        )
    if intent in ("greeting", "unknown"):
        return BotReply(
            msg,
            list_button_label="Wellness menu",
            list_sections=_menu_sections(),
        )
    return BotReply(msg)


def _menu_sections():
    from interactive_maps import MAIN_MENU_LIST_SECTIONS

    return MAIN_MENU_LIST_SECTIONS
