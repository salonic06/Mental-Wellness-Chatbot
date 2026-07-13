"""Optional API key auth for dashboard / analytics routes."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException


def require_dashboard_key(
    x_dashboard_key: Optional[str] = Header(default=None, alias="X-Dashboard-Key"),
) -> None:
    """
    When DASHBOARD_API_KEY is set on the bot server, /api/* requires the same
    value in X-Dashboard-Key. When unset, routes stay open (local dev only).
    """
    expected = (os.environ.get("DASHBOARD_API_KEY") or "").strip()
    if not expected:
        return
    if (x_dashboard_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing dashboard API key")
