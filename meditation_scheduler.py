"""
Timed WhatsApp nudges during an active meditation session.

Runs asyncio tasks on the FastAPI process (Render stays awake while serving).
Cancelled when the user ends, pauses, skips ahead, or leaves meditation.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Optional

from db_paths import connect
from state_store import get_user_state
from wellness_bot_class import WellnessBot
from whatsapp_cloud import WhatsAppCloudAPI

logger = logging.getLogger(__name__)

_tasks: Dict[str, asyncio.Task] = {}


def nudges_enabled() -> bool:
    return os.environ.get("ENABLE_MEDITATION_NUDGES", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _make_api() -> WhatsAppCloudAPI:
    return WhatsAppCloudAPI(
        access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
    )


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


async def cancel_meditation_nudges(user_phone: str) -> None:
    task = _tasks.pop(user_phone, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def schedule_meditation_nudges(user_phone: str) -> None:
    """After **ready**, push remaining script parts on interval gaps from meditations.json."""
    if not nudges_enabled():
        return

    await cancel_meditation_nudges(user_phone)

    if not _still_meditating(user_phone):
        return

    conn = connect()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT meditation_type FROM active_meditations WHERE user_phone = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()

    if not row:
        return

    meditation_type = row[0]
    bot = WellnessBot()
    meditation = bot.meditations.get(meditation_type)
    if not meditation:
        return

    keys = bot._meditation_script_keys(meditation)
    script = meditation.get("script", {})
    intervals = meditation.get("intervals") or [int(k) for k in keys]
    if len(keys) < 2:
        return

    async def _runner() -> None:
        try:
            for idx in range(2, len(keys)):
                gap_min = intervals[idx] - intervals[idx - 1]
                wait_sec = max(60, int(gap_min * 60))
                await asyncio.sleep(wait_sec)

                if not _still_meditating(user_phone):
                    return

                body = script.get(keys[idx], "").strip()
                if not body:
                    continue

                part_num = idx + 1
                text = (
                    f"Meditation — part {part_num}/{len(keys)}\n\n"
                    f"{body}\n\n"
                    "Type **next** or **end** anytime."
                )
                api = _make_api()
                await api.send_text(to=user_phone, text=text)
                logger.info(
                    "Meditation nudge sent (user_hash=%s, part=%s)",
                    hash(user_phone),
                    part_num,
                )

            if _still_meditating(user_phone):
                api = _make_api()
                await api.send_text(
                    to=user_phone,
                    text=(
                        "That was the last guided part.\n"
                        "Type **end** when you're done, or /mood to log how you feel."
                    ),
                )
        except asyncio.CancelledError:
            logger.debug("Meditation nudge task cancelled (user_hash=%s)", hash(user_phone))
        except Exception:
            logger.exception("Meditation nudge task failed (user_hash=%s)", hash(user_phone))

    _tasks[user_phone] = asyncio.create_task(_runner())
    logger.info("Meditation nudges scheduled (user_hash=%s)", hash(user_phone))


async def on_meditation_user_message(user_phone: str, resolved_text: str) -> None:
    """Call from webhook after each inbound message during meditation flows."""
    if not nudges_enabled():
        return

    text = (resolved_text or "").strip().lower()

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
