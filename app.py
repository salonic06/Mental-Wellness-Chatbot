import json
import logging
import os
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from api_routes import router as api_router
from bot_router import process_message
from database import init_db
from interactive_maps import resolve_inbound_text
from checkin_nudge_scheduler import start_daily_nudge_scheduler
from meditation_scheduler import on_meditation_user_message
from whatsapp_cloud import WhatsAppCloudAPI, extract_inbound_message, verify_meta_signature
from whatsapp_health import probe_whatsapp_token

_BASE_DIR = Path(__file__).resolve().parent
_ENV_PATH = _BASE_DIR / ".env"
load_dotenv(_ENV_PATH, override=True)

logger = logging.getLogger("mental_wellness_bot")
logging.basicConfig(level=logging.INFO)

_FALLBACK_REPLY = (
    "I'm here — something went wrong on my side. "
    "Try again in a moment, or type /help."
)


def _run_db_backup() -> None:
    script = _BASE_DIR / "scripts" / "backup_db.py"
    try:
        subprocess.run([sys.executable, str(script)], check=False, timeout=120)
    except Exception as exc:
        logger.warning("DB backup failed: %s", exc)


def _backup_scheduler_loop() -> None:
    _run_db_backup()
    while True:
        time.sleep(24 * 3600)
        _run_db_backup()


def _start_backup_scheduler() -> None:
    if os.environ.get("ENABLE_SCHEDULED_BACKUP", "").lower() not in ("1", "true", "yes"):
        return
    threading.Thread(target=_backup_scheduler_loop, daemon=True).start()
    logger.info("Scheduled DB backup enabled (on startup + every 24h)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized at %s", os.environ.get("DATABASE_PATH", "wellness.db"))
    _start_backup_scheduler()
    start_daily_nudge_scheduler()
    wa = probe_whatsapp_token()
    if wa.get("configured") and not wa.get("ok"):
        logger.error(
            "WhatsApp token probe failed (%s) — messages will not send until "
            "WHATSAPP_ACCESS_TOKEN is renewed. See docs/LONG_LIVED_TOKEN.md",
            wa.get("detail"),
        )
    yield


app = FastAPI(title="Mental Wellness Chatbot (WhatsApp Cloud API)", lifespan=lifespan)
app.include_router(api_router)


def _required_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_wa_id(wa_id: str) -> str:
    return "".join(ch for ch in wa_id if ch.isdigit())


async def _process_inbound_and_reply(sender: str, raw: str) -> None:
    """Process message and send reply — runs after webhook acks Meta."""
    try:
        access_token = _required_env("WHATSAPP_ACCESS_TOKEN")
        phone_number_id = _required_env("WHATSAPP_PHONE_NUMBER_ID")
        api = WhatsAppCloudAPI(access_token=access_token, phone_number_id=phone_number_id)

        reply = process_message(sender, raw)
        await api.send_reply(to=sender, reply=reply)
        await on_meditation_user_message(sender, resolve_inbound_text(raw).strip().lower())
    except Exception as exc:
        logger.exception("Inbound processing failed (sender_hash=%s): %s", hash(sender), exc)
        try:
            access_token = (os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
            phone_id = (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
            if access_token and phone_id:
                api = WhatsAppCloudAPI(access_token=access_token, phone_number_id=phone_id)
                await api.send_text(to=sender, text=_FALLBACK_REPLY)
        except Exception:
            logger.exception("Fallback send also failed (sender_hash=%s)", hash(sender))


@app.get("/webhook")
async def webhook_verify(request: Request):
    """
    Meta webhook verification.
    Meta sends: hub.mode, hub.verify_token, hub.challenge
    """
    qp = request.query_params
    mode = qp.get("hub.mode") or qp.get("hub_mode")
    token = qp.get("hub.verify_token") or qp.get("hub_verify_token")
    challenge = qp.get("hub.challenge") or qp.get("hub_challenge")

    verify_token = os.environ.get("META_VERIFY_TOKEN", "")
    if mode == "subscribe" and token and verify_token and token == verify_token:
        return PlainTextResponse(challenge or "", status_code=200)

    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
):
    load_dotenv(_ENV_PATH, override=True)
    raw_body = await request.body()

    app_secret = (os.environ.get("META_APP_SECRET") or "").strip()
    if app_secret:
        if not verify_meta_signature(app_secret=app_secret, raw_body=raw_body, x_hub_signature_256=x_hub_signature_256):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload: Dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    inbound = extract_inbound_message(payload)
    if not inbound or not inbound.get("from"):
        return {"status": "ignored"}

    sender = _normalize_wa_id(inbound["from"])
    raw = (inbound.get("text") or "").strip()
    logger.info(
        "Inbound queued (sender_hash=%s, interactive=%s)",
        hash(sender),
        inbound.get("interactive", "no"),
    )

    # Ack Meta immediately; process + send in background (LLM + cold start safe).
    background_tasks.add_task(_process_inbound_and_reply, sender, raw)
    return {"status": "ok"}


@app.get("/health")
async def health():
    from llm_client import status as llm_status

    wa = probe_whatsapp_token()
    return {
        "status": "ok" if wa.get("ok", True) or not wa.get("configured") else "degraded",
        "llm": llm_status(),
        "whatsapp": wa,
    }
