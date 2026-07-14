"""Pattern detection over user wellness history."""

from datetime import datetime

import db_paths
from patterns import care_ping_reason, detect_user_patterns, patterns_context_block


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


def test_care_ping_reason_trend_down(tmp_db, user_phone):
    # Older (better) then recent (worse) — intensities are newest-first in query
    # detect_user_patterns: first_half = later chronologically (older in list after mid)
    # intensities from checkins DESC then moods DESC — we insert with same timestamp
    # Use spaced timestamps via direct inserts
    import db_paths
    from datetime import datetime, timedelta

    conn = db_paths.connect()
    c = conn.cursor()
    base = datetime.now()
    # Older high moods, then recent low — insert older first with older timestamps
    rows = [
        (8, base - timedelta(days=10)),
        (7, base - timedelta(days=9)),
        (7, base - timedelta(days=8)),
        (3, base - timedelta(days=2)),
        (2, base - timedelta(days=1)),
        (2, base),
    ]
    for intensity, ts in rows:
        c.execute(
            "INSERT INTO checkins (user_phone, intensity, category, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_phone, intensity, "work", "", ts.isoformat()),
        )
    conn.commit()
    conn.close()
    assert care_ping_reason(user_phone) == "trend_down"


def test_care_ping_reason_low_avg(tmp_db, user_phone):
    _seed_checkins(user_phone, [(3, "health"), (2, "health"), (4, "health")])
    assert care_ping_reason(user_phone) in ("low_avg", "trend_down")
