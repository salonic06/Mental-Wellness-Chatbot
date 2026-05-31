import pytest

from wa_me import build_wa_me_link, normalize_wa_display_number


def test_normalize_strips_plus_and_spaces():
    assert normalize_wa_display_number("+1 (555) 123-4567") == "15551234567"


def test_build_link():
    assert build_wa_me_link("919876543210", "Hi") == "https://wa.me/919876543210?text=Hi"


def test_build_link_requires_digits():
    with pytest.raises(ValueError):
        build_wa_me_link("abc", "Hi")
