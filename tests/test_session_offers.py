"""Tests for follow-up offers and command normalization."""

from bot_router import process_message
from chat_flow import enter_chat_with_context, start_chat
from command_normalize import normalize_inbound
from session_offers import set_pending_offer
from state_store import get_user_state


def test_normalize_checkin_hyphen():
    assert normalize_inbound("/check-in") == "/checkin"


def test_pause_chat_button_outside_chat(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "vent_done")
    assert "pause" in reply.text.lower() or "doing" in reply.text.lower()
    assert "didn't catch" not in reply.text.lower()


def test_pause_chat_button_inside_chat(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setattr("llm_wellness.chat_open_reply", lambda phone: None)
    start_chat(user_phone)
    process_message(user_phone, "skip")  # pre mood
    reply = process_message(user_phone, "vent_done")
    assert get_user_state(user_phone)["state"] == "chat_post_mood"
    assert "1" in reply.text and "10" in reply.text
    process_message(user_phone, "skip")
    assert get_user_state(user_phone)["state"] == "initial"


def test_sure_fulfills_pending_affirmation(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    enter_chat_with_context(user_phone, "Want an affirmation?", pending_offer="/affirmation")
    reply = process_message(user_phone, "Sure!")
    assert reply.text
    assert len(reply.text) > 5


def test_yea_starts_meditation_offer(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    set_pending_offer(user_phone, "/meditate medium")
    reply = process_message(user_phone, "yea")
    assert "meditation" in reply.text.lower() or "ready" in reply.text.lower()
