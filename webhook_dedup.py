"""Deduplicate Meta WhatsApp webhook deliveries (retries cause duplicate replies)."""

from __future__ import annotations

from datetime import datetime, timedelta

import db_paths
from db_sql import execute, is_unique_violation


def init_dedup_table(conn) -> None:
    execute(
        conn.cursor(),
        """CREATE TABLE IF NOT EXISTS webhook_dedup (
               message_id TEXT PRIMARY KEY,
               created_at TEXT NOT NULL
           )""",
    )


def try_claim_message(message_id: str) -> bool:
    """
    Return True if this inbound message id is new and should be processed.
    Meta may deliver the same webhook more than once on retries.
    """
    if not message_id:
        return True

    conn = db_paths.connect()
    try:
        cur = conn.cursor()
        init_dedup_table(conn)
        execute(
            cur,
            "INSERT INTO webhook_dedup (message_id, created_at) VALUES (?, ?)",
            (message_id, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except Exception as exc:
        if is_unique_violation(exc):
            return False
        raise
    finally:
        conn.close()


def prune_old_claims(days: int = 7) -> None:
    """Keep dedup table small."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = db_paths.connect()
    try:
        cur = conn.cursor()
        init_dedup_table(conn)
        execute(cur, "DELETE FROM webhook_dedup WHERE created_at < ?", (since,))
        conn.commit()
    finally:
        conn.close()
