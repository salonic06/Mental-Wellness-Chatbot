"""Chat session mood outcomes — optional pre/post 1–10 for impact metrics."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from db_paths import connect, storage_kind
from db_sql import execute, is_db_error

logger = logging.getLogger(__name__)

SKIP_TOKENS = frozenset({"skip", "s", "-", "no", "pass"})


def parse_mood_reply(text: str) -> tuple[Optional[int], bool]:
    """
    Returns (intensity, is_skip).
    intensity is 1–10 or None if skip/invalid.
    is_skip True means user explicitly skipped.
    """
    raw = (text or "").strip().lower()
    if raw in SKIP_TOKENS:
        return None, True
    try:
        # Allow "7" or "7/10"
        token = raw.split("/")[0].split()[0]
        value = int(token)
    except (ValueError, IndexError):
        return None, False
    if 1 <= value <= 10:
        return value, False
    return None, False


def open_chat_outcome(user_phone: str, source: str = "chat") -> Optional[int]:
    """Create an open session row; return id or None on failure."""
    try:
        conn = connect()
        c = conn.cursor()
        now = datetime.now()
        if storage_kind() == "postgres":
            execute(
                c,
                """INSERT INTO chat_session_outcomes
                   (user_phone, opened_at, source)
                   VALUES (?, ?, ?)
                   RETURNING id""",
                (user_phone, now, source),
            )
            row = c.fetchone()
            conn.commit()
            conn.close()
            return int(row[0]) if row else None
        execute(
            c,
            """INSERT INTO chat_session_outcomes
               (user_phone, opened_at, source)
               VALUES (?, ?, ?)""",
            (user_phone, now, source),
        )
        outcome_id = c.lastrowid
        conn.commit()
        conn.close()
        return int(outcome_id) if outcome_id else None
    except Exception as e:
        if is_db_error(e):
            logger.error("open_chat_outcome failed: %s", e)
            return None
        raise


def set_pre_mood(outcome_id: int, intensity: Optional[int], skipped: bool = False) -> None:
    try:
        conn = connect()
        c = conn.cursor()
        execute(
            c,
            """UPDATE chat_session_outcomes
               SET pre_intensity = ?, skipped_pre = ?
               WHERE id = ?""",
            (intensity, 1 if skipped else 0, outcome_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        if is_db_error(e):
            logger.error("set_pre_mood failed: %s", e)
            return
        raise


def close_chat_outcome(
    outcome_id: int,
    *,
    post_intensity: Optional[int] = None,
    skipped_post: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Close session with optional post mood. Computes mood_delta when both scores exist.
    Returns summary dict for the reply, or None.
    """
    try:
        conn = connect()
        c = conn.cursor()
        execute(
            c,
            "SELECT pre_intensity FROM chat_session_outcomes WHERE id = ?",
            (outcome_id,),
        )
        row = c.fetchone()
        pre = row[0] if row else None
        delta = None
        if pre is not None and post_intensity is not None:
            delta = int(post_intensity) - int(pre)
        execute(
            c,
            """UPDATE chat_session_outcomes
               SET post_intensity = ?,
                   skipped_post = ?,
                   mood_delta = ?,
                   closed_at = ?
               WHERE id = ?""",
            (
                post_intensity,
                1 if skipped_post else 0,
                delta,
                datetime.now(),
                outcome_id,
            ),
        )
        conn.commit()
        conn.close()
        return {
            "pre_intensity": pre,
            "post_intensity": post_intensity,
            "mood_delta": delta,
        }
    except Exception as e:
        if is_db_error(e):
            logger.error("close_chat_outcome failed: %s", e)
            return None
        raise


def abandon_chat_outcome(outcome_id: Optional[int]) -> None:
    """Mark open session closed without post mood (cancel / abandon)."""
    if not outcome_id:
        return
    close_chat_outcome(outcome_id, post_intensity=None, skipped_post=True)
