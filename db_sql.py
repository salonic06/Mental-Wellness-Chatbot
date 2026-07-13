"""SQL helpers shared by SQLite (local/tests) and Postgres (Neon production)."""

from __future__ import annotations

from typing import Any, Tuple

from db_paths import use_postgres


def sql(text: str) -> str:
    if use_postgres():
        return text.replace("?", "%s")
    return text


def execute(cur, query: str, params: Tuple[Any, ...] = ()) -> None:
    cur.execute(sql(query), params)


def is_unique_violation(exc: BaseException) -> bool:
    if use_postgres():
        import psycopg2.errors

        return isinstance(exc, psycopg2.errors.UniqueViolation)
    import sqlite3

    return isinstance(exc, sqlite3.IntegrityError)


def is_db_error(exc: BaseException) -> bool:
    if use_postgres():
        import psycopg2

        return isinstance(exc, psycopg2.Error)
    import sqlite3

    return isinstance(exc, sqlite3.Error)


def insert_user_ignore(cur, phone_number: str, joined_date) -> None:
    if use_postgres():
        cur.execute(
            """INSERT INTO users (phone_number, joined_date)
               VALUES (%s, %s) ON CONFLICT (phone_number) DO NOTHING""",
            (phone_number, joined_date),
        )
    else:
        cur.execute(
            "INSERT OR IGNORE INTO users (phone_number, joined_date) VALUES (?, ?)",
            (phone_number, joined_date),
        )


def upsert_conversation_state(cur, user_phone: str, state: str, data_json: str) -> None:
    if use_postgres():
        cur.execute(
            """INSERT INTO conversation_state (user_phone, state, data_json)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_phone) DO UPDATE SET
                 state = EXCLUDED.state,
                 data_json = EXCLUDED.data_json""",
            (user_phone, state, data_json),
        )
    else:
        cur.execute(
            """INSERT OR REPLACE INTO conversation_state (user_phone, state, data_json)
               VALUES (?, ?, ?)""",
            (user_phone, state, data_json),
        )


def upsert_active_meditation(cur, user_phone: str, meditation_type: str) -> None:
    if use_postgres():
        cur.execute(
            """INSERT INTO active_meditations
               (user_phone, meditation_type, start_time, paused, step_index)
               VALUES (%s, %s, NULL, 0, 0)
               ON CONFLICT (user_phone) DO UPDATE SET
                 meditation_type = EXCLUDED.meditation_type,
                 start_time = NULL,
                 paused = 0,
                 step_index = 0""",
            (user_phone, meditation_type),
        )
    else:
        cur.execute(
            """INSERT OR REPLACE INTO active_meditations
               (user_phone, meditation_type, start_time, paused, step_index)
               VALUES (?, ?, NULL, 0, 0)""",
            (user_phone, meditation_type),
        )
