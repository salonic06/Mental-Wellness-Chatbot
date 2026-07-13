"""Normalize slash commands and interactive payloads."""

from __future__ import annotations

from interactive_maps import resolve_inbound_text

COMMAND_ALIASES = {
    "/check-in": "/checkin",
    "/check_in": "/checkin",
    "/talk": "/vent",
}

DONE_TOKENS = frozenset({"/done", "done", "vent_done"})


def normalize_inbound(raw: str) -> str:
    """Resolve interactive ids and normalize command spelling."""
    text = resolve_inbound_text((raw or "").strip())
    if not text.startswith("/"):
        return text
    parts = text.split(maxsplit=1)
    cmd_raw = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if cmd_raw in COMMAND_ALIASES:
        cmd = COMMAND_ALIASES[cmd_raw]
    else:
        cmd = "/" + cmd_raw.lstrip("/").replace("-", "").replace("_", "")
    return f"{cmd} {args}".strip()


def is_done_signal(raw: str, stripped: str) -> bool:
    key = (raw or "").strip().lower()
    return stripped.lower() in DONE_TOKENS or key in DONE_TOKENS
