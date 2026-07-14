"""Admin-only stats from SQLite or Postgres (Cloud API mode — no Twilio)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict

import db_paths
from db_sql import execute, is_db_error


def fetch_bot_stats() -> Dict[str, Any]:
    if not db_paths.db_available():
        return {"error": "database_missing", "path": db_paths.backend_label()}

    conn = db_paths.connect()
    try:
        c = conn.cursor()

        def scalar(sql_str: str, params: tuple = ()) -> int:
            execute(c, sql_str, params)
            row = c.fetchone()
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
            "care_enabled": scalar(
                "SELECT COUNT(*) FROM daily_reminders WHERE care_enabled = 1"
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
            "database_path": db_paths.backend_label(),
            "storage": db_paths.storage_kind(),
            "meditation_nudges": os.environ.get("ENABLE_MEDITATION_NUDGES", "true"),
            "daily_checkin_nudges": os.environ.get("ENABLE_DAILY_CHECKIN_NUDGES", "false"),
        }
        return stats
    except Exception as exc:
        if is_db_error(exc):
            return {"error": "query_failed", "detail": str(exc)}
        raise
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
        f"Care pings on: {stats.get('care_enabled', 0)}\n"
        f"Activity (7d, approx): {stats['messages_last_7d']} logged events\n"
        f"DB: {stats['database_path']} ({stats.get('storage', 'sqlite')})\n"
        f"Meditation nudges: {stats['meditation_nudges']}\n"
        f"Daily check-in nudges: {stats['daily_checkin_nudges']}"
    )


def format_ping_message() -> str:
    token = bool((os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip())
    phone_id = bool((os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip())
    verify = bool((os.environ.get("META_VERIFY_TOKEN") or "").strip())
    secret = bool((os.environ.get("META_APP_SECRET") or "").strip())
    display = (os.environ.get("WHATSAPP_DISPLAY_NUMBER") or "").strip()

    from whatsapp_health import probe_whatsapp_token

    wa = probe_whatsapp_token()

    lines = [
        "*Config check*",
        f"WHATSAPP_ACCESS_TOKEN: {'set' if token else 'MISSING'}",
        f"WHATSAPP_PHONE_NUMBER_ID: {'set' if phone_id else 'MISSING'}",
        f"META_VERIFY_TOKEN: {'set' if verify else 'missing'}",
        f"META_APP_SECRET: {'set' if secret else 'missing'}",
        f"WHATSAPP_DISPLAY_NUMBER: {display or '(not set — wa.me link needs this)'}",
    ]
    if wa.get("configured"):
        if wa.get("ok"):
            lines.append("WhatsApp token: valid")
        else:
            lines.append(
                f"WhatsApp token: **{wa.get('detail', 'invalid')}** — renew token on Render"
            )
    if token and phone_id and wa.get("ok"):
        lines.append("Ready to send via Cloud API (use /stats for DB counts).")
    elif token and phone_id:
        lines.append("Token set but probe failed — messages may stop after a few hours.")
    else:
        lines.append("Cannot send until token + phone number ID are set on Render.")
    return "\n".join(lines)
