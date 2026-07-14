"""
Opt-in proactive WhatsApp companion nudges.

Morning ritual (/remind on): affirmation, check-in invite, or both — soft-random
minute within the configured window.

Care pings (/care on): pattern-gated afternoon "how are you holding up?" when
mood trends look rough — still opt-in, capped, never crisis replay.

Requires an awake host (Render free sleeps ~15 min idle → use UptimeRobot on
/health). WhatsApp free-form sends only work within ~24h of the user's last
message; outside that, Meta rejects the send (templates would be needed later).
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from db_paths import connect
from db_sql import execute

logger = logging.getLogger(__name__)

VALID_MODES = frozenset({"checkin", "affirmation", "both"})

NUDGE_MESSAGE = (
    "Good morning — how are you starting the day?\n\n"
    "Reply /checkin for a quick guided check-in, or just tell me how you feel."
)

AFFIRMATION_FALLBACK = (
    "Good morning. You don't have to have it all figured out today — "
    "showing up for yourself, even quietly, already counts."
)

CARE_FALLBACK = (
    "Hey — just checking in. No pressure to do anything fancy. "
    "How are you holding up?"
)


def nudges_enabled() -> bool:
    return os.environ.get("ENABLE_DAILY_CHECKIN_NUDGES", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def care_pings_enabled() -> bool:
    raw = os.environ.get("ENABLE_CARE_PINGS")
    if raw is None or raw.strip() == "":
        return nudges_enabled()
    return raw.lower() in ("1", "true", "yes")


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
    """Window length from DAILY_NUDGE_HOUR:00 (supports multi-hour soft-random)."""
    try:
        return max(5, min(360, int(os.environ.get("DAILY_NUDGE_WINDOW_MINUTES", "30"))))
    except ValueError:
        return 30


def _care_hour() -> int:
    try:
        return max(0, min(23, int(os.environ.get("CARE_PING_HOUR", "15"))))
    except ValueError:
        return 15


def _care_window_minutes() -> int:
    try:
        return max(15, min(360, int(os.environ.get("CARE_PING_WINDOW_MINUTES", "120"))))
    except ValueError:
        return 120


def _care_min_days_between() -> int:
    try:
        return max(1, min(14, int(os.environ.get("CARE_PING_MIN_DAYS", "2"))))
    except ValueError:
        return 2


def _session_hours() -> int:
    """WhatsApp free-form messaging window (stay under Meta's 24h)."""
    try:
        return max(1, min(23, int(os.environ.get("WHATSAPP_SESSION_HOURS", "23"))))
    except ValueError:
        return 23


def _minutes_since_window_start(now: datetime, hour: int) -> Optional[float]:
    start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now < start:
        return None
    return (now - start).total_seconds() / 60.0


def should_send_nudge_now(now: datetime) -> bool:
    """True if *now* is inside the morning send window (any user might be due)."""
    elapsed = _minutes_since_window_start(now, _nudge_hour())
    if elapsed is None:
        return False
    return elapsed < _nudge_window_minutes()


def should_send_care_now(now: datetime) -> bool:
    elapsed = _minutes_since_window_start(now, _care_hour())
    if elapsed is None:
        return False
    return elapsed < _care_window_minutes()


def _user_due_at_offset(now: datetime, hour: int, window: int, preferred_minute: int) -> bool:
    elapsed = _minutes_since_window_start(now, hour)
    if elapsed is None or elapsed >= window:
        return False
    offset = max(0, min(window - 1, preferred_minute))
    return elapsed >= offset


def _pick_preferred_minute() -> int:
    window = _nudge_window_minutes()
    return random.randint(0, max(0, window - 1))


def set_daily_reminder(
    user_phone: str,
    enabled: bool,
    mode: Optional[str] = None,
) -> None:
    mode_norm = (mode or "both").strip().lower()
    if mode_norm not in VALID_MODES:
        mode_norm = "both"
    preferred = _pick_preferred_minute() if enabled else None
    conn = connect()
    try:
        c = conn.cursor()
        if enabled:
            execute(
                c,
                """INSERT INTO daily_reminders
                   (user_phone, enabled, last_sent_date, mode, care_enabled,
                    last_care_sent_date, preferred_minute)
                   VALUES (?, 1, NULL, ?, 0, NULL, ?)
                   ON CONFLICT(user_phone) DO UPDATE SET
                     enabled = 1,
                     mode = excluded.mode,
                     preferred_minute = COALESCE(
                       daily_reminders.preferred_minute, excluded.preferred_minute
                     )""",
                (user_phone, mode_norm, preferred),
            )
        else:
            execute(
                c,
                """INSERT INTO daily_reminders (user_phone, enabled, last_sent_date)
                   VALUES (?, 0, NULL)
                   ON CONFLICT(user_phone) DO UPDATE SET enabled = 0""",
                (user_phone,),
            )
        conn.commit()
    finally:
        conn.close()


def set_reminder_mode(user_phone: str, mode: str) -> bool:
    mode_norm = mode.strip().lower()
    if mode_norm not in VALID_MODES:
        return False
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """INSERT INTO daily_reminders (user_phone, enabled, mode, preferred_minute)
               VALUES (?, 0, ?, ?)
               ON CONFLICT(user_phone) DO UPDATE SET mode = excluded.mode""",
            (user_phone, mode_norm, _pick_preferred_minute()),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def set_care_enabled(user_phone: str, enabled: bool) -> None:
    preferred = _pick_preferred_minute()
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """INSERT INTO daily_reminders
               (user_phone, enabled, care_enabled, preferred_minute)
               VALUES (?, 0, ?, ?)
               ON CONFLICT(user_phone) DO UPDATE SET care_enabled = excluded.care_enabled""",
            (user_phone, 1 if enabled else 0, preferred),
        )
        conn.commit()
    finally:
        conn.close()


