import asyncio
import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from bot_reply import BotReply, Button

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

    async def _post_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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

    async def send_text(self, *, to: str, text: str, preview_url: bool = False) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }
        return await self._post_message(payload)

    async def send_reply_buttons(
        self,
        *,
        to: str,
        body: str,
        buttons: List[Button],
    ) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": btn_id, "title": title[:20]},
                        }
                        for btn_id, title in buttons[:3]
                    ]
                },
            },
        }
        return await self._post_message(payload)

    async def send_list(
        self,
        *,
        to: str,
        body: str,
        button_label: str,
        sections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body[:1024]},
                "action": {
                    "button": button_label[:20],
                    "sections": sections,
                },
            },
        }
        return await self._post_message(payload)

    async def send_reply(self, *, to: str, reply: BotReply) -> None:
        """Send text and optional interactive UI (buttons or list, not both)."""
        if reply.has_interactive:
            if reply.buttons:
                await self.send_reply_buttons(to=to, body=reply.text, buttons=reply.buttons)
                return
            if reply.list_sections:
                await self.send_list(
                    to=to,
                    body=reply.text,
                    button_label=reply.list_button_label,
                    sections=reply.list_sections,
                )
                return
        await self.send_text(to=to, text=reply.text)


def verify_meta_signature(
    *,
    app_secret: str,
    raw_body: bytes,
    x_hub_signature_256: Optional[str],
) -> bool:
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


def extract_inbound_message(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    First inbound user message: text or interactive (button/list reply).
    Returns {"from", "text", "message_id"?} where text is body or interactive id.
    """
    try:
        entries = payload.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = change.get("value") or {}
                messages = value.get("messages") or []
                for msg in messages:
                    wa_from = msg.get("from", "")
                    message_id = msg.get("id") or ""
                    msg_type = msg.get("type")
                    if msg_type == "text" and "text" in msg:
                        return {
                            "from": wa_from,
                            "text": msg["text"].get("body", ""),
                            "message_id": message_id,
                        }
                    if msg_type == "interactive":
                        inter = msg.get("interactive") or {}
                        if inter.get("type") == "button_reply":
                            br = inter.get("button_reply") or {}
                            return {
                                "from": wa_from,
                                "text": br.get("id", ""),
                                "interactive": "button",
                                "message_id": message_id,
                            }
                        if inter.get("type") == "list_reply":
                            lr = inter.get("list_reply") or {}
                            return {
                                "from": wa_from,
                                "text": lr.get("id", ""),
                                "interactive": "list",
                                "message_id": message_id,
                            }
    except Exception:
        logger.exception("Failed to parse inbound WhatsApp payload")
        return None
    return None


# Backward-compatible alias
def extract_inbound_text_message(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    return extract_inbound_message(payload)
