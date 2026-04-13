"""Tests for apply_xcstrings_changes.py.

Requires Python 3.14+ and pytest.
Run with: pytest tests/ -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script under test
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.parent / "xcode-localizer" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from apply_xcstrings_changes import (  # noqa: E402
    DEFAULT_SETTINGS,
    apply_changes,
    catalog_languages,
    default_comment_for,
    derive_key,
    get_comment,
    get_value,
    history_groups,
    history_rows,
    item_comments,
    key_parts,
    lower_camel,
    merge_settings,
    placeholders,
    snake_case,
    split_key,
    swift_identifier,
    upper_camel,
    write_swift_api,
    CATALOG_PATH,
    CONFIG_PATH,
    SWIFT_PATH,
    REPORTS_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(**overrides) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s["validElements"] = list(DEFAULT_SETTINGS["validElements"])
    s.update(overrides)
    return s


# ===========================================================================
# Unit tests: string helpers
# ===========================================================================

class TestSnakeCase:
    def test_simple_word(self):
        assert snake_case("Hello") == "hello"

    def test_multi_word(self):
        assert snake_case("Hello World") == "hello_world"

    def test_camel_case(self):
        assert snake_case("helloWorld") == "hello_world"

    def test_already_snake(self):
        assert snake_case("hello_world") == "hello_world"

    def test_accented_chars(self):
        assert snake_case("Ñoño") == "nono"

    def test_numbers(self):
        assert snake_case("screen2") == "screen2"

    def test_leading_trailing_non_alpha(self):
        assert snake_case("__hello__") == "hello"

    def test_special_chars(self):
        assert snake_case("sign-in / register") == "sign_in_register"

    def test_empty_string(self):
        assert snake_case("") == ""


class TestUpperCamel:
    def test_single_word(self):
        assert upper_camel("hello") == "Hello"

    def test_multi_word(self):
        assert upper_camel("hello_world") == "HelloWorld"

    def test_settings_notifications(self):
        assert upper_camel("settings_notifications") == "SettingsNotifications"

    def test_starts_with_digit(self):
        assert upper_camel("2fast") == "_2fast"

    def test_empty(self):
        assert upper_camel("") == "_"


class TestLowerCamel:
    def test_single_word(self):
        assert lower_camel("hello") == "hello"

    def test_multi_word(self):
        assert lower_camel("button_sign_in") == "buttonSignIn"

    def test_single_char_part(self):
        result = lower_camel("a_b_c")
        assert result[0].islower()


class TestSwiftIdentifier:
    def test_normal_name(self):
        assert swift_identifier("buttonSignIn") == "buttonSignIn"

    def test_swift_keyword(self):
        assert swift_identifier("in") == "`in`"
        assert swift_identifier("default") == "`default`"
        assert swift_identifier("class") == "`class`"

    def test_non_keyword_word(self):
        assert swift_identifier("cancel") == "cancel"


# ===========================================================================
# Unit tests: localization key logic
# ===========================================================================

class TestDeriveKey:
    def setup_method(self):
        self.settings = _settings()

    def test_basic_key(self):
        item = {"screen": "login", "element": "button", "meaning": "sign_in"}
        assert derive_key(item, self.settings) == "login_button_sign_in"

    def test_default_screen(self):
        item = {"element": "button", "meaning": "cancel"}
        assert derive_key(item, self.settings) == "common_button_cancel"

    def test_explicit_key_overrides(self):
        item = {"key": "my_custom_key", "element": "button", "meaning": "ignore"}
        assert derive_key(item, self.settings) == "my_custom_key"

    def test_normalises_screen_to_snake_case(self):
        item = {"screen": "My Screen", "element": "title", "meaning": "welcome"}
        key = derive_key(item, self.settings)
        assert key == "my_screen_title_welcome"

    def test_invalid_element_raises(self):
        item = {"screen": "login", "element": "banana", "meaning": "sign_in"}
        with pytest.raises(SystemExit):
            derive_key(item, self.settings)

    def test_missing_element_raises(self):
        item = {"screen": "login", "meaning": "sign_in"}
        with pytest.raises(SystemExit):
            derive_key(item, self.settings)

    def test_missing_meaning_raises(self):
        item = {"screen": "login", "element": "button"}
        with pytest.raises(SystemExit):
            derive_key(item, self.settings)


class TestKeyParts:
    def setup_method(self):
        self.settings = _settings()

    def test_known_element(self):
        screen, element, meaning = key_parts("login_button_sign_in", self.settings)
        assert screen == "login"
        assert element == "button"
        assert meaning == "sign_in"

    def test_long_element(self):
        screen, element, meaning = key_parts(
            "profile_navigation_title_settings", self.settings
        )
        assert element == "navigation_title"

    def test_unknown_element_fallback(self):
        screen, element, meaning = key_parts("some_unknown_key", self.settings)
        assert screen == "common"
        assert element == "text"


class TestSplitKey:
    def setup_method(self):
        self.settings = _settings()

    def test_splits_correctly(self):
        screen, name = split_key("login_button_sign_in", self.settings)
        assert screen == "login"
        assert name == "button_sign_in"


# ===========================================================================
# Unit tests: placeholders
# ===========================================================================

class TestPlaceholders:
    def test_no_placeholder(self):
        assert placeholders("Hello World") == []

    def test_percent_at(self):
        assert placeholders("Hello %@") == ["%@"]

    def test_percent_d(self):
        assert placeholders("Count: %d") == ["%d"]

    def test_multiple_same(self):
        result = placeholders("%@ has %d items")
        assert "%@" in result
        assert "%d" in result

    def test_none_value(self):
        assert placeholders(None) == []

    def test_named_placeholder(self):
        result = placeholders("Hello %(name)@")
        assert "%(name)@" in result

    def test_double_brace(self):
        result = placeholders("Hello {{name}}")
        assert "{{name}}" in result


# ===========================================================================
# Unit tests: settings
# ===========================================================================

class TestMergeSettings:
    def test_defaults_when_empty(self):
        s = merge_settings({})
        assert s["defaultLanguage"] == "en"
        assert "button" in s["validElements"]

    def test_overrides_languages(self):
        s = merge_settings({"languages": ["en", "it", "fr"]})
        assert s["languages"] == ["en", "it", "fr"]

    def test_normalises_valid_elements(self):
        s = merge_settings({"validElements": ["Button", "LABEL"]})
        assert "button" in s["validElements"]
        assert "label" in s["validElements"]

    def test_bad_key_pattern_raises(self):
        with pytest.raises(SystemExit):
            merge_settings({"keyPattern": "{screen}_{meaning}"})

    def test_bad_swift_api_name_raises(self):
        with pytest.raises(SystemExit):
            merge_settings({"swiftApiName": "L10n"})

    def test_migrates_base_languages(self):
        s = merge_settings({"baseLanguages": ["en", "de"]})
        assert s["languages"] == ["en", "de"]
        assert "baseLanguages" not in s


class TestItemComments:
    def test_dict_comments(self):
        item = {"comments": {"en": "A button.", "es": "Un botón."}}
        c = item_comments(item)
        assert c["en"] == "A button."

    def test_string_comments_mapped_to_default(self):
        item = {"comments": "A button."}
        c = item_comments(item)
        assert c["default"] == "A button."

    def test_top_level_comment_fallback(self):
        item = {"comment": "A button."}
        c = item_comments(item)
        assert c["default"] == "A button."


# ===========================================================================
# Integration tests: apply_changes
# ===========================================================================

@pytest.fixture(autouse=True)
def tmp_translations(tmp_path, monkeypatch):
    """Run each test from a fresh temp directory with no Translations/ folder."""
    monkeypatch.chdir(tmp_path)
    # Patch the module-level Path constants to resolve relative to tmp_path
    import apply_xcstrings_changes as mod
    monkeypatch.setattr(mod, "CATALOG_PATH", tmp_path / "Translations" / "Localizable.xcstrings")
    monkeypatch.setattr(mod, "SWIFT_PATH", tmp_path / "Translations" / "AppStrings.swift")
    monkeypatch.setattr(mod, "LEGACY_SWIFT_PATH", tmp_path / "Translations" / "L10n.swift")
    monkeypatch.setattr(mod, "CONFIG_PATH", tmp_path / "Translations" / "xcode-localizer.config.json")
    monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path / "Translations" / "reports")
    monkeypatch.setattr(mod, "LATEST_REPORT_PATH", tmp_path / "Translations" / "reports" / "latest.html")
    monkeypatch.setattr(mod, "HISTORY_REPORT_PATH", tmp_path / "Translations" / "reports" / "historyofchanges.html")
    return tmp_path


def _base_changes(**extra) -> dict:
    return {
        "defaultLanguage": "en",
        "items": [
            {
                "screen": "login",
                "element": "button",
                "meaning": "sign_in",
                "translations": {"en": "Sign in", "es": "Iniciar sesión"},
            }
        ],
        **extra,
    }


class TestApplyChangesNewKey:
    def test_creates_catalog(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        keys, warnings, reports = apply_changes(_base_changes(), True, settings)

        assert "login_button_sign_in" in keys
        catalog = json.loads(mod.CATALOG_PATH.read_text())
        assert "login_button_sign_in" in catalog["strings"]

    def test_creates_swift_api(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        swift = mod.SWIFT_PATH.read_text()
        assert "AppStrings" in swift
        assert "LocalizedStringResource" in swift
        assert "buttonSignIn" in swift
        # Timestamp must NOT be in generated Swift (avoids noisy diffs)
        assert "Generated on:" not in swift

    def test_creates_html_reports(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        _, _, reports = apply_changes(_base_changes(), True, settings)

        assert mod.LATEST_REPORT_PATH.exists()
        assert mod.HISTORY_REPORT_PATH.exists()
        assert mod.HISTORY_REPORT_PATH.name == "historyofchanges.html"
        assert len(reports) == 3  # latest, history, timestamped

    def test_latest_html_contains_key(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        content = mod.LATEST_REPORT_PATH.read_text()
        assert "login_button_sign_in" in content
        assert "Xcode Localizer - Current localizations" in content
        assert "Last time generated:" in content

    def test_change_report_contains_new_status(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        _, _, reports = apply_changes(_base_changes(), True, settings)

        timestamped = [p for p in reports if "latest" not in str(p) and "history" not in str(p)]
        assert len(timestamped) == 1
        content = Path(timestamped[0]).read_text()
        assert "new" in content

    def test_missing_translations_dir_raises_without_flag(self, tmp_translations):
        settings = _settings()
        with pytest.raises(SystemExit):
            apply_changes(_base_changes(), False, settings)

    def test_missing_language_raises(self, tmp_translations):
        settings = _settings(languages=["en", "es", "it"])
        changes = {
            "defaultLanguage": "en",
            "items": [
                {
                    "screen": "login",
                    "element": "button",
                    "meaning": "sign_in",
                    "translations": {"en": "Sign in"},  # missing es and it
                }
            ],
        }
        with pytest.raises(SystemExit):
            apply_changes(changes, True, settings)


class TestApplyChangesUpdateKey:
    def test_update_shows_old_value_in_report(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        updated = {
            "defaultLanguage": "en",
            "items": [
                {
                    "screen": "login",
                    "element": "button",
                    "meaning": "sign_in",
                    "translations": {"en": "Log in", "es": "Entrar"},
                }
            ],
        }
        _, _, reports = apply_changes(updated, True, settings)

        timestamped = [p for p in reports if "latest" not in str(p) and "history" not in str(p)]
        content = Path(timestamped[0]).read_text()
        assert "Sign in" in content  # old value
        assert "Log in" in content   # new value
        assert "updated" in content


class TestApplyChangesDeleteKey:
    def test_delete_removes_key_from_catalog(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        delete_changes = {
            "items": [{"key": "login_button_sign_in", "delete": True}]
        }
        apply_changes(delete_changes, True, settings)

        catalog = json.loads(mod.CATALOG_PATH.read_text())
        assert "login_button_sign_in" not in catalog["strings"]

    def test_delete_writes_deleted_status_in_report(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        delete_changes = {
            "items": [{"key": "login_button_sign_in", "delete": True}]
        }
        _, _, reports = apply_changes(delete_changes, True, settings)
        timestamped = [p for p in reports if "latest" not in str(p) and "history" not in str(p)]
        content = Path(timestamped[0]).read_text()
        assert "deleted" in content


# ===========================================================================
# Integration tests: generated Swift API
# ===========================================================================

class TestWriteSwiftApi:
    def test_groups_by_screen(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        catalog = {
            "sourceLanguage": "en",
            "version": "1.1",
            "strings": {
                "login_button_sign_in": {},
                "login_placeholder_username": {},
                "common_button_cancel": {},
            },
        }
        (tmp_translations / "Translations").mkdir(parents=True, exist_ok=True)
        write_swift_api(catalog, settings)

        swift = mod.SWIFT_PATH.read_text()
        assert "enum Login" in swift
        assert "enum Common" in swift
        assert "buttonSignIn" in swift
        assert "placeholderUsername" in swift
        assert "buttonCancel" in swift

    def test_no_timestamp_in_output(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        catalog = {"sourceLanguage": "en", "version": "1.1", "strings": {}}
        (tmp_translations / "Translations").mkdir(parents=True, exist_ok=True)
        write_swift_api(catalog, settings)
        swift = mod.SWIFT_PATH.read_text()
        assert "Generated on:" not in swift

    def test_availability_annotation(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        catalog = {"sourceLanguage": "en", "version": "1.1", "strings": {}}
        (tmp_translations / "Translations").mkdir(parents=True, exist_ok=True)
        write_swift_api(catalog, settings)
        swift = mod.SWIFT_PATH.read_text()
        assert "@available(macOS 13, iOS 16" in swift

    def test_no_nonisolated_on_global_let(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        catalog = {"sourceLanguage": "en", "version": "1.1", "strings": {}}
        (tmp_translations / "Translations").mkdir(parents=True, exist_ok=True)
        write_swift_api(catalog, settings)
        swift = mod.SWIFT_PATH.read_text()
        assert "nonisolated let resourceBundleDescription" not in swift

    def test_swift_keyword_escaped(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        # "default" is a Swift keyword; the element "button" + meaning "default" → buttonDefault
        # "in" is a keyword; element "button" + meaning "in" → buttonIn → but lower_camel("button_in") = "buttonIn" which is fine
        # Let's test with element=button meaning=default → key = common_button_default → name = button_default → lower_camel = buttonDefault (not a keyword)
        # Test with key whose camelCase IS a keyword: element=tab meaning=in → common_tab_in → name=tab_in → tabIn (not keyword)
        # Hard to trigger via normal keys. Test swift_identifier directly.
        assert swift_identifier("in") == "`in`"
        assert swift_identifier("buttonSignIn") == "buttonSignIn"


# ===========================================================================
# Integration tests: HTML reports
# ===========================================================================

class TestHtmlReports:
    def test_history_groups_empty_when_no_reports(self, tmp_translations):
        import apply_xcstrings_changes as mod
        (tmp_translations / "Translations" / "reports").mkdir(parents=True, exist_ok=True)
        groups = history_groups()
        assert groups == {}

    def test_no_output_outside_translations(self, tmp_translations):
        settings = _settings()
        apply_changes(_base_changes(), True, settings)
        # Verify no files were created outside Translations/
        all_files = list(tmp_translations.rglob("*"))
        outside = [
            f for f in all_files
            if f.is_file()
            and not str(f).startswith(str(tmp_translations / "Translations"))
        ]
        assert outside == [], f"Unexpected files outside Translations/: {outside}"

    def test_latest_html_has_required_buttons(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        apply_changes(_base_changes(), True, settings)
        content = mod.LATEST_REPORT_PATH.read_text()
        assert "Go To Key descriptions" in content
        assert "History of changes" in content
        assert "[hidden] { display: none !important; }" in content

    def test_latest_html_groups_descriptions_by_pattern_screen_and_element(self, tmp_translations):
        import apply_xcstrings_changes as mod
        settings = _settings()
        changes = _base_changes(items=[
            {
                "screen": "login",
                "element": "button",
                "meaning": "sign_in",
                "translations": {"en": "Sign in", "es": "Iniciar sesión"},
                "comment": "Primary login action",
            },
            {
                "screen": "login",
                "element": "placeholder",
                "meaning": "email",
                "translations": {"en": "Email", "es": "Email"},
                "comment": "Email input placeholder",
            },
        ])
        apply_changes(changes, True, settings)

        content = mod.LATEST_REPORT_PATH.read_text()
        assert "Grouped by the `{screen}_{element}_{meaning}` screen and element parts." in content
        assert "Grouped by the `{screen}` part of the `{screen}_{element}_{meaning}` key." in content
        assert "Grouped by the `{element}` part of the `{screen}_{element}_{meaning}` key." in content
        assert content.count("<h3>Key descriptions</h3>") >= 4
        assert content.count("<h2>Key descriptions</h2>") == 1
        all_keys_section = content.split('<section id="view-all" class="view" data-view>', 1)[1].split('<section id="view-pattern"', 1)[0]
        by_pattern_section = content.split('<section id="view-pattern" class="view" data-view hidden>', 1)[1].split('<section id="view-screen"', 1)[0]
        assert '<section id="key-descriptions">' in all_keys_section
        assert '<section id="key-descriptions">' not in by_pattern_section
        assert "login / button" in content
        assert "Primary login action" in content
        assert "login / placeholder" in content
        assert "Email input placeholder" in content

    def test_history_report_uses_date_author_review_table_and_filter(self, tmp_translations, monkeypatch):
        import apply_xcstrings_changes as mod
        monkeypatch.setenv("GIT_AUTHOR_NAME", "Report Author")
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        content = mod.HISTORY_REPORT_PATH.read_text()
        assert '<th>date</th><th>author</th><th class="cell-action"></th>' in content
        assert '<td class="cell-action"><a class="button button-review"' in content
        assert "Filter by date" in content
        assert "Filter by author" in content
        assert 'type="date"' in content
        assert "Last time generated:" in content
        assert "Date:" not in content
        assert "<h2>13-04-2026</h2>" not in content
        assert "No localization text was generated for that date or author." in content
        assert 'class="empty-filter"' in content
        assert "data-filter-table" in content
        assert "data-date-filter" in content
        assert "data-author-filter" in content
        assert "↗ Review" in content
        assert "Report Author" in content

    def test_history_rows_extracts_author_from_change_report(self, tmp_translations):
        import apply_xcstrings_changes as mod
        reports_dir = tmp_translations / "Translations" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = "01-02-2026-030405-xcode-localizer.html"
        (reports_dir / filename).write_text(
            "<table><thead><tr><th>status</th><th>author</th></tr></thead>"
            "<tbody><tr><td>new</td><td>Jane Doe</td></tr></tbody></table>",
            encoding="utf-8",
        )

        rows = history_rows([filename])
        assert rows[0][0] == "01-02-2026 03:04:05"
        assert rows[0][1] == "Jane Doe"
        assert "↗ Review" in rows[0][2]
        assert rows[0][3] == "2026-02-01"

    def test_history_rows_are_most_recent_first(self, tmp_translations):
        import apply_xcstrings_changes as mod
        reports_dir = tmp_translations / "Translations" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filenames = [
            "01-02-2026-030405-xcode-localizer.html",
            "02-02-2026-030405-xcode-localizer.html",
            "02-02-2026-040405-xcode-localizer.html",
        ]
        for filename in filenames:
            (reports_dir / filename).write_text(
                "<table><thead><tr><th>author</th></tr></thead>"
                "<tbody><tr><td>Jane Doe</td></tr></tbody></table>",
                encoding="utf-8",
            )

        rows = history_rows(filenames)
        assert rows[0][0] == "02-02-2026 04:04:05"
        assert rows[1][0] == "02-02-2026 03:04:05"
        assert rows[2][0] == "01-02-2026 03:04:05"

    def test_change_report_has_old_new_columns(self, tmp_translations):
        settings = _settings()
        _, _, reports = apply_changes(_base_changes(), True, settings)
        timestamped = [p for p in reports if "latest" not in str(p) and "history" not in str(p)]
        content = Path(timestamped[0]).read_text()
        assert "en old" in content
        assert "es old" in content

    def test_history_report_no_double_escape_in_data_author(self, tmp_translations, monkeypatch):
        import apply_xcstrings_changes as mod
        monkeypatch.setenv("GIT_AUTHOR_NAME", "Alice & Bob")
        settings = _settings()
        apply_changes(_base_changes(), True, settings)

        content = mod.HISTORY_REPORT_PATH.read_text()
        # data-author must be singly HTML-escaped (& → &amp;), never double-escaped (&amp; → &amp;amp;)
        assert 'data-author="alice &amp; bob"' in content
        assert "&amp;amp;" not in content
