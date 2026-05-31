import sqlite3

from db_paths import DATABASE_PATH


def init_db(db_path=None) -> None:
    path = db_path or str(DATABASE_PATH)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS active_meditations
           (user_phone TEXT PRIMARY KEY, meditation_type TEXT, start_time DATETIME, paused INTEGER DEFAULT 0)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
           (phone_number TEXT PRIMARY KEY, name TEXT, joined_date DATE)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS mood_logs
           (id INTEGER PRIMARY KEY AUTOINCREMENT, user_phone TEXT, mood TEXT,
            intensity INTEGER, timestamp DATETIME, notes TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS meditation_sessions
           (id INTEGER PRIMARY KEY AUTOINCREMENT, user_phone TEXT, duration INTEGER,
            type TEXT, started_at DATETIME, completed_at DATETIME)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS conversation_state
           (user_phone TEXT PRIMARY KEY, state TEXT NOT NULL, data_json TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS checkins
           (id INTEGER PRIMARY KEY AUTOINCREMENT, user_phone TEXT, intensity INTEGER,
            category TEXT, note TEXT, created_at DATETIME)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS vent_logs
           (id INTEGER PRIMARY KEY AUTOINCREMENT, user_phone TEXT, sentiment_bucket TEXT,
            word_count INTEGER, is_crisis INTEGER DEFAULT 0, created_at DATETIME)"""
    )
    try:
        c.execute("ALTER TABLE meditation_sessions ADD COLUMN started_at DATETIME")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE vent_logs ADD COLUMN source TEXT DEFAULT 'vent'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute(
            "ALTER TABLE active_meditations ADD COLUMN step_index INTEGER DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
