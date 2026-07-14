from vent_flow import handle_vent_message, start_vent
from state_store import get_user_state
from session_outcomes import parse_mood_reply


def test_parse_mood_reply():
    assert parse_mood_reply("7") == (7, False)
    assert parse_mood_reply("skip") == (None, True)
    assert parse_mood_reply("nope") == (None, False)


def test_vent_session_history_accumulates(tmp_db, user_phone, monkeypatch):
    """Vent turns are stored so the LLM sees the full session, not just the last line."""
    import llm_wellness

    captured = {"calls": []}

    def fake_reply(user_text, sentiment_bucket, user_phone, vent_history=None):
        captured["calls"].append(
            {"latest": user_text, "hist_len": len(vent_history or [])}
        )
        captured["history"] = vent_history or []
        captured["latest"] = user_text
        return f"Reply to: {user_text}"

    monkeypatch.setattr(llm_wellness, "empathetic_vent_reply", fake_reply)
    monkeypatch.setattr(llm_wellness, "chat_open_reply", lambda phone: None)

    start_vent(user_phone)
    assert get_user_state(user_phone)["state"] == "chat_pre_mood"
    handle_vent_message(user_phone, "6")
    assert get_user_state(user_phone)["state"] == "chatting"

    handle_vent_message(user_phone, "Work was awful today")
    assert captured["latest"] == "Work was awful today"
    assert captured["history"] == []

    handle_vent_message(user_phone, "My manager keeps piling on deadlines")
    assert captured["latest"] == "My manager keeps piling on deadlines"
    assert captured["calls"] == [
        {"latest": "Work was awful today", "hist_len": 0},
        {"latest": "My manager keeps piling on deadlines", "hist_len": 2},
    ]
    prior = captured["history"]
    assert len(prior) >= 2
    assert prior[0]["role"] == "user"
    assert "Work was awful" in prior[0]["content"]


def test_vent_flow_with_impact_moods(tmp_db, user_phone, monkeypatch):
    monkeypatch.setattr(
        "llm_wellness.chat_open_reply",
        lambda phone: None,
    )
    intro = start_vent(user_phone)
    assert get_user_state(user_phone)["state"] == "chat_pre_mood"
    assert "1" in intro and "10" in intro
    assert "/done" not in intro.lower()

    ack = handle_vent_message(user_phone, "4")
    assert get_user_state(user_phone)["state"] == "chatting"
    assert ack

    reply = handle_vent_message(user_phone, "Today was stressful but I managed")
    assert reply and ("Detected tone" in reply or "Tone:" in reply or "listening" in reply.lower() or len(reply) > 10)

    post_ask = handle_vent_message(user_phone, "/done")
    assert get_user_state(user_phone)["state"] == "chat_post_mood"
    assert "1" in post_ask and "10" in post_ask

    done = handle_vent_message(user_phone, "7")
    assert get_user_state(user_phone)["state"] == "initial"
    assert done
    assert "+3" in done or "3" in done
