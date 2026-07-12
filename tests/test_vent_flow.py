from vent_flow import handle_vent_message, start_vent
from state_store import get_user_state


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

    start_vent(user_phone)
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


def test_vent_flow(tmp_db, user_phone):
    intro = start_vent(user_phone)
    assert get_user_state(user_phone)["state"] == "venting"
    assert "/done" in intro.lower()

    reply = handle_vent_message(user_phone, "Today was stressful but I managed")
    assert reply and "Detected tone" in reply

    done = handle_vent_message(user_phone, "/done")
    assert done
    assert get_user_state(user_phone)["state"] == "initial"
