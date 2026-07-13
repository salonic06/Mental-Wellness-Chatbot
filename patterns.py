"""
Pattern detection over a user's own wellness history.

Feeds the LLM context layer and weekly summaries — never exposes raw vent text
to admins; only aggregated signals.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import db_paths

CHAT_STATE = "chatting"
LEGACY_VENT_STATE = "venting"
CHAT_STATES = frozenset({CHAT_STATE, LEGACY_VENT_STATE})


def detect_user_patterns(user_phone: str, days: int = 14) -> Dict[str, Any]:
    """Return structured + human insight lines for one user."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = db_paths.connect()
    c = conn.cursor()

    c.execute(
        """SELECT intensity, category, note, created_at FROM checkins
           WHERE user_phone = ? AND created_at >= ?
           ORDER BY created_at DESC""",
        (user_phone, since),
    )
    checkins = c.fetchall()

    c.execute(
        """SELECT intensity, timestamp FROM mood_logs
           WHERE user_phone = ? AND mood != 'crisis' AND intensity IS NOT NULL
             AND timestamp >= ?
           ORDER BY timestamp DESC""",
        (user_phone, since),
    )
    moods = c.fetchall()

    c.execute(
        """SELECT sentiment_bucket, COUNT(*) FROM vent_logs
           WHERE user_phone = ? AND is_crisis = 0 AND created_at >= ?
           GROUP BY sentiment_bucket""",
        (user_phone, since),
    )
    vent_buckets = dict(c.fetchall())

    conn.close()

    intensities = [r[0] for r in checkins if r[0] is not None]
    intensities += [r[0] for r in moods if r[0] is not None]

    cats = Counter((r[1] or "other").lower() for r in checkins)
    top_cat, top_cat_n = cats.most_common(1)[0] if cats else (None, 0)

    mid = len(intensities) // 2
    first_half = intensities[mid:] if intensities else []
    second_half = intensities[:mid] if intensities else []
    trend = "stable"
    if first_half and second_half:
        delta = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
        if delta >= 0.4:
            trend = "up"
        elif delta <= -0.4:
            trend = "down"

    negative_vent = sum(
        vent_buckets.get(k, 0)
        for k in ("strong_negative", "mild_negative")
    )
    total_vent = sum(vent_buckets.values())
    neg_ratio = round(negative_vent / total_vent, 2) if total_vent else None

    insights: List[str] = []
    if top_cat and top_cat_n >= 2:
        insights.append(f"{top_cat} has come up {top_cat_n} times in recent check-ins.")
    if trend == "down" and len(intensities) >= 4:
        insights.append("Mood scores have dipped compared to earlier this fortnight.")
    elif trend == "up" and len(intensities) >= 4:
        insights.append("Mood scores are trending upward lately.")
    if neg_ratio and neg_ratio >= 0.5 and total_vent >= 3:
        insights.append("Several recent conversations carried heavy emotional weight.")

    avg = round(sum(intensities) / len(intensities), 1) if intensities else None

    return {
        "days": days,
        "entry_count": len(intensities),
        "avg_mood": avg,
        "mood_trend": trend,
        "top_category": top_cat,
        "top_category_count": top_cat_n,
        "vent_sessions": total_vent,
        "negative_vent_ratio": neg_ratio,
        "insights": insights,
    }


def global_insights(days: int = 14) -> Dict[str, Any]:
    """Aggregate patterns across all users — safe for admin dashboard."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = db_paths.connect()
    c = conn.cursor()

    c.execute(
        """SELECT ROUND(AVG(intensity), 2), COUNT(*)
           FROM mood_logs
           WHERE mood != 'crisis' AND intensity IS NOT NULL AND timestamp >= ?""",
        (since,),
    )
    mood_row = c.fetchone()
    avg_mood, mood_n = (mood_row[0], mood_row[1] or 0) if mood_row else (None, 0)

    c.execute(
        """SELECT category, COUNT(*) FROM checkins
           WHERE created_at >= ? GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5""",
        (since,),
    )
    top_categories = [{"category": r[0], "count": r[1]} for r in c.fetchall()]

    c.execute(
        """SELECT sentiment_bucket, COUNT(*) FROM vent_logs
           WHERE is_crisis = 0 AND created_at >= ?
           GROUP BY sentiment_bucket""",
        (since,),
    )
    vent_tone = {r[0]: r[1] for r in c.fetchall()}

    c.execute(
        "SELECT COUNT(*) FROM vent_logs WHERE is_crisis = 1 AND created_at >= ?",
        (since,),
    )
    crisis_n = c.fetchone()[0] or 0
    conn.close()

    insights: List[str] = []
    if top_categories:
        top = top_categories[0]
        insights.append(
            f"Most logged topic lately: {top['category']} ({top['count']} check-ins)."
        )
    neg = vent_tone.get("strong_negative", 0) + vent_tone.get("mild_negative", 0)
    total_vent = sum(vent_tone.values())
    if total_vent >= 3 and neg / total_vent >= 0.45:
        insights.append("Conversation tone has leaned heavier recently.")
    if crisis_n:
        insights.append(f"{crisis_n} crisis safety flag(s) in the last {days} days.")

    return {
        "days": days,
        "avg_mood": avg_mood,
        "mood_entries": mood_n,
        "top_categories": top_categories,
        "vent_tone": vent_tone,
        "crisis_events": crisis_n,
        "insights": insights,
    }


def patterns_context_block(user_phone: str) -> str:
    """Short block for LLM system context."""
    p = detect_user_patterns(user_phone)
    if not p["insights"] and p["avg_mood"] is None:
        return ""
    lines = []
    if p["avg_mood"] is not None:
        lines.append(f"Recent average mood: {p['avg_mood']}/10 ({p['entry_count']} entries).")
    lines.extend(p["insights"][:3])
    return "Observed patterns (use gently, do not quote as diagnosis):\n" + "\n".join(lines)
