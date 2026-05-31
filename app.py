import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from api_routes import router as api_router
from bot_router import process_message
from database import init_db
from whatsapp_cloud import WhatsAppCloudAPI, extract_inbound_text_message, verify_meta_signature

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH, override=True)

logger = logging.getLogger("mental_wellness_bot")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mental Wellness Chatbot (WhatsApp Cloud API)")
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database initialized")


def _required_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_wa_id(wa_id: str) -> str:
    return "".join(ch for ch in wa_id if ch.isdigit())


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

    inbound = extract_inbound_text_message(payload)
    if not inbound or not inbound.get("from"):
        return {"status": "ignored"}

    sender = _normalize_wa_id(inbound["from"])
    text = (inbound.get("text") or "").strip()
    logger.info("Inbound message received (sender_hash=%s)", hash(sender))

    try:
        access_token = _required_env("WHATSAPP_ACCESS_TOKEN")
        phone_number_id = _required_env("WHATSAPP_PHONE_NUMBER_ID")
        api = WhatsAppCloudAPI(access_token=access_token, phone_number_id=phone_number_id)

        reply = process_message(sender, text)
        await api.send_text(to=sender, text=reply)
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Webhook handler failed while processing message: %s", exc)
        # Always 200 so Meta stops retrying; check server logs for the real error.
        return {"status": "error", "detail": "send_failed"}


@app.get("/health")
async def health():
    return {"status": "ok"}

