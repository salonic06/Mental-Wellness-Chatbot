from languages import (
    LANGUAGES,
    STRINGS,
    effective_language,
    get_user_language,
    language_list_sections,
    list_row_count,
    normalize_lang,
    parse_language_choice,
    set_user_language,
    t,
    main_menu_sections,
)


def test_supported_five_languages():
    codes = {code for code, _, _ in LANGUAGES}
    assert codes == {"en", "hi", "mr", "gu", "bn"}


def test_set_and_get_language(tmp_db):
    phone = "919900000001"
    set_user_language(phone, "mr")
    assert get_user_language(phone) == "mr"
    set_user_language(phone, "bn")
    assert get_user_language(phone) == "bn"


def test_effective_language_uses_stored_preference_only(tmp_db):
    phone = "919900000002"
    assert effective_language(phone) == "en"
    set_user_language(phone, "hi")
    assert effective_language(phone) == "hi"
    # Hindi script in message must not override stored Marathi
    set_user_language(phone, "mr")
    assert effective_language(phone) == "mr"


def test_parse_language_choice():
    assert parse_language_choice("lang_mr") == "mr"
    assert parse_language_choice("marathi") == "mr"
    assert parse_language_choice("tamil") is None
    assert parse_language_choice("nope") is None


def test_language_list_has_five_options():
    sections = language_list_sections()
    assert list_row_count(sections) == 5
    ids = [row["id"] for sec in sections for row in sec["rows"]]
    assert ids == ["lang_en", "lang_hi", "lang_mr", "lang_gu", "lang_bn"]


def test_main_menu_includes_language(tmp_db):
    sections = main_menu_sections("919900000003")
    ids = [row["id"] for row in sections[0]["rows"]]
    assert "cmd_language" in ids
    assert "cmd_remind" in ids
    assert "cmd_care" in ids
    assert "cmd_help" in ids


def test_localized_chat_intro(tmp_db):
    set_user_language("919900000004", "hi")
    intro = t("919900000004", "chat_intro")
    assert "जगह" in intro


def test_localized_breathe_choose(tmp_db):
    set_user_language("919900000005", "bn")
    text = t("919900000005", "breathe_choose")
    assert "প্যাটার্ন" in text


def test_marathi_menu_fully_localized(tmp_db):
    set_user_language("919900000010", "mr")
    sections = main_menu_sections("919900000010")
    titles = [row["title"] for row in sections[0]["rows"]]
    assert "Check-in" not in titles
    assert "Meditate" not in titles
    assert "चेक-इन" in titles
    assert t("919900000010", "menu_label") == "आरोग्य मेनू"


def test_all_locales_have_same_string_keys():
    en_keys = set(STRINGS["en"].keys())
    for code in ("hi", "mr", "gu", "bn"):
        assert set(STRINGS[code].keys()) == en_keys, f"missing keys in {code}"
