"""
Seed demo mood logs and check-ins for dashboard / ML training.
Does not delete existing data. Uses fake phone numbers 9199000000XX.

Run: py scripts/seed_demo_data.py
"""

import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from db_paths import DATABASE_PATH  # noqa: E402

DB_PATH = DATABASE_PATH

CATEGORIES = ["work", "health", "relationships", "studies", "other"]
NOTES = [
    "Busy week at college",
    "Slept poorly",
    "Feeling more balanced today",
    "Exam stress",
    "Good conversation with a friend",
    "Needed a break",
    "",
]


def seed(n_users: int = 8, days: int = 30, checkins_per_user: int = 4) -> None:
    sys.path.insert(0, str(ROOT))
    from database import init_db

    init_db(DB_PATH)
    random.seed(42)
    now = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for i in range(1, n_users + 1):
        phone = f"9199000000{i:02d}"
        joined = now - timedelta(days=random.randint(10, 60))
        c.execute(
            "INSERT OR IGNORE INTO users (phone_number, joined_date) VALUES (?, ?)",
            (phone, joined.date()),
        )

        for _ in range(checkins_per_user):
            intensity = random.choices(
                range(1, 11),
                weights=[1, 1, 2, 2, 3, 4, 5, 6, 7, 8],
            )[0]
            category = random.choice(CATEGORIES)
            note = random.choice(NOTES)
            created = now - timedelta(
                days=random.randint(0, days),
                hours=random.randint(0, 23),
            )
            c.execute(
                """INSERT INTO checkins (user_phone, intensity, category, note, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (phone, intensity, category, note, created),
            )
            c.execute(
                """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (phone, "checkin", intensity, created, f"[{category}] {note}".strip()),
            )

        # Extra standalone mood logs
        for _ in range(random.randint(2, 5)):
            intensity = random.randint(3, 9)
            created = now - timedelta(days=random.randint(0, days))
            c.execute(
                """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (phone, "mood_log", intensity, created, random.choice(NOTES)),
            )

    conn.commit()
    c.execute("SELECT COUNT(*) FROM checkins")
    total_checkins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM mood_logs")
    total_moods = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    conn.close()

    print(f"Demo data added. Totals: {total_users} users, {total_checkins} check-ins, {total_moods} mood logs.")


if __name__ == "__main__":
    seed()
