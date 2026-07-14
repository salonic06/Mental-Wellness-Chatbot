"""
Wellness-specific LLM brain.

This module turns the generic ``llm_client`` into warm, personalized, and *safe*
wellness replies. Every public function degrades gracefully: if the LLM is not
configured or errors, it returns ``None`` and the caller keeps its existing
deterministic behavior.

Safety model:
- Crisis detection (self-harm/suicide) is handled BEFORE this module ever runs,
  by ``sentiment_nlp.detect_crisis`` in the router. The system prompt below adds
  a second layer of guardrails, but it is never the only safeguard.
- The persona is a *wellness companion*, explicitly NOT a therapist. No
  diagnosis, no medication or treatment advice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import db_paths
from db_sql import execute
import llm_client
from patterns import patterns_context_block

logger = logging.getLogger(__name__)

MAX_VENT_HISTORY_TURNS = 8  # user+assistant pairs kept for in-session context

# Cache translated meditation/breathing script lines per (lang, text hash).
_content_cache: dict = {}

# If the model judges a free-text message to indicate self-harm / suicide risk,
# it returns ONLY this token. The caller then routes to the crisis handler.
# This is a SECOND safety layer behind the deterministic phrase check.
CRISIS_SENTINEL = "[[CRISIS]]"

SAFETY_DIRECTIVE = (
    "SAFETY OVERRIDE (highest priority): If the message expresses any suicidal "
    "thoughts, a wish to die or disappear, intent or plans to harm themselves, "
    "or that they may be in immediate danger, DO NOT reply normally. Instead "
    f"output exactly this token and nothing else: {CRISIS_SENTINEL}"
)

PERSONA = (
    "You are 'Wellness Buddy', a warm, emotionally present companion on WhatsApp. "
    "You sound like a thoughtful friend who remembers context — never like a FAQ bot, "
    "survey form, or scripted IVR. You are NOT a therapist, doctor, or crisis service; "
    "you never diagnose, label conditions, or give medical, medication, legal, or "
    "treatment advice."
)

STYLE = (
    "Style rules: reply in 2-4 short sentences suitable for WhatsApp. Be specific to "
    "what they said — mirror their language and energy. Validate feelings first. Ask at "
    "most one gentle question. No headings, bullet lists, markdown, or feature tours. "
    "Never list slash commands or explain how to use the app unless they explicitly ask. "
    "Avoid clichés ('I'm here for you' alone, 'just breathe'). Sound human and varied."
)


def _base_system(user_phone: str = "", hint_text: str = "") -> str:
    from languages import llm_language_directive

    if user_phone:
        style = STYLE + " " + llm_language_directive(user_phone)
    else:
        style = STYLE
    return f"{PERSONA}\n\n{style}"


def _recent_rows(user_phone: str, days: int = 14):
    """Return (checkins, mood_logs) recent rows for one user, newest first."""
    try:
        conn = db_paths.connect()
        conn.row_factory = None
        c = conn.cursor()
        since = (datetime.now() - timedelta(days=days)).isoformat()
        execute(
            c,
            """SELECT intensity, category, note, created_at FROM checkins
               WHERE user_phone = ? AND created_at >= ?
               ORDER BY created_at DESC LIMIT 20""",
            (user_phone, since),
        )
        checkins = c.fetchall()
        execute(
            c,
            """SELECT intensity, notes, timestamp FROM mood_logs
               WHERE user_phone = ? AND mood != 'crisis' AND timestamp >= ?
               ORDER BY timestamp DESC LIMIT 20""",
            (user_phone, since),
        )
        moods = c.fetchall()
        conn.close()
        return checkins, moods
    except Exception:
        logger.exception("Failed to load user context")
        return [], []


def build_user_context(user_phone: str) -> str:
    """
    A short, privacy-scoped natural-language summary of THIS user's own recent
    entries, used to personalize replies. Returns '' when there is no history.
    """
    checkins, moods = _recent_rows(user_phone)
    if not checkins and not moods:
        return ""

    intensities = [row[0] for row in checkins if row[0] is not None]
    intensities += [row[0] for row in moods if row[0] is not None]
    lines = []
    if intensities:
        avg = sum(intensities) / len(intensities)
        lines.append(f"Average recent mood: {avg:.1f}/10 over {len(intensities)} entries.")

    cats = [(row[1] or "other") for row in checkins]
    if cats:
        top = max(set(cats), key=cats.count)
        lines.append(f"Most common check-in topic lately: {top}.")

    notes = [str(row[2]).strip() for row in checkins if row[2] and str(row[2]).strip()]
    notes += [str(row[1]).strip() for row in moods if row[1] and str(row[1]).strip()]
    notes = [n for n in notes if n][:3]
    if notes:
        joined = " | ".join(notes)
        lines.append(f"Recent notes they wrote: {joined}")

    if not lines:
        return ""

    pattern_block = patterns_context_block(user_phone)
    base = "Context about this person (private, do not quote verbatim):\n" + "\n".join(lines)
    if pattern_block:
        return base + "\n\n" + pattern_block
    return base


def empathetic_vent_reply(
    user_text: str,
    sentiment_bucket: str,
    user_phone: str,
    vent_history: Optional[List[dict]] = None,
) -> Optional[str]:
    """A supportive, context-aware reply to a free-text vent message."""
    context = build_user_context(user_phone)
    tone = sentiment_bucket.replace("_", " ")
    history = _vent_history_to_turns(vent_history or [])

    session_block = ""
    if history:
        session_block = (
            "This is an ongoing vent session — read the prior turns and respond "
            "to their latest message. Do not repeat advice you already gave; "
            "build on what they shared.\n\n"
        )

    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + session_block
        + (f"{context}\n\n" if context else "")
        + (
            f"Detected emotional tone (latest message): {tone}.\n"
            f'Their latest message: "{user_text}"\n\n'
            "Respond as their wellness companion. Reflect something specific they said — "
            "not a generic pep talk. Feel human and present. Offer warmth; at most one "
            "small optional next step in plain language (never slash commands)."
        )
    )
    return llm_client.generate(
        _base_system(user_phone, user_text), user_prompt, temperature=0.9, history=history
    )


def _vent_history_to_turns(vent_history: List[dict]) -> List[tuple]:
    """Convert stored vent session to LLM (role, content) pairs."""
    turns: List[tuple] = []
    for item in vent_history[-MAX_VENT_HISTORY_TURNS * 2 :]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            turns.append((role, content))
    return turns


def personalized_affirmation(user_phone: str) -> Optional[str]:
    """One short affirmation tailored to the user's recent context."""
    context = build_user_context(user_phone)
    user_prompt = (
        f"{context}\n\n" if context else ""
    ) + (
        "Write ONE short, sincere affirmation (1-2 sentences) for this person. "
        "Make it feel earned and specific, not a generic quote. No hashtags, no "
        "quotation marks, no author attribution."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.85, max_tokens=120
    )


