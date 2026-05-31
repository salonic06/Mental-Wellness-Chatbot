def test_affirmation(bot):
    msg = bot.daily_affirmation("", "919900000001")
    assert len(msg) > 10


def test_mood_log(bot, user_phone):
    bot.start_command("", user_phone)
    msg = bot.log_mood("8 good day", user_phone)
    assert "thanks" in msg.lower() or "mood" in msg.lower()


def test_invite_requires_display_number(tmp_db, user_phone, monkeypatch):
    monkeypatch.setenv("ADMIN_NUMBERS", user_phone)
    monkeypatch.delenv("WHATSAPP_DISPLAY_NUMBER", raising=False)
    from wellness_bot_class import WellnessBot

    msg = WellnessBot().admin_invite_command("", user_phone)
    assert "WHATSAPP_DISPLAY_NUMBER" in msg
