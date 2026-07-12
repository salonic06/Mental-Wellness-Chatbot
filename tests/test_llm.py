"""Tests for the pluggable LLM layer and its graceful fallbacks."""

from datetime import datetime

import db_paths
import llm_client
import llm_wellness


def _clear_llm_env(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def test_disabled_by_default(monkeypatch):
    _clear_llm_env(monkeypatch)
    assert llm_client.is_enabled() is False
    assert llm_client.generate("sys", "hi") is None


def test_enabled_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm_client.is_enabled() is False
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert llm_client.is_enabled() is True


def test_vent_uses_llm_when_available(tmp_db, user_phone, monkeypatch):
    from vent_flow import handle_vent_message, start_vent

    start_vent(user_phone)
    monkeypatch.setattr(
        llm_client, "generate", lambda *a, **k: "I hear how heavy that felt today."
    )
    reply = handle_vent_message(user_phone, "Work was horrible today")
    assert "I hear how heavy that felt today." in reply
    assert "Detected tone" not in reply  # LLM path replaces the deterministic reply


def test_vent_falls_back_without_llm(tmp_db, user_phone, monkeypatch):
    _clear_llm_env(monkeypatch)
    from vent_flow import handle_vent_message, start_vent

    start_vent(user_phone)
    reply = handle_vent_message(user_phone, "Work was horrible today")
    assert "Detected tone" in reply  # deterministic fallback preserved


def test_affirmation_falls_back_without_llm(bot, user_phone, monkeypatch):
    _clear_llm_env(monkeypatch)
    msg = bot.daily_affirmation("", user_phone)
    assert len(msg) > 10


def test_affirmation_uses_llm_when_available(bot, user_phone, monkeypatch):
    monkeypatch.setattr(
        llm_client, "generate", lambda *a, **k: "You are steadier than you feel."
    )
    msg = bot.daily_affirmation("", user_phone)
    assert msg == "You are steadier than you feel."


def _seed_moods(user_phone, values):
    conn = db_paths.connect()
    c = conn.cursor()
    now = datetime.now().isoformat()
    for v in values:
        c.execute(
            "INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_phone, "checkin", v, now, ""),
        )
    c.execute(
        "INSERT INTO checkins (user_phone, intensity, category, note, created_at) "
        "VALUES (?, 5, 'work', 'deadlines', ?)",
        (user_phone, now),
    )
    conn.commit()
    conn.close()


def test_weekly_summary_empty(tmp_db, user_phone):
    text = llm_wellness.weekly_summary_text(user_phone)
    assert "No check-ins" in text


def test_weekly_summary_templated_fallback(tmp_db, user_phone, monkeypatch):
    _clear_llm_env(monkeypatch)
    _seed_moods(user_phone, [6, 7, 8])
    text = llm_wellness.weekly_summary_text(user_phone)
    assert "average mood" in text.lower()
    assert "7.0/10" in text


def test_llm_crisis_sentinel_routes_to_crisis(tmp_db, user_phone, monkeypatch):
    """If the model flags risk the phrase list missed, we show crisis resources."""
    from vent_flow import handle_vent_message, start_vent

    start_vent(user_phone)
    monkeypatch.setattr(
        "llm_wellness.empathetic_vent_reply",
        lambda *a, **k: "[[CRISIS]]",
    )
    reply = handle_vent_message(user_phone, "everything feels pointless lately")
    assert "iCall" in reply or "1860" in reply or "emergency" in reply.lower()
    assert "[[CRISIS]]" not in reply  # sentinel must never leak to the user


def test_expanded_crisis_phrases():
    from sentiment_nlp import detect_crisis

    assert detect_crisis("I feel like everyone would be better without me")
    assert detect_crisis("I just want to disappear")
    assert detect_crisis("there's no point in living")
    assert not detect_crisis("this deadline is stressing me out")