def weekly_stats(user_phone: str) -> dict:
    """Compute this-week vs last-week numbers for the weekly summary."""
    conn = db_paths.connect()
    c = conn.cursor()
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).isoformat()
    two_weeks_ago = (now - timedelta(days=14)).isoformat()

    def _avg_count(start: str, end: Optional[str]):
        if end is None:
            execute(
                c,
                """SELECT AVG(intensity), COUNT(*) FROM mood_logs
                   WHERE user_phone = ? AND mood != 'crisis'
                     AND intensity IS NOT NULL AND timestamp >= ?""",
                (user_phone, start),
            )
        else:
            execute(
                c,
                """SELECT AVG(intensity), COUNT(*) FROM mood_logs
                   WHERE user_phone = ? AND mood != 'crisis'
                     AND intensity IS NOT NULL
                     AND timestamp >= ? AND timestamp < ?""",
                (user_phone, start, end),
            )
        row = c.fetchone()
        return (row[0], row[1] or 0)

    this_avg, this_count = _avg_count(week_ago, None)
    last_avg, _ = _avg_count(two_weeks_ago, week_ago)

    execute(
        c,
        """SELECT category, COUNT(*) AS n FROM checkins
           WHERE user_phone = ? AND created_at >= ?
           GROUP BY category ORDER BY n DESC LIMIT 1""",
        (user_phone, week_ago),
    )
    top_row = c.fetchone()
    conn.close()

    return {
        "this_avg": round(this_avg, 1) if this_avg is not None else None,
        "last_avg": round(last_avg, 1) if last_avg is not None else None,
        "entries": this_count,
        "top_topic": top_row[0] if top_row else None,
    }


