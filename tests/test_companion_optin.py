from companion_optin import soft_opt_in_suggestion
from checkin_nudge_scheduler import get_reminder_status, set_care_enabled, set_daily_reminder
from session_offers import get_pending_offer
from bot_router import process_message


def test_soft_optin_morning_when_off(tmp_db, user_phone):
    hint = soft_opt_in_suggestion(user_phone, prefer="morning")
    assert "morning" in hint.lower()
    assert get_pending_offer(user_phone) == "/remind on"


def test_soft_optin_skips_if_already_on(tmp_db, user_phone):
    set_daily_reminder(user_phone, True)
    assert soft_opt_in_suggestion(user_phone, prefer="morning") == ""


def test_soft_optin_care_on_low_mood(tmp_db, user_phone):
    hint = soft_opt_in_suggestion(user_phone, prefer="care", intensity=3)
    assert "yes" in hint.lower()
    assert get_pending_offer(user_phone) == "/care on"


def test_affirmation_can_offer_morning(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setenv("ENABLE_DAILY_CHECKIN_NUDGES", "true")
    reply = process_message(user_phone, "/affirmation")
    assert "yes" in reply.text.lower() or "morning" in reply.text.lower()
    # Accept
    on = process_message(user_phone, "yes")
    assert get_reminder_status(user_phone)["enabled"] is True
    assert "morning" in on.text.lower() or "note" in on.text.lower()
    assert "UptimeRobot" not in on.text
    assert "Asia/Kolkata" not in on.text


def test_remind_on_copy_is_human(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setenv("ENABLE_DAILY_CHECKIN_NUDGES", "true")
    reply = process_message(user_phone, "/remind on")
    assert "UptimeRobot" not in reply.text
    assert "/health" not in reply.text
    assert "WhatsApp rule" not in reply.text
    assert "morning" in reply.text.lower()
