from fastapi.testclient import TestClient

import api_routes
import db_paths
from app import app
from database import init_db


def test_health():
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "llm" in body and "enabled" in body["llm"]


def test_api_metrics(tmp_db, monkeypatch):
    monkeypatch.setattr(db_paths, "DATABASE_PATH", tmp_db)
    init_db(str(tmp_db))
    client = TestClient(app)
    summary = client.get("/api/metrics/summary").json()
    assert "users" in summary


def test_api_requires_key_when_set(tmp_db, monkeypatch):
    monkeypatch.setenv("DASHBOARD_API_KEY", "secret-key")
    monkeypatch.setattr(db_paths, "DATABASE_PATH", tmp_db)
    init_db(str(tmp_db))
    client = TestClient(app)
    assert client.get("/api/metrics/summary").status_code == 401
    r = client.get(
        "/api/metrics/summary",
        headers={"X-Dashboard-Key": "secret-key"},
    )
    assert r.status_code == 200


def test_api_mood_trends(tmp_db, monkeypatch):
    monkeypatch.setattr(db_paths, "DATABASE_PATH", tmp_db)
    init_db(str(tmp_db))
    client = TestClient(app)
    body = client.get("/api/metrics/mood-trends").json()
    assert "series" in body


def test_api_patterns(tmp_db, monkeypatch):
    monkeypatch.setattr(db_paths, "DATABASE_PATH", tmp_db)
    init_db(str(tmp_db))
    client = TestClient(app)
    body = client.get("/api/patterns/insights").json()
    assert "insights" in body
