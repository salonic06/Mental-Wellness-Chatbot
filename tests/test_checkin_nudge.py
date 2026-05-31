from datetime import datetime
from zoneinfo import ZoneInfo

from checkin_nudge_scheduler import (
    get_reminder_status,
    nudges_enabled,
    run_daily_nudge_tick,
    set_daily_reminder,
    should_send_nudge_now,
)


def test_reminder_prefs(tmp_db, user_phone):
    assert get_reminder_status(user_phone)["enabled"] is False
    set_daily_reminder(user_phone, True)
    assert get_reminder_status(user_phone)["enabled"] is True


def test_nudges_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_DAILY_CHECKIN_NUDGES", raising=False)
    assert nudges_enabled() is False


def test_should_send_only_morning_window(monkeypatch):
    monkeypatch.setenv("DAILY_NUDGE_HOUR", "9")
    monkeypatch.setenv("DAILY_NUDGE_WINDOW_MINUTES", "30")
    tz = ZoneInfo("Asia/Kolkata")
    assert should_send_nudge_now(datetime(2026, 5, 31, 9, 15, tzinfo=tz)) is True
    assert should_send_nudge_now(datetime(2026, 5, 31, 9, 45, tzinfo=tz)) is False
    assert should_send_nudge_now(datetime(2026, 5, 31, 21, 15, tzinfo=tz)) is False


def test_tick_no_send_without_env(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ENABLE_DAILY_CHECKIN_NUDGES", "true")
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    set_daily_reminder(user_phone, True)
    assert run_daily_nudge_tick() == 0
