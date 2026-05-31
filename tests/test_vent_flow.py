from vent_flow import handle_vent_message, start_vent
from state_store import get_user_state


def test_vent_flow(tmp_db, user_phone):
    intro = start_vent(user_phone)
    assert get_user_state(user_phone)["state"] == "venting"
    assert "/done" in intro.lower()

    reply = handle_vent_message(user_phone, "Today was stressful but I managed")
    assert reply and "Detected tone" in reply

    done = handle_vent_message(user_phone, "/done")
    assert done
    assert get_user_state(user_phone)["state"] == "initial"
