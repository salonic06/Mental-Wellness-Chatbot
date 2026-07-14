from datetime import datetime
from zoneinfo import ZoneInfo

from checkin_nudge_scheduler import (
    get_reminder_status,
    in_whatsapp_session,
    nudges_enabled,
    run_care_ping_tick,
    run_daily_nudge_tick,
    set_care_enabled,
    set_daily_reminder,
    set_reminder_mode,
    should_send_care_now,
    should_send_nudge_now,
    touch_last_seen,
)
from datetime import timedelta

from patterns import care_ping_reason


def test_reminder_prefs(tmp_db, user_phone):
    assert get_reminder_status(user_phone)["enabled"] is False
    set_daily_reminder(user_phone, True, mode="affirmation")
    status = get_reminder_status(user_phone)
    assert status["enabled"] is True
    assert status["mode"] == "affirmation"
    assert status["preferred_minute"] is not None


def test_reminder_mode_and_care(tmp_db, user_phone):
    set_daily_reminder(user_phone, True)
    set_reminder_mode(user_phone, "checkin")
    set_care_enabled(user_phone, True)
    status = get_reminder_status(user_phone)
    assert status["mode"] == "checkin"
    assert status["care_enabled"] is True


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


def test_multi_hour_morning_window(monkeypatch):
    monkeypatch.setenv("DAILY_NUDGE_HOUR", "8")
    monkeypatch.setenv("DAILY_NUDGE_WINDOW_MINUTES", "180")
    tz = ZoneInfo("Asia/Kolkata")
    assert should_send_nudge_now(datetime(2026, 5, 31, 8, 0, tzinfo=tz)) is True
    assert should_send_nudge_now(datetime(2026, 5, 31, 10, 30, tzinfo=tz)) is True
    assert should_send_nudge_now(datetime(2026, 5, 31, 11, 0, tzinfo=tz)) is False


def test_care_window(monkeypatch):
    monkeypatch.setenv("CARE_PING_HOUR", "15")
    monkeypatch.setenv("CARE_PING_WINDOW_MINUTES", "120")
    tz = ZoneInfo("Asia/Kolkata")
    assert should_send_care_now(datetime(2026, 5, 31, 15, 30, tzinfo=tz)) is True
    assert should_send_care_now(datetime(2026, 5, 31, 18, 0, tzinfo=tz)) is False


def test_whatsapp_session_gate(tmp_db, user_phone):
    assert in_whatsapp_session(user_phone) is False
    touch_last_seen(user_phone, datetime.now() - timedelta(hours=2))
    assert in_whatsapp_session(user_phone) is True
    touch_last_seen(user_phone, datetime.now() - timedelta(hours=30))
    assert in_whatsapp_session(user_phone) is False


def test_tick_no_send_without_env(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ENABLE_DAILY_CHECKIN_NUDGES", "true")
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    set_daily_reminder(user_phone, True)
    touch_last_seen(user_phone)
    assert run_daily_nudge_tick() == 0


def test_care_tick_skips_without_reason(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ENABLE_DAILY_CHECKIN_NUDGES", "true")
    monkeypatch.setenv("ENABLE_CARE_PINGS", "true")
    monkeypatch.setenv("CARE_PING_HOUR", "15")
    monkeypatch.setenv("CARE_PING_WINDOW_MINUTES", "120")
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    set_care_enabled(user_phone, True)
    touch_last_seen(user_phone)
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 5, 31, 15, 10, tzinfo=tz)
    assert care_ping_reason(user_phone) is None
    assert run_care_ping_tick(now) == 0
