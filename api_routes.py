"""Read-only REST endpoints for the Next.js dashboard (add DASHBOARD_API_KEY in prod)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from api_auth import require_dashboard_key
from db_paths import backend_label, connect, db_available, storage_kind
from db_sql import execute
from patterns import global_insights

router = APIRouter(prefix="/api", tags=["analytics"], dependencies=[Depends(require_dashboard_key)])


def _query(sql_str: str, params: tuple = ()) -> list:
    if not db_available():
        return []
    conn = connect()
    try:
        if storage_kind() != "postgres":
            conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        execute(cur, sql_str, params)
        rows = cur.fetchall()
        if storage_kind() == "postgres":
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in rows]
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/health")
def api_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "database": "present" if db_available() else "missing",
        "database_path": backend_label(),
        "storage": storage_kind(),
    }


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
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    activity_7d = _query(
        """SELECT COUNT(*) AS n FROM (
            SELECT timestamp AS t FROM mood_logs WHERE timestamp >= ?
            UNION ALL SELECT created_at FROM checkins WHERE created_at >= ?
            UNION ALL SELECT created_at FROM vent_logs WHERE created_at >= ?
        )""",
        (week_ago, week_ago, week_ago),
    )
    return {
        "users": users[0]["n"] if users else 0,
        "mood_logs": moods[0]["n"] if moods else 0,
        "crisis_flags_mood_table": crises[0]["n"] if crises else 0,
        "checkins": checkins[0]["n"] if checkins else 0,
        "vent_events": vents[0]["n"] if vents else 0,
        "crisis_flags_vent_table": vent_crises[0]["n"] if vent_crises else 0,
        "avg_mood_intensity": avg[0]["avg"] if avg and avg[0]["avg"] is not None else None,
        "activity_last_7d": activity_7d[0]["n"] if activity_7d else 0,
        "storage": storage_kind(),
    }


@router.get("/metrics/mood-trends")
def mood_trends(days: int = 30) -> Dict[str, Any]:
    days = max(7, min(days, 90))
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = _query(
        """
        SELECT date(timestamp) AS day,
               ROUND(AVG(intensity), 2) AS avg_intensity,
               COUNT(*) AS entries
        FROM mood_logs
        WHERE mood != 'crisis' AND intensity IS NOT NULL AND timestamp >= ?
        GROUP BY date(timestamp)
        ORDER BY day ASC
        """,
        (since,),
    )
    return {"days": days, "series": rows}


@router.get("/metrics/checkin-categories")
def checkin_categories() -> Dict[str, Any]:
    rows = _query(
        """
        SELECT category, COUNT(*) AS count
        FROM checkins
        GROUP BY category
        ORDER BY count DESC
        """
    )
    return {"items": rows}


@router.get("/vent/sentiment-summary")
def vent_sentiment_summary(days: int = 30) -> Dict[str, Any]:
    """Aggregated vent tone buckets — no message text."""
    days = max(7, min(days, 90))
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = _query(
        """
        SELECT sentiment_bucket, COUNT(*) AS count
        FROM vent_logs
        WHERE is_crisis = 0 AND created_at >= ?
        GROUP BY sentiment_bucket
        ORDER BY count DESC
        """,
        (since,),
    )
    crises = _query(
        "SELECT COUNT(*) AS n FROM vent_logs WHERE is_crisis = 1 AND created_at >= ?",
        (since,),
    )
    return {
        "days": days,
        "buckets": rows,
        "crisis_events": crises[0]["n"] if crises else 0,
    }


@router.get("/metrics/activity-trends")
def activity_trends(days: int = 30) -> Dict[str, Any]:
    """Daily event counts (mood + check-in + chat tone logs) — all users, anonymous."""
    days = max(7, min(days, 90))
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = _query(
        """
        SELECT day, SUM(events) AS events FROM (
            SELECT date(timestamp) AS day, COUNT(*) AS events
            FROM mood_logs
            WHERE mood != 'crisis' AND timestamp >= ?
            GROUP BY date(timestamp)
            UNION ALL
            SELECT date(created_at) AS day, COUNT(*) AS events
            FROM checkins
            WHERE created_at >= ?
            GROUP BY date(created_at)
            UNION ALL
            SELECT date(created_at) AS day, COUNT(*) AS events
            FROM vent_logs
            WHERE is_crisis = 0 AND created_at >= ?
            GROUP BY date(created_at)
        ) AS combined
        GROUP BY day
        ORDER BY day ASC
        """,
        (since, since, since),
    )
    active = _query(
        """
        SELECT COUNT(DISTINCT user_phone) AS n FROM (
            SELECT user_phone FROM mood_logs WHERE timestamp >= ?
            UNION SELECT user_phone FROM checkins WHERE created_at >= ?
            UNION SELECT user_phone FROM vent_logs WHERE created_at >= ?
        ) AS u
        """,
        (since, since, since),
    )
    return {
        "days": days,
        "series": rows,
        "active_users": active[0]["n"] if active else 0,
        "total_events": sum(r["events"] for r in rows),
    }


@router.get("/patterns/insights")
def patterns_insights(days: int = 14) -> Dict[str, Any]:
    return global_insights(days=days)


@router.get("/mood-logs")
def mood_logs(limit: int = 50) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    rows = _query(
        """
        SELECT date(timestamp) AS day, intensity, mood
        FROM mood_logs
        WHERE mood != 'crisis'
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
        SELECT date(created_at) AS day, intensity, category
        FROM checkins
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}


@router.get("/vent-logs")
def vent_logs(limit: int = 50) -> Dict[str, Any]:
    """Tone buckets only — never returns user message content."""
    limit = max(1, min(limit, 200))
    rows = _query(
        """
        SELECT date(created_at) AS day, sentiment_bucket, is_crisis, source
        FROM vent_logs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"items": rows}
