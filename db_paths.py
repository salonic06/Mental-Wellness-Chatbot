"""Single source of truth for SQLite file or Neon/Postgres (DATABASE_URL)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Union

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "wellness.db")))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(BASE_DIR / "backups")))

DbConnection = Union[sqlite3.Connection, "psycopg2.extensions.connection"]


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def use_postgres() -> bool:
    url = database_url().lower()
    return url.startswith("postgres://") or url.startswith("postgresql://")


def storage_kind() -> str:
    if use_postgres():
        return "postgres"
    if str(DATABASE_PATH).replace("\\", "/").startswith("/data/"):
        return "persistent"
    return "ephemeral"


def backend_label() -> str:
    if use_postgres():
        host = database_url().split("@")[-1].split("/")[0] if "@" in database_url() else "postgres"
        return f"postgres://{host}"
    return str(DATABASE_PATH)


def db_available() -> bool:
    if use_postgres():
        return bool(database_url())
    return DATABASE_PATH.exists()


def connect() -> DbConnection:
    if use_postgres():
        import psycopg2

        return psycopg2.connect(database_url())
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DATABASE_PATH))
