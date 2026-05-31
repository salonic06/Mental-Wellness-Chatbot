from checkin_flow import handle_checkin_message, start_checkin
from state_store import get_user_state


def test_checkin_happy_path(tmp_db, user_phone):
    assert "1" in start_checkin(user_phone)
    assert get_user_state(user_phone)["state"] == "checkin_mood"

    r1 = handle_checkin_message(user_phone, "7")
    assert r1 and "area" in r1.lower()

    r2 = handle_checkin_message(user_phone, "work")
    assert r2 and ("note" in r2.lower() or "anything" in r2.lower())

    r3 = handle_checkin_message(user_phone, "busy week")
    assert r3
    assert get_user_state(user_phone)["state"] == "initial"


def test_checkin_cancel(tmp_db, user_phone):
    start_checkin(user_phone)
    msg = handle_checkin_message(user_phone, "/cancel")
    assert msg and "cancel" in msg.lower()
    assert get_user_state(user_phone)["state"] == "initial"
