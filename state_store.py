import json
from typing import Any, Dict, Optional

from db_paths import DATABASE_PATH, connect
from db_sql import execute, upsert_conversation_state

_DB = str(DATABASE_PATH)


def get_user_state(user_phone: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "SELECT state, data_json FROM conversation_state WHERE user_phone = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row:
        return {"state": "initial", "data": {}}
    state, data_json = row
    data = json.loads(data_json) if data_json else {}
    return {"state": state, "data": data}


def set_user_state(
    user_phone: str,
    state: str,
    data: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> None:
    conn = connect()
    try:
        c = conn.cursor()
        upsert_conversation_state(c, user_phone, state, json.dumps(data or {}))
        conn.commit()
    finally:
        conn.close()


def clear_user_state(user_phone: str, db_path: Optional[str] = None) -> None:
    set_user_state(user_phone, "initial", {}, db_path)
