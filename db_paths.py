"""Single source of truth for SQLite location (local, Render disk, or custom path)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# On Render with a persistent disk: set DATABASE_PATH=/data/wellness.db
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "wellness.db")))

# Backup folder (use /data/backups when disk is mounted)
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(BASE_DIR / "backups")))


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DATABASE_PATH))
