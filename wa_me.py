"""Build WhatsApp click-to-chat (wa.me) links."""

from __future__ import annotations

from urllib.parse import quote


def normalize_wa_display_number(raw: str) -> str:
    """Digits only, no + or spaces — required for wa.me URLs."""
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def build_wa_me_link(display_number: str, prefill: str = "Hi") -> str:
    """
    Example: build_wa_me_link("15551234567", "Hi") → https://wa.me/15551234567?text=Hi
    """
    digits = normalize_wa_display_number(display_number)
    if not digits:
        raise ValueError("display_number must contain digits")
    text = quote(prefill or "Hi", safe="")
    return f"https://wa.me/{digits}?text={text}"