def _fallback_summary(stats: dict) -> str:
    if not stats["entries"]:
        return (
            "No check-ins logged in the last 7 days yet. Try /checkin or "
            "/mood 7 to start building your weekly picture."
        )
    parts = [f"Your week: average mood {stats['this_avg']}/10 across {stats['entries']} entries."]
    if stats["last_avg"] is not None:
        delta = stats["this_avg"] - stats["last_avg"]
        if delta >= 0.3:
            parts.append(f"That's up from {stats['last_avg']} last week - nice trend.")
        elif delta <= -0.3:
            parts.append(f"That's down from {stats['last_avg']} last week - be gentle with yourself.")
        else:
            parts.append(f"About the same as last week ({stats['last_avg']}).")
    if stats["top_topic"]:
        parts.append(f"Most check-ins were about {stats['top_topic']}.")
    return " ".join(parts)


def companion_chat(user_phone: str, text: str, intent: str) -> Optional[str]:
    """Natural reply when the user sends free text outside a command flow."""
    context = build_user_context(user_phone)
    intent_guide = {
        "greeting": (
            "They said hello. Welcome them warmly like a friend, not an app. "
            "Invite how they're doing — one gentle question. No menus or commands."
        ),
        "thanks": "They thanked you. Acknowledge briefly; leave the door open.",
        "goodbye": "They're signing off. Warm brief send-off — no new tasks.",
        "vent_hint": (
            "They hinted at distress. Validate first; invite them to share more "
            "in plain language (not 'type /vent')."
        ),
        "mood_hint": (
            "They mentioned mood. Acknowledge it; invite a short note about how "
            "they feel, or offer check-in gently in plain language."
        ),
        "open_share": (
            "They shared something substantial. Reflect what you heard specifically; "
            "invite them to say more if they want."
        ),
        "unknown": "Casual message. Be welcoming and curious — no feature list.",
    }.get(intent, "Be a warm wellness companion.")

    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + f"Intent: {intent}. {intent_guide}\n\n"
        f'Their message: "{text}"\n\n'
        "Reply in 1-3 short sentences. No command lists, no bullet points."
    )
    return llm_client.generate(
        _base_system(user_phone, text), user_prompt, temperature=0.85
    )


def chat_open_reply(user_phone: str) -> Optional[str]:
    """Warm opening when the user explicitly starts Talk-it-out / chat mode."""
    context = build_user_context(user_phone)
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + "They just opened a private space to talk. Welcome them like a trusted "
        "friend who has time — not a product script. Invite whatever is on their mind. "
        "Do NOT mention slash commands, menus, buttons, /done, or how to use the app."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.9, max_tokens=120
    )


def chat_already_open_reply(user_phone: str) -> Optional[str]:
    """Soft ack when they re-tap Talk it out while already chatting."""
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        "They're already talking with you and opened the chat option again. "
        "Briefly reassure you're still here and listening; invite them to continue. "
        "No commands, no menus, no instructions."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.85, max_tokens=80
    )


def checkin_closing_reply(
    user_phone: str,
    intensity: int,
    category: str,
    note: str,
    suggested_tip: str,
    suggested_cmd: str,
) -> Optional[str]:
    """Warm wrap-up after a guided check-in saves."""
    context = build_user_context(user_phone)
    note_line = f'Note they added: "{note}".\n' if note else ""
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + f"They just finished a check-in: mood {intensity}/10, topic {category}.\n"
        + note_line
        + f"A helpful next step might be: {suggested_tip} ({suggested_cmd}).\n\n"
        "Write 2-3 warm sentences acknowledging their check-in. Mention the score "
        "naturally. Offer ONE optional next step in plain language — phrase it as "
        "a suggestion, not a yes/no question. Do not list multiple commands."
    )
    return llm_client.generate(
        _base_system(user_phone, note), user_prompt, temperature=0.7
    )


def mood_log_reply(user_phone: str, intensity: int, notes: str) -> Optional[str]:
    """Personalized acknowledgment after /mood."""
    context = build_user_context(user_phone)
    notes_line = f'They wrote: "{notes}".\n' if notes else ""
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + f"They logged mood {intensity}/10.\n"
        + notes_line
        + "Respond warmly in 2-3 sentences. Validate their feeling. Suggest ONE "
        "gentle optional next step (vent, breathe, check-in, or meditation) in "
        "plain language — no slash commands unless natural."
    )
    return llm_client.generate(
        _base_system(user_phone, notes), user_prompt, temperature=0.75
    )


