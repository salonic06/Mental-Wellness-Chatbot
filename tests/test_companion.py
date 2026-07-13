"""Tests for free-text companion routing."""

from companion import classify_free_text, companion_reply, handle_free_text


def test_classify_greeting():
    assert classify_free_text("hi") == "greeting"
    assert classify_free_text("Hello there") == "greeting"


def test_classify_vent_hint():
    assert classify_free_text("I'm really stressed about work") == "vent_hint"


def test_classify_open_share():
    assert classify_free_text("today was exhausting and I don't know what to do anymore about it") == "open_share"


def test_companion_fallback_greeting():
    msg = companion_reply("919900000099", "hey", "greeting")
    assert "here" in msg.lower() or "doing" in msg.lower()


def test_handle_free_text_hi(tmp_db, user_phone, monkeypatch):
    reply = handle_free_text(user_phone, "hi")
    assert reply.text
    assert reply.list_sections is not None


def test_handle_free_text_stressed(tmp_db, user_phone, monkeypatch):
    from state_store import get_user_state

    reply = handle_free_text(user_phone, "I'm so anxious right now")
    assert reply.text
    assert get_user_state(user_phone)["state"] == "chatting"
