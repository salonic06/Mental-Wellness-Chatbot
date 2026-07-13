"""Pattern detection over user wellness history."""

from datetime import datetime

import db_paths
from patterns import detect_user_patterns, patterns_context_block


def _seed_checkins(user_phone, rows):
    conn = db_paths.connect()
    c = conn.cursor()
    now = datetime.now().isoformat()
    for intensity, category in rows:
        c.execute(
            "INSERT INTO checkins (user_phone, intensity, category, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_phone, intensity, category, "", now),
        )
    conn.commit()
    conn.close()


def test_patterns_empty(tmp_db, user_phone):
    p = detect_user_patterns(user_phone)
    assert p["entry_count"] == 0
    assert p["insights"] == []


def test_patterns_top_category(tmp_db, user_phone):
    _seed_checkins(user_phone, [(5, "work"), (4, "work"), (6, "health")])
    p = detect_user_patterns(user_phone)
    assert p["top_category"] == "work"
    assert p["top_category_count"] == 2
    assert any("work" in i for i in p["insights"])


def test_patterns_context_block(tmp_db, user_phone):
    _seed_checkins(user_phone, [(5, "work"), (4, "work")])
    block = patterns_context_block(user_phone)
    assert "work" in block.lower()
