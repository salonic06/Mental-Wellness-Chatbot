from fastapi.testclient import TestClient

import db_paths
from app import app
from database import init_db


def test_health():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_api_metrics(tmp_db, monkeypatch):
    import api_routes

    monkeypatch.setattr(db_paths, "DATABASE_PATH", tmp_db)
    monkeypatch.setattr(api_routes, "DB_PATH", tmp_db)
    init_db(str(tmp_db))
    client = TestClient(app)
    summary = client.get("/api/metrics/summary").json()
    assert "users" in summary