def get_reminder_status(user_phone: str) -> dict:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """SELECT enabled, last_sent_date, mode, care_enabled,
                      last_care_sent_date, preferred_minute
               FROM daily_reminders WHERE user_phone = ?""",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return {
            "enabled": False,
            "last_sent_date": None,
            "mode": "both",
            "care_enabled": False,
            "last_care_sent_date": None,
            "preferred_minute": None,
        }
    return {
        "enabled": bool(row[0]),
        "last_sent_date": row[1],
        "mode": (row[2] or "both"),
        "care_enabled": bool(row[3]),
        "last_care_sent_date": row[4],
        "preferred_minute": row[5],
    }


def touch_last_seen(user_phone: str, when: Optional[datetime] = None) -> None:
    """Record inbound activity for WhatsApp 24h session checks."""
    ts = (when or datetime.now()).isoformat()
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """INSERT INTO users (phone_number, last_seen_at)
               VALUES (?, ?)
               ON CONFLICT(phone_number) DO UPDATE SET last_seen_at = excluded.last_seen_at""",
            (user_phone, ts),
        )
        conn.commit()
    finally:
        conn.close()


def last_seen_at(user_phone: str) -> Optional[datetime]:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "SELECT last_seen_at FROM users WHERE phone_number = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    raw = row[0]
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def in_whatsapp_session(user_phone: str, now: Optional[datetime] = None) -> bool:
    seen = last_seen_at(user_phone)
    if not seen:
        return False
    now_naive = (now or datetime.now()).replace(tzinfo=None)
    return (now_naive - seen) <= timedelta(hours=_session_hours())


def _morning_users_due(local_today: str) -> List[Tuple[str, str, int]]:
    """Return (phone, mode, preferred_minute) for morning-eligible users."""
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """SELECT user_phone, mode, preferred_minute FROM daily_reminders
               WHERE enabled = 1
                 AND (last_sent_date IS NULL OR last_sent_date != ?)""",
            (local_today,),
        )
        rows = []
        for phone, mode, pref in c.fetchall():
            rows.append((phone, (mode or "both"), int(pref if pref is not None else 0)))
        return rows
    finally:
        conn.close()


def _care_users_due(local_today: str, min_days: int) -> List[Tuple[str, int]]:
    cutoff = (date.fromisoformat(local_today) - timedelta(days=min_days - 1)).isoformat()
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            """SELECT user_phone, preferred_minute FROM daily_reminders
               WHERE care_enabled = 1
                 AND (last_care_sent_date IS NULL OR last_care_sent_date < ?)""",
            (cutoff,),
        )
        return [(r[0], int(r[1] if r[1] is not None else 0)) for r in c.fetchall()]
    finally:
        conn.close()


def _mark_morning_sent(user_phone: str, local_today: str) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "UPDATE daily_reminders SET last_sent_date = ? WHERE user_phone = ?",
            (local_today, user_phone),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_care_sent(user_phone: str, local_today: str) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "UPDATE daily_reminders SET last_care_sent_date = ? WHERE user_phone = ?",
            (local_today, user_phone),
        )
        conn.commit()
    finally:
        conn.close()


def _static_affirmation() -> str:
    try:
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parent / "affirmations.json"
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, list) and items:
            pick = random.choice(items)
            if isinstance(pick, str) and pick.strip():
                return f"Good morning.\n\n{pick.strip()}"
            if isinstance(pick, dict):
                text = (pick.get("text") or pick.get("affirmation") or "").strip()
                if text:
                    return f"Good morning.\n\n{text}"
    except Exception:
        pass
    return AFFIRMATION_FALLBACK