def localize_wellness_content(user_phone: str, english_text: str, kind: str = "meditation") -> str:
    """
    Translate scripted wellness content (meditation parts) into the user's language.
    Falls back to English when LLM is off or translation fails.
    """
    from languages import LLM_LANG, effective_language

    text = (english_text or "").strip()
    if not text:
        return text

    lang = effective_language(user_phone)
    if lang == "en":
        return text

    cache_key = (lang, kind, text)
    if cache_key in _content_cache:
        return _content_cache[cache_key]

    if not llm_client.is_enabled():
        return text

    target = LLM_LANG.get(lang, "English")
    prompt = (
        f"Translate this {kind} guidance into {target}. "
        "Keep the same calm, gentle tone. Preserve line breaks and ellipsis (...). "
        "Do not add commands or commentary. Output ONLY the translation.\n\n"
        f"{text}"
    )
    out = llm_client.generate(
        "You are a precise translator for wellness meditation and breathing scripts.",
        prompt,
        temperature=0.2,
        max_tokens=min(900, max(120, len(text) * 2)),
    )
    result = (out or text).strip()
    _content_cache[cache_key] = result
    return result


def post_session_reflection(user_phone: str, activity: str) -> Optional[str]:
    """Short closing line after meditation or breathing."""
    context = build_user_context(user_phone)
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + f"They just finished: {activity}.\n\n"
        "One or two sentences — acknowledge the pause they took. Optionally ask "
        "how they feel now. No commands unless one fits naturally."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.65, max_tokens=100
    )


def personalized_nudge(user_phone: str) -> Optional[str]:
    """Morning reminder body when LLM is available."""
    context = build_user_context(user_phone)
    if not context:
        return None
    user_prompt = (
        f"{context}\n\n"
        "Write a brief good-morning check-in nudge (2 sentences max). Reference "
        "their recent patterns gently — do not quote notes verbatim. Invite them "
        "to share how they feel or do a quick check-in in plain language — no slash "
        "commands. No hashtags."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.75, max_tokens=120
    )


def personalized_care_ping(user_phone: str, reason: str) -> Optional[str]:
    """Afternoon companion check-in when mood/patterns look rough."""
    context = build_user_context(user_phone)
    reason_hint = {
        "trend_down": "Their mood scores have dipped lately.",
        "low_avg": "Their recent average mood has been on the lower side.",
        "heavy_vent": "Recent conversations carried heavier emotional weight.",
        "quiet_checkins": "They used to check in and have gone quiet for a couple of days.",
    }.get(reason, "They could use a gentle check-in.")
    user_prompt = (
        f"{SAFETY_DIRECTIVE}\n\n"
        + (f"{context}\n\n" if context else "")
        + f"Reason for reaching out (internal, do not quote): {reason_hint}\n\n"
        "Write a short WhatsApp message (2 sentences max) like a caring friend "
        "asking how they are holding up. Warm, no diagnosis, no lecture, no "
        "feature-spam. Do not mention crisis helplines unless they already said "
        "they are in danger. No hashtags, no slash commands required."
    )
    return llm_client.generate(
        _base_system(user_phone), user_prompt, temperature=0.7, max_tokens=120
    )


def _summary_header(stats: dict) -> str:
    lines = [
        "*Your week*",
        f"Average mood: {stats['this_avg']}/10 · {stats['entries']} entries",
    ]
    if stats["last_avg"] is not None:
        delta = stats["this_avg"] - stats["last_avg"]
        if delta >= 0.3:
            lines.append(f"Trend: up from {stats['last_avg']} last week.")
        elif delta <= -0.3:
            lines.append(f"Trend: down from {stats['last_avg']} last week.")
        else:
            lines.append(f"Trend: steady (last week {stats['last_avg']}).")
    if stats["top_topic"]:
        lines.append(f"Top topic: {stats['top_topic']}.")
    return "\n".join(lines)


def weekly_summary_text(user_phone: str) -> str:
    """
    Structured weekly stats + optional LLM narrative. Always returns a string.
    """
    stats = weekly_stats(user_phone)
    if not stats["entries"]:
        return _fallback_summary(stats)

    header = _summary_header(stats)
    patterns = patterns_context_block(user_phone)

    user_prompt = (
        "Write 2-3 warm sentences reflecting on this person's week. "
        "Do NOT repeat the numeric stats (they appear above your message). "
        "No bullet lists. End with one small optional suggestion, not a yes/no question.\n\n"
        f"Average mood this week: {stats['this_avg']}/10 ({stats['entries']} entries).\n"
        f"Average mood last week: {stats['last_avg']}.\n"
        f"Most frequent topic: {stats['top_topic']}."
    )
    if patterns:
        user_prompt += f"\n\n{patterns}"
    llm = llm_client.generate(_base_system(user_phone), user_prompt, temperature=0.6)
    narrative = llm or "Keep noticing what helps — even small check-ins add up."
    return f"{header}\n\n{narrative}"
