"""
SQLite backup — run locally or on Render Cron.

Keeps the last N copies in BACKUP_DIR (default: ./backups).
On Render free tier, files survive restarts but not redeploys unless you use
a persistent disk (set BACKUP_DIR=/data/backups) or download backups periodically.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db_paths import BACKUP_DIR, DATABASE_PATH  # noqa: E402

KEEP_LAST = int(os.environ.get("BACKUP_KEEP", "7"))


def main() -> None:
    if not DATABASE_PATH.exists():
        print(f"No database at {DATABASE_PATH} — nothing to back up.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"wellness_{stamp}.db"
    shutil.copy2(DATABASE_PATH, dest)
    print(f"Backed up to {dest}")

    backups = sorted(BACKUP_DIR.glob("wellness_*.db"), key=lambda p: p.stat().st_mtime)
    while len(backups) > KEEP_LAST:
        old = backups.pop(0)
        old.unlink()
        print(f"Removed old backup {old.name}")


if __name__ == "__main__":
    main()