def _morning_body(user_phone: str, mode: str) -> str:
    mode = (mode or "both").lower()
    affirmation = None
    checkin = None

    if mode in ("affirmation", "both"):
        try:
            from llm_wellness import personalized_affirmation

            affirmation = personalized_affirmation(user_phone)
        except Exception:
            affirmation = None
        if not affirmation:
            affirmation = _static_affirmation()
        else:
            affirmation = f"Good morning.\n\n{affirmation.strip()}"

    if mode in ("checkin", "both"):
        try:
            from llm_wellness import personalized_nudge

            checkin = personalized_nudge(user_phone)
        except Exception:
            checkin = None
        if not checkin:
            checkin = NUDGE_MESSAGE

    if mode == "affirmation":
        return affirmation or AFFIRMATION_FALLBACK
    if mode == "checkin":
        return checkin or NUDGE_MESSAGE
    # both — avoid duplicating "Good morning"
    checkin_body = (checkin or NUDGE_MESSAGE).strip()
    if checkin_body.lower().startswith("good morning"):
        # drop the greeting line(s) from check-in half
        lines = checkin_body.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0].lower().startswith("good morning"):
            lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
        checkin_body = "\n".join(lines).strip() or (
            "When you have a moment, tell me how you're starting the day — "
            "or reply /checkin for a short guided check-in."
        )
    return f"{affirmation}\n\n{checkin_body}"


def _care_body(user_phone: str, reason: str) -> str:
    try:
        from llm_wellness import personalized_care_ping

        custom = personalized_care_ping(user_phone, reason)
        if custom:
            return custom
    except Exception:
        pass
    return CARE_FALLBACK


def send_text_sync(to: str, text: str) -> bool:
    token = (os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not token or not phone_id:
        logger.warning("Proactive nudge skipped: missing WhatsApp env")
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
            logger.error("Proactive send failed: %s %s", resp.status_code, resp.text)
            return False
        return True
    except Exception:
        logger.exception("Proactive send error (user_hash=%s)", hash(to))
        return False


def run_daily_nudge_tick(now: Optional[datetime] = None) -> int:
    """Send morning reminders to eligible users; return count sent."""
    tz = _timezone()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    if not should_send_nudge_now(now):
        return 0

    local_today = now.date().isoformat()
    window = _nudge_window_minutes()
    hour = _nudge_hour()
    sent = 0
    for phone, mode, pref in _morning_users_due(local_today):
        if not _user_due_at_offset(now, hour, window, pref):
            continue
        if not in_whatsapp_session(phone, now.replace(tzinfo=None)):
            logger.info(
                "Morning nudge skipped (outside WhatsApp session, user_hash=%s)",
                hash(phone),
            )
            continue
        if send_text_sync(phone, _morning_body(phone, mode)):
            _mark_morning_sent(phone, local_today)
            sent += 1
            logger.info("Morning companion nudge sent (user_hash=%s)", hash(phone))
    return sent


def run_care_ping_tick(now: Optional[datetime] = None) -> int:
    """Send pattern-gated care pings; return count sent."""
    if not care_pings_enabled():
        return 0

    tz = _timezone()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    if not should_send_care_now(now):
        return 0

    from patterns import care_ping_reason

    local_today = now.date().isoformat()
    window = _care_window_minutes()
    hour = _care_hour()
    # Spread care sends across the afternoon window using preferred_minute scaled
    care_offset_span = min(window, _nudge_window_minutes())
    sent = 0
    for phone, pref in _care_users_due(local_today, _care_min_days_between()):
        offset = pref % max(1, care_offset_span)
        if not _user_due_at_offset(now, hour, window, offset):
            continue
        if not in_whatsapp_session(phone, now.replace(tzinfo=None)):
            logger.info(
                "Care ping skipped (outside WhatsApp session, user_hash=%s)",
                hash(phone),
            )
            continue
        reason = care_ping_reason(phone)
        if not reason:
            continue
        if send_text_sync(phone, _care_body(phone, reason)):
            _mark_care_sent(phone, local_today)
            sent += 1
            logger.info(
                "Care ping sent reason=%s (user_hash=%s)", reason, hash(phone)
            )
    return sent


def run_companion_tick(now: Optional[datetime] = None) -> dict:
    """Run morning + care ticks; return counts."""
    morning = run_daily_nudge_tick(now) if nudges_enabled() else 0
    care = run_care_ping_tick(now)
    return {"morning": morning, "care": care}


def _scheduler_loop() -> None:
    interval = max(300, int(os.environ.get("DAILY_NUDGE_POLL_SECONDS", "900")))
    while True:
        try:
            counts = run_companion_tick()
            total = counts["morning"] + counts["care"]
            if total:
                logger.info(
                    "Companion nudge tick: morning=%s care=%s",
                    counts["morning"],
                    counts["care"],
                )
        except Exception:
            logger.exception("Companion nudge scheduler tick failed")
        time.sleep(interval)


def start_daily_nudge_scheduler() -> None:
    if not nudges_enabled() and not care_pings_enabled():
        return
    threading.Thread(
        target=_scheduler_loop, daemon=True, name="companion-nudges"
    ).start()
    logger.info(
        "Companion nudges enabled (morning %s:00 +%smin %s; care %s:00 +%smin; "
        "poll=%ss). Keep host awake (UptimeRobot → /health) or sends will miss.",
        _nudge_hour(),
        _nudge_window_minutes(),
        _timezone(),
        _care_hour(),
        _care_window_minutes(),
        os.environ.get("DAILY_NUDGE_POLL_SECONDS", "900"),
    )
