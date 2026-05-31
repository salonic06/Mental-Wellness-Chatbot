"""Outbound message shape (plain text and/or WhatsApp interactive UI)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# (button_id, title) — WhatsApp allows max 3 reply buttons; title max ~20 chars
Button = Tuple[str, str]


@dataclass
class BotReply:
    text: str
    buttons: Optional[List[Button]] = None
    list_body: Optional[str] = None
    list_button_label: str = "Choose"
    list_sections: Optional[List[Dict[str, Any]]] = None

    @property
    def has_interactive(self) -> bool:
        return bool(self.buttons or self.list_sections)
