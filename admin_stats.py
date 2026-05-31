"""Admin-only stats from SQLite (Cloud API mode — no Twilio)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict

from db_paths import DATABASE_PATH, connect


def fetch_bot_stats() -> Dict[str, Any]:
    if not DATABASE_PATH.exists():
        return {"error": "database_missing", "path": str(DATABASE_PATH)}

    conn = connect()
    try:
        c = conn.cursor()

        def scalar(sql: str, params: tuple = ()) -> int:
            row = c.execute(sql, params).fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        week_ago = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        stats = {
            "users": scalar("SELECT COUNT(*) FROM users"),
            "mood_logs": scalar("SELECT COUNT(*) FROM mood_logs WHERE mood != 'crisis'"),
            "crisis_mood_flags": scalar("SELECT COUNT(*) FROM mood_logs WHERE mood = 'crisis'"),
            "checkins": scalar("SELECT COUNT(*) FROM checkins"),
            "vent_events": scalar("SELECT COUNT(*) FROM vent_logs WHERE is_crisis = 0"),
            "vent_crises": scalar("SELECT COUNT(*) FROM vent_logs WHERE is_crisis = 1"),
            "active_meditations": scalar("SELECT COUNT(*) FROM active_meditations"),
            "reminders_enabled": scalar(
                "SELECT COUNT(*) FROM daily_reminders WHERE enabled = 1"
            ),
            "messages_last_7d": scalar(
                "SELECT COUNT(*) FROM mood_logs WHERE timestamp >= ?",
                (week_ago,),
            )
            + scalar(
                "SELECT COUNT(*) FROM checkins WHERE created_at >= ?",
                (week_ago,),
            )
            + scalar(
                "SELECT COUNT(*) FROM vent_logs WHERE created_at >= ?",
                (week_ago,),
            ),
            "database_path": str(DATABASE_PATH),
            "meditation_nudges": os.environ.get("ENABLE_MEDITATION_NUDGES", "true"),
            "daily_checkin_nudges": os.environ.get("ENABLE_DAILY_CHECKIN_NUDGES", "false"),
        }
        return stats
    except sqlite3.Error as exc:
        return {"error": "query_failed", "detail": str(exc)}
    finally:
        conn.close()


def format_stats_message(stats: Dict[str, Any]) -> str:
    if stats.get("error"):
        return f"Stats unavailable: {stats['error']}"

    return (
        "*Bot stats*\n"
        f"Users: {stats['users']}\n"
        f"Mood logs: {stats['mood_logs']} (crisis flags: {stats['crisis_mood_flags']})\n"
        f"Check-ins: {stats['checkins']}\n"
        f"Vent events: {stats['vent_events']} (crisis: {stats['vent_crises']})\n"
        f"Active meditations: {stats['active_meditations']}\n"
        f"Daily reminders on: {stats['reminders_enabled']}\n"
        f"Activity (7d, approx): {stats['messages_last_7d']} logged events\n"
        f"DB: {stats['database_path']}\n"
        f"Meditation nudges: {stats['meditation_nudges']}\n"
        f"Daily check-in nudges: {stats['daily_checkin_nudges']}"
    )


def format_ping_message() -> str:
    token = bool((os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip())
    phone_id = bool((os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip())
    verify = bool((os.environ.get("META_VERIFY_TOKEN") or "").strip())
    secret = bool((os.environ.get("META_APP_SECRET") or "").strip())
    display = (os.environ.get("WHATSAPP_DISPLAY_NUMBER") or "").strip()

    lines = [
        "*Config check*",
        f"WHATSAPP_ACCESS_TOKEN: {'set' if token else 'MISSING'}",
        f"WHATSAPP_PHONE_NUMBER_ID: {'set' if phone_id else 'MISSING'}",
        f"META_VERIFY_TOKEN: {'set' if verify else 'missing'}",
        f"META_APP_SECRET: {'set' if secret else 'missing'}",
        f"WHATSAPP_DISPLAY_NUMBER: {display or '(not set — wa.me link needs this)'}",
    ]
    if token and phone_id:
        lines.append("Ready to send via Cloud API (use /stats for DB counts).")
    else:
        lines.append("Cannot send until token + phone number ID are set on Render.")
    return "\n".join(lines)
