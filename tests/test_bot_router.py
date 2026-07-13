import os

from bot_router import process_message
from state_store import get_user_state


def test_start_and_help(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/start")
    assert "companion" in reply.text.lower() or "hey" in reply.text.lower()
    assert reply.list_sections is not None


def test_meditate_quick_ready(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    process_message(user_phone, "/meditate quick")
    assert get_user_state(user_phone)["state"] == "meditating"
    reply = process_message(user_phone, "ready")
    assert "breath" in reply.text.lower() or "Focus" in reply.text


def test_crisis_interrupts(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    process_message(user_phone, "/vent")
    reply = process_message(user_phone, "I want to end my life")
    assert "concerned" in reply.text.lower() or "emergency" in reply.text.lower()
    assert get_user_state(user_phone)["state"] == "initial"


def test_remind_on_off(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    on = process_message(user_phone, "/remind on")
    assert "ON" in on.text or "Reminder saved" in on.text
    off = process_message(user_phone, "/remind off")
    assert "OFF" in off.text


def test_admin_stats(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", user_phone)
    process_message(user_phone, "/start")
    stats = process_message(user_phone, "/stats")
    assert "Bot stats" in stats.text
    ping = process_message(user_phone, "/ping")
    assert "WHATSAPP_ACCESS_TOKEN" in ping.text


def test_free_text_hi_routes_companion(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "hi")
    assert reply.text
    lowered = reply.text.lower()
    assert "menu" in lowered or "here" in lowered or "doing" in lowered


def test_mood_without_args_starts_checkin(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/mood")
    assert "check-in" in reply.text.lower() or "1" in reply.text
    assert get_user_state(user_phone)["state"] == "checkin_mood"


def test_analyze_routes_to_summary(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/analyze")
    assert "check-in" in reply.text.lower() or "week" in reply.text.lower() or "mood" in reply.text.lower()
