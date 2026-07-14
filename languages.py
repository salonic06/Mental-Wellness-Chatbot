"""User language preference, script detection, and localized UI (with English fallback)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bot_reply import BotReply, Button
from db_paths import connect
from db_sql import execute

ButtonList = List[Button]

# code, native label (picker), English name (LLM)
INDIAN_LANGUAGES: List[Tuple[str, str, str]] = [
    ("en", "English", "English"),
    ("hi", "हिंदी", "Hindi"),
    ("mr", "मराठी", "Marathi"),
    ("gu", "ગુજરાતી", "Gujarati"),
    ("bn", "বাংলা", "Bengali"),
    ("ta", "தமிழ்", "Tamil"),
    ("te", "తెలుగు", "Telugu"),
    ("kn", "ಕನ್ನಡ", "Kannada"),
    ("ml", "മലയാളം", "Malayalam"),
    ("pa", "ਪੰਜਾਬੀ", "Punjabi"),
    ("ur", "اردو", "Urdu"),
]

# First page of WhatsApp list picker (max 5 + "More languages" row).
LANG_PICKER_TOP_CODES = ("en", "hi", "mr", "gu", "bn")

SUPPORTED = frozenset(code for code, _, _ in INDIAN_LANGUAGES)
DEFAULT_LANG = "en"

# WhatsApp interactive lists: max 10 rows total across all sections.
WHATSAPP_LIST_MAX_ROWS = 10
LANG_PICKER_MORE_ID = "lang_picker_more"

_LANG_BY_CODE = {code: (code, native, english) for code, native, english in INDIAN_LANGUAGES}
LANG_PICKER_TOP = [_LANG_BY_CODE[c] for c in LANG_PICKER_TOP_CODES]
LANG_PICKER_MORE = [entry for entry in INDIAN_LANGUAGES if entry[0] not in LANG_PICKER_TOP_CODES]

SCRIPT_DETECTORS: List[Tuple[str, re.Pattern[str]]] = [
    ("bn", re.compile(r"[\u0980-\u09FF]")),
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),
    ("te", re.compile(r"[\u0C00-\u0C7F]")),
    ("gu", re.compile(r"[\u0A80-\u0AFF]")),
    ("kn", re.compile(r"[\u0C80-\u0CFF]")),
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),
    ("pa", re.compile(r"[\u0A00-\u0A7F]")),
    ("ur", re.compile(r"[\u0600-\u06FF]")),
    ("hi", re.compile(r"[\u0900-\u097F]")),  # Devanagari — Hindi/Marathi; default Hindi
]

LANG_ALIASES: Dict[str, str] = {
    "english": "en",
    "hindi": "hi",
    "bengali": "bn",
    "bangla": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
}

LANG_SET_MSG: Dict[str, str] = {
    "en": "Language set to English.",
    "hi": "भाषा हिंदी में सेट हो गई।",
    "bn": "ভাষা বাংলায় সেট হয়েছে।",
    "ta": "மொழி தமிழில் அமைக்கப்பட்டது.",
    "te": "భాష తెలుగులో సెట్ చేయబడింది.",
    "mr": "भाषा मराठीत सेट केली.",
    "gu": "ભાષા ગુજરાતીમાં સેટ થઈ.",
    "kn": "ಭಾಷೆ ಕನ್ನಡದಲ್ಲಿ ಹೊಂದಿಸಲಾಗಿದೆ.",
    "ml": "ഭാഷ മലയാളത്തിൽ സജ്ജമാക്കി.",
    "pa": "ਭਾਸ਼ਾ ਪੰਜਾਬੀ ਵਿੱਚ ਸੈੱਟ ਹੋ ਗਈ।",
    "ur": "زبان اردو میں سیٹ ہو گئی۔",
}

LLM_LANG: Dict[str, str] = {
    "en": "English",
    "hi": "Hindi (Devanagari script)",
    "bn": "Bengali (Bangla script)",
    "ta": "Tamil (Tamil script)",
    "te": "Telugu (Telugu script)",
    "mr": "Marathi (Devanagari script)",
    "gu": "Gujarati (Gujarati script)",
    "kn": "Kannada (Kannada script)",
    "ml": "Malayalam (Malayalam script)",
    "pa": "Punjabi (Gurmukhi script)",
    "ur": "Urdu (Arabic/Nastaliq script)",
}

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": (
            "Hey — I'm your wellness companion.\n\n"
            "I'm here for check-ins, venting, breathing, and quiet moments — "
            "not therapy, just a steady presence that remembers your mood over time.\n\n"
            "Tell me how you're doing, or tap the menu below."
        ),
        "language_pick": (
            "Choose your language:\n\n"
            "I'll reply in your language from now on. Change anytime with /language"
        ),
        "help": (
            "I'm your wellness companion — talk naturally or tap the menu.\n\n"
            "• /checkin — guided mood log\n"
            "• Just talk — I'll listen\n"
            "• /summary — your week + patterns\n"
            "• /language — change language\n\n"
            "Tap *Quick actions* below."
        ),
        "menu_label": "Wellness menu",
        "help_menu_label": "Quick actions",
        "lang_list_btn": "Choose language",
        "checkin_topic_label": "Pick topic",
        "meditation_choose": "Choose a meditation length:",
        "checkin_start": (
            "Quick check-in — no wrong answers.\n\n"
            "How are you right now? Reply 1 (low) to 10 (great).\n\n"
            "/cancel anytime."
        ),
        "checkin_category_prompt": "What area is this mostly about? Pick below or reply 1–5.",
        "checkin_note_prompt": "Any short note? (Optional — reply 'skip')",
        "checkin_cancel": "Check-in cancelled. /help anytime.",
        "checkin_invalid_number": "Please reply with a whole number from 1 to 10.",
        "checkin_out_of_range": "Please use a number between 1 and 10.",
        "checkin_invalid_category": "Please choose a topic from the list.",
        "section_wellness": "Wellness",
        "section_languages": "Languages",
    },
    "hi": {
        "welcome": (
            "नमस्ते — मैं आपका wellness companion हूँ।\n\n"
            "check-in, बातचीत, breathing और meditation — therapy नहीं।\n\n"
            "बताइए आप कैसे हैं, या menu खोलें।"
        ),
        "language_pick": (
            "अपनी भाषा चुनें:\n\n"
            "अब से आपकी भाषा में जवाब दूँगा। /language से बदलें।"
        ),
        "help": (
            "Naturally बात करें या menu use करें।\n\n"
            "• /checkin — mood log\n"
            "• /summary — hafta summary\n"
            "• /language — भाषा बदलें"
        ),
        "menu_label": "Wellness menu",
        "help_menu_label": "विकल्प",
        "lang_list_btn": "भाषा चुनें",
        "checkin_topic_label": "विषय",
        "meditation_choose": "Meditation length:",
        "checkin_start": "Mood 1 (low) se 10 (great)? /cancel anytime.",
        "checkin_category_prompt": "Kis area ke baare mein? Neeche topic chunen.",
        "checkin_note_prompt": "Chhota note? ('skip' likhen)",
        "checkin_cancel": "Check-in radd. /help anytime.",
        "checkin_invalid_number": "1 se 10 ke beech number.",
        "checkin_out_of_range": "1 se 10 use karein.",
        "checkin_invalid_category": "List se topic chunen.",
        "section_wellness": "Wellness",
        "section_languages": "भाषाएँ",
    },
}

MENU_ROWS: Dict[str, List[Dict[str, str]]] = {
    "en": [
        {"id": "cmd_checkin", "title": "Check-in", "description": "Mood + topic"},
        {"id": "cmd_vent", "title": "Talk it out", "description": "Open chat"},
        {"id": "cmd_meditate", "title": "Meditate", "description": "3 / 10 / 20 min"},
        {"id": "cmd_breathe", "title": "Breathe", "description": "Calm · relax"},
        {"id": "cmd_affirmation", "title": "Affirmation", "description": "Boost"},
        {"id": "cmd_summary", "title": "My week", "description": "Trends"},
    ],
    "hi": [
        {"id": "cmd_checkin", "title": "Check-in", "description": "Mood + topic"},
        {"id": "cmd_vent", "title": "Baat karein", "description": "Khul kar baat"},
        {"id": "cmd_meditate", "title": "Meditate", "description": "3 / 10 / 20 min"},
        {"id": "cmd_breathe", "title": "Breathe", "description": "Calm"},
        {"id": "cmd_affirmation", "title": "Affirmation", "description": "Boost"},
        {"id": "cmd_summary", "title": "Mera hafta", "description": "Trends"},
    ],
}

MEDITATION_BUTTONS_I18N: Dict[str, ButtonList] = {
    lang: [
        ("med_quick", "Quick (3 min)"),
        ("med_medium", "Medium (10m)"),
        ("med_long", "Long (20 min)"),
    ]
    for lang in SUPPORTED
}

BREATHE_BUTTONS_I18N: Dict[str, ButtonList] = {
    lang: [
        ("breathe_calm", "Calm"),
        ("breathe_relaxation", "Relaxation"),
        ("breathe_energize", "Energize"),
    ]
    for lang in SUPPORTED
}

CHAT_FOLLOWUP_I18N: Dict[str, ButtonList] = {
    "en": [
        ("vent_done", "Pause chat"),
        ("cmd_breathe", "Breathe"),
        ("cmd_checkin", "Check-in"),
    ],
    "hi": [
        ("vent_done", "Chat रोकें"),
        ("cmd_breathe", "Breathe"),
        ("cmd_checkin", "Check-in"),
    ],
}
for code in SUPPORTED:
    if code not in CHAT_FOLLOWUP_I18N:
        CHAT_FOLLOWUP_I18N[code] = CHAT_FOLLOWUP_I18N["en"]

CHECKIN_CATEGORIES_I18N: Dict[str, List[Dict[str, str]]] = {
    lang: [
        {"id": "cat_work", "title": "Work", "description": "Job / career"},
        {"id": "cat_health", "title": "Health", "description": "Body / mind"},
        {"id": "cat_relationships", "title": "Relationships", "description": "Family"},
        {"id": "cat_studies", "title": "Studies", "description": "School"},
        {"id": "cat_other", "title": "Other", "description": "Other"},
    ]
    for lang in SUPPORTED
}


def normalize_lang(code: Optional[str]) -> str:
    if not code:
        return DEFAULT_LANG
    code = code.strip().lower()
    if code.startswith("lang_"):
        code = code[5:]
    if code in LANG_ALIASES:
        code = LANG_ALIASES[code]
    return code if code in SUPPORTED else DEFAULT_LANG


def detect_language_from_text(text: str) -> Optional[str]:
    if not text or text.strip().startswith("/"):
        return None
    for code, pattern in SCRIPT_DETECTORS:
        if pattern.search(text):
            return code
    return None


def parse_language_choice(raw: str) -> Optional[str]:
    key = (raw or "").strip().lower()
    if key.startswith("lang_"):
        return normalize_lang(key)
    if key in LANG_ALIASES:
        return LANG_ALIASES[key]
    if key in SUPPORTED:
        return key
    return None


def list_row_count(sections: List[Dict[str, Any]]) -> int:
    return sum(len(section.get("rows") or []) for section in sections)


def language_list_sections(page: int = 1) -> List[Dict[str, Any]]:
    if page == 2:
        return [
            {
                "title": "More languages",
                "rows": [
                    {"id": f"lang_{code}", "title": native, "description": english}
                    for code, native, english in LANG_PICKER_MORE
                ],
            }
        ]

    rows = [
        {"id": f"lang_{code}", "title": native, "description": english}
        for code, native, english in LANG_PICKER_TOP
    ]
    if LANG_PICKER_MORE:
        more_label = ", ".join(native for _, native, _ in LANG_PICKER_MORE)
        rows.append(
            {
                "id": LANG_PICKER_MORE_ID,
                "title": "More languages",
                "description": more_label[:72],
            }
        )
    return [{"title": "Popular", "rows": rows}]


def language_picker_page2_reply(user_phone: str) -> BotReply:
    return BotReply(
        t(user_phone, "language_pick"),
        list_button_label=t(user_phone, "lang_list_btn"),
        list_sections=language_list_sections(page=2),
    )


def language_picker_reply(user_phone: str) -> BotReply:
    return BotReply(
        t(user_phone, "language_pick"),
        list_button_label=t(user_phone, "lang_list_btn"),
        list_sections=language_list_sections(),
    )


def language_set_message(lang: str) -> str:
    lang = normalize_lang(lang)
    return LANG_SET_MSG.get(lang, f"Language set to {LLM_LANG.get(lang, lang)}.")


def maybe_auto_set_language(user_phone: str, text: str) -> Optional[str]:
    """Persist detected language for new users. Returns lang if set."""
    if not needs_language_setup(user_phone):
        return None
    detected = detect_language_from_text(text)
    if not detected:
        return None
    set_user_language(user_phone, detected)
    return detected


def get_user_language(user_phone: str) -> Optional[str]:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "SELECT preferred_language FROM users WHERE phone_number = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row or row[0] is None or str(row[0]).strip() == "":
        return None
    return normalize_lang(row[0])


def effective_language(user_phone: str, hint_text: str = "") -> str:
    stored = get_user_language(user_phone)
    if stored:
        return stored
    detected = detect_language_from_text(hint_text)
    return detected or DEFAULT_LANG


def needs_language_setup(user_phone: str) -> bool:
    return get_user_language(user_phone) is None


def set_user_language(user_phone: str, lang: str) -> str:
    from datetime import datetime

    lang = normalize_lang(lang)
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "UPDATE users SET preferred_language = ? WHERE phone_number = ?",
            (lang, user_phone),
        )
        if c.rowcount == 0:
            execute(
                c,
                """INSERT INTO users (phone_number, joined_date, preferred_language)
                   VALUES (?, ?, ?)""",
                (user_phone, datetime.now(), lang),
            )
        conn.commit()
    finally:
        conn.close()
    return lang


def t(user_phone: str, key: str, *, hint_text: str = "") -> str:
    lang = effective_language(user_phone, hint_text)
    bucket = STRINGS.get(lang) or STRINGS["en"]
    return bucket.get(key, STRINGS["en"].get(key, key))


def llm_language_directive(user_phone: str, hint_text: str = "") -> str:
    lang = effective_language(user_phone, hint_text)
    name = LLM_LANG.get(lang, "English")
    return (
        f"IMPORTANT: Reply entirely in {name}. Match the user's language and script. "
        "Keep 2-4 short WhatsApp-friendly sentences. You may use common English "
        "wellness words (check-in, meditate) when natural."
    )


def main_menu_sections(user_phone: str) -> List[Dict[str, Any]]:
    lang = effective_language(user_phone)
    rows = MENU_ROWS.get(lang) or MENU_ROWS["en"]
    return [{"title": t(user_phone, "section_wellness"), "rows": rows}]


def meditation_buttons(user_phone: str) -> ButtonList:
    return MEDITATION_BUTTONS_I18N[effective_language(user_phone)]


def breathe_buttons(user_phone: str) -> ButtonList:
    return BREATHE_BUTTONS_I18N[effective_language(user_phone)]


def chat_followup_buttons(user_phone: str) -> ButtonList:
    return CHAT_FOLLOWUP_I18N[effective_language(user_phone)]


def checkin_category_list(user_phone: str) -> List[Dict[str, Any]]:
    lang = effective_language(user_phone)
    rows = CHECKIN_CATEGORIES_I18N.get(lang) or CHECKIN_CATEGORIES_I18N["en"]
    return [{"title": t(user_phone, "checkin_topic_label"), "rows": rows}]
