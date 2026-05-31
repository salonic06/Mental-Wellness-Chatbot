import json
import sqlite3
from typing import Any, Dict, Optional


def get_user_state(user_phone: str, db_path: str = "wellness.db") -> Dict[str, Any]:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT state, data_json FROM conversation_state WHERE user_phone = ?",
        (user_phone,),
    )
    row = c.fetchone()
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
    db_path: str = "wellness.db",
) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO conversation_state (user_phone, state, data_json)
           VALUES (?, ?, ?)""",
        (user_phone, state, json.dumps(data or {})),
    )
    conn.commit()
    conn.close()


def clear_user_state(user_phone: str, db_path: str = "wellness.db") -> None:
    set_user_state(user_phone, "initial", {}, db_path)
