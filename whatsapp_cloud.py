import asyncio
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class WhatsAppCloudAPI:
    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        graph_api_version: str = "v22.0",
    ) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.graph_api_version = graph_api_version

    @property
    def _messages_url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_api_version}/{self.phone_number_id}/messages"

    async def send_text(self, *, to: str, text: str, preview_url: bool = False) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }

        headers = {"Authorization": f"Bearer {self.access_token}"}
        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(self._messages_url, json=payload, headers=headers)
                if resp.is_error:
                    logger.error(
                        "WhatsApp send failed status=%s body=%s",
                        resp.status_code,
                        resp.text,
                    )
                    resp.raise_for_status()
                return resp.json()
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
                last_error = exc
                logger.warning("WhatsApp send attempt %s failed: %s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise last_error  # type: ignore[misc]


def verify_meta_signature(
    *,
    app_secret: str,
    raw_body: bytes,
    x_hub_signature_256: Optional[str],
) -> bool:
    """
    Meta Webhooks signature verification.
    Header format: 'sha256=<hex_digest>'
    """
    if not app_secret:
        return False
    if not x_hub_signature_256:
        return False
    if not x_hub_signature_256.startswith("sha256="):
        return False

    their = x_hub_signature_256.removeprefix("sha256=")
    mac = hmac.new(app_secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    ours = mac.hexdigest()
    return hmac.compare_digest(ours, their)


def extract_inbound_text_message(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extracts the first inbound text message.\n
    Returns {\"from\": \"<wa_id>\", \"text\": \"...\"} or None.\n
    Note: Cloud API payloads can include multiple entries/changes/messages; we keep it simple for the scaffold.
    """
    try:
        entries = payload.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = (change.get("value") or {})
                messages = value.get("messages") or []
                for msg in messages:
                    if msg.get("type") == "text" and "text" in msg:
                        return {"from": msg.get("from", ""), "text": msg["text"].get("body", "")}
    except Exception:
        return None
    return None

