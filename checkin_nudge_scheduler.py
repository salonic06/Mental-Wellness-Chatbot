"""
Optional daily WhatsApp reminder to run /checkin.

Users opt in with /remind on. Scheduler runs in a background thread when
ENABLE_DAILY_CHECKIN_NUDGES=true on an always-on host (e.g. Render).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx

from db_paths import connect

logger = logging.getLogger(__name__)

NUDGE_MESSAGE = (
    "Good morning from your Wellness Buddy.\n\n"
    "How are you today? Reply /checkin for a quick guided check-in, "
    "or /mood 7 with a short note."
)


def nudges_enabled() -> bool:
    return os.environ.get("ENABLE_DAILY_CHECKIN_NUDGES", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _timezone() -> ZoneInfo:
    name = (os.environ.get("TIMEZONE") or "UTC").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _nudge_hour() -> int:
    try:
        hour = int(os.environ.get("DAILY_NUDGE_HOUR", "9"))
        return max(0, min(23, hour))
    except ValueError:
        return 9


def _nudge_window_minutes() -> int:
    """How many minutes after the hour start we may send (default 9:00–9:29)."""
    try:
        return max(5, min(59, int(os.environ.get("DAILY_NUDGE_WINDOW_MINUTES", "30"))))
    except ValueError:
        return 30


def should_send_nudge_now(now: datetime) -> bool:
    """Send only in the configured morning window, not all day after that hour."""
    if now.hour != _nudge_hour():
        return False
    return now.minute < _nudge_window_minutes()


def set_daily_reminder(user_phone: str, enabled: bool) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO daily_reminders (user_phone, enabled, last_sent_date)
               VALUES (?, ?, NULL)
               ON CONFLICT(user_phone) DO UPDATE SET enabled = excluded.enabled""",
            (user_phone, 1 if enabled else 0),
        )
        conn.commit()
    finally:
        conn.close()


def get_reminder_status(user_phone: str) -> dict:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT enabled, last_sent_date FROM daily_reminders WHERE user_phone = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return {"enabled": False, "last_sent_date": None}
    return {"enabled": bool(row[0]), "last_sent_date": row[1]}


def _users_due_today(local_today: str) -> List[str]:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            """SELECT user_phone FROM daily_reminders
               WHERE enabled = 1
                 AND (last_sent_date IS NULL OR last_sent_date != ?)""",
            (local_today,),
        )
        return [row[0] for row in c.fetchall()]
    finally:
        conn.close()


def _mark_sent(user_phone: str, local_today: str) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            """UPDATE daily_reminders SET last_sent_date = ? WHERE user_phone = ?""",
            (local_today, user_phone),
        )
        conn.commit()
    finally:
        conn.close()


def send_text_sync(to: str, text: str) -> bool:
    token = (os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not token or not phone_id:
        logger.warning("Daily nudge skipped: missing WhatsApp env")
        return False

    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": "".join(ch for ch in to if ch.isdigit()),
        "type": "text",
        "text": {"body": text},
    }
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.is_error:
            logger.error("Daily nudge send failed: %s %s", resp.status_code, resp.text)
            return False
        return True
    except Exception:
        logger.exception("Daily nudge send error (user_hash=%s)", hash(to))
        return False


def run_daily_nudge_tick() -> int:
    """Send reminders to eligible users; return count sent."""
    tz = _timezone()
    now = datetime.now(tz)
    if not should_send_nudge_now(now):
        return 0

    local_today = now.date().isoformat()
    sent = 0
    for phone in _users_due_today(local_today):
        if send_text_sync(phone, NUDGE_MESSAGE):
            _mark_sent(phone, local_today)
            sent += 1
            logger.info("Daily check-in nudge sent (user_hash=%s)", hash(phone))
    return sent


def _scheduler_loop() -> None:
    interval = max(300, int(os.environ.get("DAILY_NUDGE_POLL_SECONDS", "900")))
    while True:
        try:
            if nudges_enabled():
                count = run_daily_nudge_tick()
                if count:
                    logger.info("Daily nudge tick: sent %s message(s)", count)
        except Exception:
            logger.exception("Daily nudge scheduler tick failed")
        time.sleep(interval)


def start_daily_nudge_scheduler() -> None:
    if not nudges_enabled():
        return
    threading.Thread(target=_scheduler_loop, daemon=True, name="daily-checkin-nudges").start()
    logger.info(
        "Daily check-in nudges enabled (%s:00–%s:%02d %s, poll=%ss)",
        _nudge_hour(),
        _nudge_hour(),
        _nudge_window_minutes() - 1,
        _timezone(),
        os.environ.get("DAILY_NUDGE_POLL_SECONDS", "900"),
    )
