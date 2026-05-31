from meditation_scheduler import (
    _minutes_after_ready,
    _minutes_between_parts,
    clean_script_body,
)


def test_clean_script_body():
    raw = "Breathe in\n[2 minutes passed]"
    assert "[2 minutes passed]" not in clean_script_body(raw)
    assert "Breathe in" in clean_script_body(raw)


def test_quick_session_timing():
    intervals = [0, 1, 2, 3]
    assert _minutes_after_ready(intervals, 2) == 1.0
    assert _minutes_after_ready(intervals, 3) == 2.0
    assert _minutes_between_parts(intervals, 1, 2) == 1.0
    assert _minutes_between_parts(intervals, 2, 3) == 1.0
