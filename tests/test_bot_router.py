import pytest

from bot_router import process_message
from languages import set_user_language
from state_store import get_user_state


def test_start_shows_menu_not_language_picker(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/start")
    assert reply.list_sections is not None
    ids = [row["id"] for row in reply.list_sections[0]["rows"]]
    assert "cmd_language" in ids
    assert "cmd_remind" in ids
    assert "cmd_care" in ids
    assert "cmd_help" in ids
    assert "lang_hi" not in ids


def test_language_command_and_selection(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    process_message(user_phone, "/start")
    picker = process_message(user_phone, "/language")
    assert picker.list_sections is not None
    reply = process_message(user_phone, "lang_hi")
    assert "नमस्ते" in reply.text or "स्वास्थ्य" in reply.text
    assert reply.list_sections is not None


def test_language_slash_with_name(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/language marathi")
    assert "मराठी" in reply.text or "Marathi" in reply.text or "companion" in reply.text.lower()


def test_vent_intro_uses_locale(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setattr("llm_wellness.chat_open_reply", lambda phone: None)
    set_user_language(user_phone, "hi")
    reply = process_message(user_phone, "/vent")
    assert "जगह" in reply.text or "महसूस" in reply.text or "लिख" in reply.text
    assert get_user_state(user_phone)["state"] == "chat_pre_mood"


def test_breathe_uses_locale(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    set_user_language(user_phone, "bn")
    reply = process_message(user_phone, "/breathe")
    assert reply.buttons is not None


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
    assert "morning" in on.text.lower() or "notes" in on.text.lower()
    assert "UptimeRobot" not in on.text
    off = process_message(user_phone, "/remind off")
    assert "morning" in off.text.lower() or "notes" in off.text.lower()


def test_care_on_off(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    on = process_message(user_phone, "/care on")
    assert "care" in on.text.lower() or "holding" in on.text.lower()
    assert "UptimeRobot" not in on.text
    off = process_message(user_phone, "/care off")
    assert "won't" in off.text.lower() or "check-in" in off.text.lower()


def test_admin_stats(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", user_phone)
    process_message(user_phone, "/start")
    process_message(user_phone, "/language hindi")
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


def test_meditate_marathi_shell_localized(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setattr(
        "llm_wellness.localize_wellness_content",
        lambda phone, text, kind="meditation": "तुमच्या दहा मिनिटांच्या ध्यान सत्रात स्वागत आहे.",
    )
    set_user_language(user_phone, "mr")
    choose = process_message(user_phone, "/meditate")
    assert "Choose your meditation" not in choose.text
    assert "ध्यान" in choose.text
    assert get_user_state(user_phone)["state"] == "meditation_choose"
    intro = process_message(user_phone, "med_medium")
    assert "Welcome to your" not in intro.text
    assert "ready" in intro.text.lower()
    assert get_user_state(user_phone)["state"] == "meditating"
    help_msg = process_message(user_phone, "great")
    assert "During meditation" not in help_msg.text
    assert "ready" in help_msg.text.lower() or "ध्यान" in help_msg.text


def test_done_during_meditation_ends_session(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    set_user_language(user_phone, "mr")
    process_message(user_phone, "/meditate medium")
    reply = process_message(user_phone, "/done")
    assert "No open chat" not in reply.text
    assert get_user_state(user_phone)["state"] == "initial"


def test_vent_while_already_chatting_is_warm(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setattr(
        "llm_wellness.chat_already_open_reply",
        lambda phone: "I'm still right here with you — go ahead.",
    )
    monkeypatch.setattr("llm_wellness.chat_open_reply", lambda phone: None)
    process_message(user_phone, "/vent")
    process_message(user_phone, "5")
    assert get_user_state(user_phone)["state"] == "chatting"
    reply = process_message(user_phone, "cmd_vent")
    assert "Keep sharing" not in reply.text
    assert "/done" not in reply.text
    assert "still right here" in reply.text.lower()


def test_start_chat_open_avoids_command_footer(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    monkeypatch.setattr(
        "llm_wellness.chat_open_reply",
        lambda phone: "I'm here with you — what's been sitting with you today?",
    )
    reply = process_message(user_phone, "cmd_vent")
    assert "This is your space" not in reply.text
    assert "/done" not in reply.text
    assert "I'm here with you" in reply.text
    assert get_user_state(user_phone)["state"] == "chat_pre_mood"


def test_analyze_routes_to_summary(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", "")
    reply = process_message(user_phone, "/analyze")
    assert "check-in" in reply.text.lower() or "week" in reply.text.lower() or "mood" in reply.text.lower()
