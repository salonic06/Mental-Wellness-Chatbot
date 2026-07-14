"""Map WhatsApp interactive IDs ↔ bot commands / check-in values."""

from __future__ import annotations

from typing import Dict, List, Tuple

from bot_reply import Button

# Inbound: button/list id → text passed to process_message
INTERACTIVE_TO_TEXT: Dict[str, str] = {
    "cmd_checkin": "/checkin",
    "cmd_vent": "/vent",
    "cmd_meditate": "/meditate",
    "cmd_breathe": "/breathe",
    "cmd_affirmation": "/affirmation",
    "cmd_summary": "/summary",
    "cmd_analyze": "/summary",
    "cmd_help": "/help",
    "cmd_cancel": "/cancel",
    "med_quick": "/meditate quick",
    "med_medium": "/meditate medium",
    "med_long": "/meditate long",
    "breathe_calm": "/breathe calm",
    "breathe_relaxation": "/breathe relaxation",
    "breathe_energize": "/breathe energize",
    "vent_done": "/done",
    "cat_work": "work",
    "cat_health": "health",
    "cat_relationships": "relationships",
    "cat_studies": "studies",
    "cat_other": "other",
}

for _code in ("en", "hi", "mr", "gu", "bn"):
    INTERACTIVE_TO_TEXT[f"lang_{_code}"] = f"lang_{_code}"

INTERACTIVE_TO_TEXT["cmd_language"] = "/language"

MAIN_MENU_BUTTONS: List[Button] = [
    ("cmd_checkin", "Check-in"),
    ("cmd_vent", "Vent"),
    ("cmd_help", "Help"),
]

MAIN_MENU_LIST_SECTIONS = [
    {
        "title": "Wellness",
        "rows": [
            {"id": "cmd_checkin", "title": "Check-in", "description": "Mood + topic (guided)"},
            {"id": "cmd_vent", "title": "Talk it out", "description": "Open conversation"},
            {"id": "cmd_meditate", "title": "Meditate", "description": "3 / 10 / 20 min guided"},
            {"id": "cmd_breathe", "title": "Breathe", "description": "Calm · relax · energize"},
            {"id": "cmd_affirmation", "title": "Affirmation", "description": "Personalized boost"},
            {"id": "cmd_summary", "title": "My week", "description": "Reflection + trends"},
        ],
    }
]

MEDITATION_BUTTONS: List[Button] = [
    ("med_quick", "Quick (3 min)"),
    ("med_medium", "Medium (10m)"),
    ("med_long", "Long (20 min)"),
]

BREATHE_BUTTONS: List[Button] = [
    ("breathe_calm", "Calm"),
    ("breathe_relaxation", "Relaxation"),
    ("breathe_energize", "Energize"),
]

CHECKIN_CATEGORY_LIST = [
    {
        "title": "Topic",
        "rows": [
            {"id": "cat_work", "title": "Work", "description": "Job / career"},
            {"id": "cat_health", "title": "Health", "description": "Body / mind"},
            {"id": "cat_relationships", "title": "Relationships", "description": "Family / friends"},
            {"id": "cat_studies", "title": "Studies", "description": "School / exams"},
            {"id": "cat_other", "title": "Other", "description": "Anything else"},
        ],
    }
]

CHAT_FOLLOWUP_BUTTONS: List[Button] = [
    ("vent_done", "Pause chat"),
    ("cmd_breathe", "Breathe"),
    ("cmd_checkin", "Check-in"),
]

# Legacy alias
VENT_FOLLOWUP_BUTTONS = CHAT_FOLLOWUP_BUTTONS


def resolve_inbound_text(raw: str) -> str:
    """Turn interactive payload id into command or check-in value."""
    key = (raw or "").strip()
    return INTERACTIVE_TO_TEXT.get(key, key)
