"""Read-only REST endpoints for dashboard / React (local demo — add auth before production)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from db_paths import DATABASE_PATH

DB_PATH = DATABASE_PATH

router = APIRouter(prefix="/api", tags=["analytics"])


def _query(sql: str, params: tuple = ()) -> list:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


@router.get("/health")
def api_health() -> Dict[str, str]:
    return {"status": "ok", "database": "present" if DB_PATH.exists() else "missing"}


@router.get("/metrics/summary")
def metrics_summary() -> Dict[str, Any]:
    users = _query("SELECT COUNT(*) AS n FROM users")
    moods = _query("SELECT COUNT(*) AS n FROM mood_logs WHERE mood != 'crisis'")
    crises = _query("SELECT COUNT(*) AS n FROM mood_logs WHERE mood = 'crisis'")
    checkins = _query("SELECT COUNT(*) AS n FROM checkins")
    vents = _query("SELECT COUNT(*) AS n FROM vent_logs WHERE is_crisis = 0")
    vent_crises = _query("SELECT COUNT(*) AS n FROM vent_logs WHERE is_crisis = 1")
    avg = _query(
        "SELECT ROUND(AVG(intensity), 2) AS avg FROM mood_logs "
        "WHERE mood != 'crisis' AND intensity IS NOT NULL"
    )
    return {
        "users": users[0]["n"] if users else 0,
        "mood_logs": moods[0]["n"] if moods else 0,
        "crisis_flags_mood_table": crises[0]["n"] if crises else 0,
        "checkins": checkins[0]["n"] if checkins else 0,
        "vent_events": vents[0]["n"] if vents else 0,
        "crisis_flags_vent_table": vent_crises[0]["n"] if vent_crises else 0,
        "avg_mood_intensity": avg[0]["avg"] if avg and avg[0]["avg"] is not None else None,
    }


@router.get("/mood-logs")
def mood_logs(limit: int = 50) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    rows = _query(
        """
        SELECT timestamp, intensity, mood, notes
        FROM mood_logs
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}


@router.get("/checkins")
def checkins(limit: int = 50) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    rows = _query(
        """
        SELECT created_at, intensity, category, note
        FROM checkins
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}


@router.get("/vent-logs")
def vent_logs(limit: int = 50) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    rows = _query(
        """
        SELECT created_at, sentiment_bucket, word_count, is_crisis, source
        FROM vent_logs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}
