"""WhatsApp Cloud API payload limits — regressions here break production sends."""

from languages import (
    LANG_PICKER_MORE_ID,
    WHATSAPP_LIST_MAX_ROWS,
    checkin_category_list,
    language_list_sections,
    list_row_count,
    main_menu_sections,
)


def test_language_picker_respects_whatsapp_row_limit():
    assert list_row_count(language_list_sections(page=1)) <= WHATSAPP_LIST_MAX_ROWS
    assert list_row_count(language_list_sections(page=2)) <= WHATSAPP_LIST_MAX_ROWS


def test_all_languages_reachable_via_picker_pages():
    ids = []
    for page in (1, 2):
        for section in language_list_sections(page=page):
            for row in section["rows"]:
                ids.append(row["id"])
    lang_ids = {i for i in ids if i.startswith("lang_") and i != LANG_PICKER_MORE_ID}
    assert lang_ids == {
        "lang_en",
        "lang_hi",
        "lang_bn",
        "lang_ta",
        "lang_te",
        "lang_mr",
        "lang_gu",
        "lang_kn",
        "lang_ml",
        "lang_pa",
        "lang_ur",
    }


def test_main_menu_and_checkin_lists_within_limit(tmp_db):
    phone = "919900000004"
    assert list_row_count(main_menu_sections(phone)) <= WHATSAPP_LIST_MAX_ROWS
    assert list_row_count(checkin_category_list(phone)) <= WHATSAPP_LIST_MAX_ROWS
