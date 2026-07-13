"""WhatsApp Cloud API connectivity checks (token validity, etc.)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


def probe_whatsapp_token() -> Dict[str, Any]:
    """
    Lightweight Graph API probe. Returns a small dict safe for /health and /ping.
    Does not log secrets.
    """
    token = (os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not token or not phone_id:
        return {
            "configured": False,
            "ok": False,
            "detail": "missing_token_or_phone_id",
        }

    url = f"https://graph.facebook.com/v22.0/{phone_id}"
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    except Exception as exc:
        logger.warning("WhatsApp token probe failed: %s", exc)
        return {"configured": True, "ok": False, "detail": "network_error"}

    if resp.status_code == 200:
        return {"configured": True, "ok": True, "detail": "valid"}

    detail = "invalid_or_expired"
    if resp.status_code == 401:
        detail = "token_expired_or_invalid"
    elif resp.status_code == 403:
        detail = "token_forbidden"

    logger.error(
        "WhatsApp token probe failed status=%s (check WHATSAPP_ACCESS_TOKEN expiry)",
        resp.status_code,
    )
    return {
        "configured": True,
        "ok": False,
        "detail": detail,
        "status_code": resp.status_code,
    }
