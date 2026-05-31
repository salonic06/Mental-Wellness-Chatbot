from admin_stats import fetch_bot_stats, format_stats_message


def test_fetch_stats_empty_db(tmp_db):
    stats = fetch_bot_stats()
    assert stats.get("users") == 0
    msg = format_stats_message(stats)
    assert "Users: 0" in msg
