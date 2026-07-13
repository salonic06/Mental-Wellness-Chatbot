import sqlite3

from db_paths import DATABASE_PATH, connect, use_postgres


def init_db(db_path=None) -> None:
    if use_postgres():
        _init_postgres()
    else:
        _init_sqlite(db_path or str(DATABASE_PATH))


def _init_postgres() -> None:
    conn = connect()
    try:
        c = conn.cursor()
        statements = [
            """CREATE TABLE IF NOT EXISTS active_meditations (
                   user_phone TEXT PRIMARY KEY,
                   meditation_type TEXT,
                   start_time TIMESTAMP,
                   paused INTEGER DEFAULT 0,
                   step_index INTEGER DEFAULT 0
               )""",
            """CREATE TABLE IF NOT EXISTS users (
                   phone_number TEXT PRIMARY KEY,
                   name TEXT,
                   joined_date TIMESTAMP
               )""",
            """CREATE TABLE IF NOT EXISTS mood_logs (
                   id SERIAL PRIMARY KEY,
                   user_phone TEXT,
                   mood TEXT,
                   intensity INTEGER,
                   timestamp TIMESTAMP,
                   notes TEXT
               )""",
            """CREATE TABLE IF NOT EXISTS meditation_sessions (
                   id SERIAL PRIMARY KEY,
                   user_phone TEXT,
                   duration INTEGER,
                   type TEXT,
                   started_at TIMESTAMP,
                   completed_at TIMESTAMP
               )""",
            """CREATE TABLE IF NOT EXISTS conversation_state (
                   user_phone TEXT PRIMARY KEY,
                   state TEXT NOT NULL,
                   data_json TEXT
               )""",
            """CREATE TABLE IF NOT EXISTS checkins (
                   id SERIAL PRIMARY KEY,
                   user_phone TEXT,
                   intensity INTEGER,
                   category TEXT,
                   note TEXT,
                   created_at TIMESTAMP
               )""",
            """CREATE TABLE IF NOT EXISTS vent_logs (
                   id SERIAL PRIMARY KEY,
                   user_phone TEXT,
                   sentiment_bucket TEXT,
                   word_count INTEGER,
                   is_crisis INTEGER DEFAULT 0,
                   source TEXT DEFAULT 'vent',
                   created_at TIMESTAMP
               )""",
            """CREATE TABLE IF NOT EXISTS daily_reminders (
                   user_phone TEXT PRIMARY KEY,
                   enabled INTEGER DEFAULT 0,
                   last_sent_date TEXT
               )""",
            """CREATE TABLE IF NOT EXISTS webhook_dedup (
                   message_id TEXT PRIMARY KEY,
                   created_at TEXT NOT NULL
               )""",
        ]
        for stmt in statements:
            c.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def _init_sqlite(path: str) -> None:
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
    c.execute(
        """CREATE TABLE IF NOT EXISTS daily_reminders
           (user_phone TEXT PRIMARY KEY, enabled INTEGER DEFAULT 0,
            last_sent_date TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS webhook_dedup
           (message_id TEXT PRIMARY KEY, created_at TEXT NOT NULL)"""
    )
    conn.commit()
    conn.close()
