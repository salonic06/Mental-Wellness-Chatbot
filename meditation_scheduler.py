"""
Timed WhatsApp nudges during an active meditation session.

After **ready**, part 1 is shown immediately (script key at intervals[1]).
Later parts fire at (intervals[idx] - intervals[1]) minutes from that moment.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from db_paths import connect
from state_store import get_user_state
from wellness_bot_class import WellnessBot
from whatsapp_cloud import WhatsAppCloudAPI

logger = logging.getLogger(__name__)

_tasks: Dict[str, asyncio.Task] = {}

_PASSED_LINE = re.compile(r"\n?\[?\d+\s*minutes?\s*passed\]?", re.IGNORECASE)


def nudges_enabled() -> bool:
    return os.environ.get("ENABLE_MEDITATION_NUDGES", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def clean_script_body(body: str) -> str:
    return _PASSED_LINE.sub("", body).strip()


def _make_api() -> WhatsAppCloudAPI:
    return WhatsAppCloudAPI(
        access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
    )


def _parse_start_time(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _still_meditating(user_phone: str) -> bool:
    if get_user_state(user_phone)["state"] != "meditating":
        return False
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM active_meditations WHERE user_phone = ? AND paused = 0",
            (user_phone,),
        )
        return c.fetchone() is not None
    finally:
        conn.close()


def _load_session(user_phone: str) -> Optional[Tuple[str, Optional[datetime], int]]:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            """SELECT meditation_type, start_time, step_index
               FROM active_meditations WHERE user_phone = ?""",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return row[0], _parse_start_time(row[1]), int(row[2] or 0)


def _set_step_index(user_phone: str, step_index: int) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE active_meditations SET step_index = ? WHERE user_phone = ?",
            (step_index, user_phone),
        )
        conn.commit()
    finally:
        conn.close()


def _minutes_after_ready(intervals: list, idx: int) -> float:
    """Minutes from **ready** until script part idx (idx >= 2)."""
    if idx < 2 or idx >= len(intervals):
        return 0.0
    anchor = intervals[1]
    return float(intervals[idx] - anchor)


def _minutes_between_parts(intervals: list, from_idx: int, to_idx: int) -> float:
    """Minutes between script indices (e.g. after pause, wait this long for the next part)."""
    if to_idx <= from_idx or from_idx < 0 or to_idx >= len(intervals):
        return 0.0
    return float(intervals[to_idx] - intervals[from_idx])


async def cancel_meditation_nudges(user_phone: str) -> None:
    task = _tasks.pop(user_phone, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _send_part(user_phone: str, *, part_num: int, total: int, body: str) -> None:
    text = (
        f"Meditation — part {part_num}/{total}\n\n"
        f"{body}\n\n"
        "Type **next** or **end** anytime."
    )
    await _make_api().send_text(to=user_phone, text=text)


async def schedule_meditation_nudges(user_phone: str, *, from_resume: bool = False) -> None:
    if not nudges_enabled():
        return

    await cancel_meditation_nudges(user_phone)

    if not _still_meditating(user_phone):
        return

    session = _load_session(user_phone)
    if not session:
        logger.warning("No meditation session to schedule (user_hash=%s)", hash(user_phone))
        return

    meditation_type, start_time, step_index = session
    if not start_time:
        logger.warning("No start_time for nudges (user_hash=%s)", hash(user_phone))
        return

    bot = WellnessBot()
    meditation = bot.meditations.get(meditation_type)
    if not meditation:
        return

    keys = bot._meditation_script_keys(meditation)
    script = meditation.get("script", {})
    intervals = meditation.get("intervals") or [int(k) for k in keys]
    duration_min = int(meditation.get("duration", intervals[-1] if intervals else 3))

    if len(keys) < 3:
        return

    async def _runner() -> None:
        try:
            prev_idx = step_index
            for idx in range(2, len(keys)):
                if idx <= step_index:
                    continue

                if from_resume:
                    # Do not catch up overdue absolute targets — pace from resume.
                    wait_sec = _minutes_between_parts(intervals, prev_idx, idx) * 60
                else:
                    wait_min = _minutes_after_ready(intervals, idx)
                    target_at = start_time + timedelta(minutes=wait_min)
                    wait_sec = (target_at - datetime.now()).total_seconds()

                if wait_sec > 0:
                    await asyncio.sleep(wait_sec)

                if not _still_meditating(user_phone):
                    return

                body = clean_script_body(script.get(keys[idx], ""))
                if not body:
                    continue

                await _send_part(
                    user_phone,
                    part_num=idx + 1,
                    total=len(keys),
                    body=body,
                )
                _set_step_index(user_phone, idx)
                prev_idx = idx
                logger.info(
                    "Meditation nudge sent (user_hash=%s, part=%s, resume=%s)",
                    hash(user_phone),
                    idx + 1,
                    from_resume,
                )

            if _still_meditating(user_phone):
                last_body = clean_script_body(script.get(keys[-1], ""))
                if "complete" not in last_body.lower():
                    await _make_api().send_text(
                        to=user_phone,
                        text=(
                            f"~{duration_min}-minute session complete.\n"
                            "Type **end** when you're done, or /mood to log how you feel."
                        ),
                    )
        except asyncio.CancelledError:
            logger.debug("Meditation nudge cancelled (user_hash=%s)", hash(user_phone))
        except Exception:
            logger.exception("Meditation nudge failed (user_hash=%s)", hash(user_phone))

    _tasks[user_phone] = asyncio.create_task(_runner())
    logger.info(
        "Meditation nudges scheduled (user_hash=%s, resume=%s, start=%s)",
        hash(user_phone),
        from_resume,
        start_time.isoformat(),
    )


async def on_meditation_user_message(user_phone: str, resolved_text: str) -> None:
    if not nudges_enabled():
        return

    text = (resolved_text or "").strip().lower()

    if text == "resume":
        await schedule_meditation_nudges(user_phone, from_resume=True)
        return

    if text in (
        "end",
        "pause",
        "next",
        "cancel",
        "cmd_cancel",
        "/cancel",
        "/done",
        "done",
    ) or text.startswith("med_"):
        await cancel_meditation_nudges(user_phone)
        return

    if text == "ready":
        await schedule_meditation_nudges(user_phone)
