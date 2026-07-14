from languages import (
    detect_language_from_text,
    LANG_PICKER_MORE_ID,
    normalize_lang,
    parse_language_choice,
    set_user_language,
    get_user_language,
    main_menu_sections,
    language_list_sections,
)


def test_detect_scripts():
    assert detect_language_from_text("मैं ठीक नहीं") == "hi"
    assert detect_language_from_text("நான் சரியில்லை") == "ta"
    assert detect_language_from_text("আমি ভালো নই") == "bn"
    assert detect_language_from_text("hello") is None
    assert detect_language_from_text("/start") is None


def test_set_and_get_language(tmp_db):
    phone = "919900000001"
    set_user_language(phone, "ta")
    assert get_user_language(phone) == "ta"
    set_user_language(phone, "bn")
    assert get_user_language(phone) == "bn"


def test_parse_language_choice():
    assert parse_language_choice("lang_te") == "te"
    assert parse_language_choice("tamil") == "ta"
    assert parse_language_choice("nope") is None


def test_language_list_has_indian_langs():
    from languages import LANG_PICKER_MORE_ID, list_row_count

    page1 = language_list_sections(page=1)
    page2 = language_list_sections(page=2)
    assert list_row_count(page1) <= 10
    assert list_row_count(page2) <= 10
    top_ids = [row["id"] for row in page1[0]["rows"] if row["id"] != LANG_PICKER_MORE_ID]
    assert top_ids == ["lang_en", "lang_hi", "lang_mr", "lang_gu", "lang_bn"]
    ids = [row["id"] for sec in page1 for row in sec["rows"]]
    ids += [row["id"] for sec in page2 for row in sec["rows"]]
    assert "lang_hi" in ids
    assert "lang_ta" in ids
    assert "lang_ur" in ids
    assert LANG_PICKER_MORE_ID in ids


def test_language_picker_more_page(tmp_db):
    from bot_router import process_message

    reply = process_message("919900000003", LANG_PICKER_MORE_ID)
    assert reply.list_sections is not None
    ids = [row["id"] for sec in reply.list_sections for row in sec["rows"]]
    assert "lang_ur" in ids


def test_main_menu_hindi(tmp_db):
    set_user_language("919900000002", "hi")
    sections = main_menu_sections("919900000002")
    assert sections[0]["rows"][1]["title"] == "Baat karein"


def test_normalize_lang():
    assert normalize_lang("lang_mr") == "mr"
    assert normalize_lang("xx") == "en"
