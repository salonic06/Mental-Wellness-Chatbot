"""Ping /health to keep Render free-tier web services warm (optional cron target)."""

from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    url = (os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    if not url:
        print("Set KEEPALIVE_URL to https://your-service.onrender.com/health", file=sys.stderr)
        return 1
    if not url.startswith("http"):
        url = f"https://{url.rstrip('/')}/health"
    elif not url.endswith("/health"):
        url = url.rstrip("/") + "/health"

    try:
        resp = httpx.get(url, timeout=30)
        print(resp.status_code, resp.text[:200])
        return 0 if resp.is_success else 1
    except Exception as exc:
        print(f"keepalive failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
