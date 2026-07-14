"""WhatsApp Cloud API payload limits — regressions here break production sends."""

from languages import (
    WHATSAPP_LIST_MAX_ROWS,
    checkin_category_list,
    language_list_sections,
    list_row_count,
    main_menu_sections,
)


def test_language_picker_respects_whatsapp_row_limit():
    assert list_row_count(language_list_sections()) <= WHATSAPP_LIST_MAX_ROWS


def test_all_five_languages_in_picker():
    ids = [row["id"] for section in language_list_sections() for row in section["rows"]]
    assert ids == ["lang_en", "lang_hi", "lang_mr", "lang_gu", "lang_bn"]


def test_main_menu_and_checkin_lists_within_limit(tmp_db):
    phone = "919900000004"
    assert list_row_count(main_menu_sections(phone)) <= WHATSAPP_LIST_MAX_ROWS
    assert list_row_count(checkin_category_list(phone)) <= WHATSAPP_LIST_MAX_ROWS
