#!/usr/bin/env python3
# Requires Python 3.14+
"""Apply Xcode 26 localization changes to Translations/ only.

Writes Localizable.xcstrings, AppStrings.swift, xcode-localizer.config.json,
and HTML review reports. Never touches app source, UI, or project files.

Usage:
    python3 apply_xcstrings_changes.py apply --allow-create-translations \\
        --changes-json '<json>'
    python3 apply_xcstrings_changes.py validate
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


CATALOG_PATH = Path("Translations/Localizable.xcstrings")
SWIFT_PATH = Path("Translations/AppStrings.swift")
LEGACY_SWIFT_PATH = Path("Translations/L10n.swift")
CONFIG_PATH = Path("Translations/xcode-localizer.config.json")
REPORTS_DIR = Path("Translations/reports")
LATEST_REPORT_PATH = REPORTS_DIR / "latest.html"
HISTORY_REPORT_PATH = REPORTS_DIR / "historyofchanges.html"
CHANGE_REPORT_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})-(\d{6})(?:-\d+)?-xcode-localizer\.html$")

DEFAULT_VALID_ELEMENTS = {
    "accessibility_label",
    "accessibility_hint",
    "alert",
    "button",
    "context_menu",
    "empty_state",
    "error",
    "label",
    "link",
    "message",
    "navigation_title",
    "picker",
    "placeholder",
    "success",
    "subtitle",
    "tab",
    "text",
    "title",
    "toggle",
    "toolbar",
    "warning",
}

DEFAULT_SETTINGS = {
    "defaultLanguage": "en",
    "languages": ["en", "es"],
    "defaultScreen": "common",
    "appVersion": "",
    "appBuild": "",
    "validElements": sorted(DEFAULT_VALID_ELEMENTS),
    "keyPattern": "{screen}_{element}_{meaning}",
    "swiftApiName": "AppStrings",
}
REPORT_APP_VERSION = "Unknown"
REPORT_APP_BUILD = "Unknown"
SOURCE_EXCLUDED_DIRS = {
    ".build",
    ".git",
    ".swiftpm",
    "Build",
    "DerivedData",
    "Pods",
    "Translations",
    "build",
}
LOCALIZATION_API_NAMES = {
    "LocalizedStringResource",
    "String(localized:",
    "NSLocalizedString",
    "AppStrings.",
}
SWIFT_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
APP_STRINGS_RE = re.compile(r"\bAppStrings\.([A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)?\b")
NON_LOCALIZED_PATTERNS = [
    ("text", re.compile(r"\bText\s*\(\s*verbatim\s*:\s*\"((?:\\.|[^\"\\])*)\"")),
    ("text", re.compile(r"\bText\s*\(\s*String\s*\(\s*\"((?:\\.|[^\"\\])*)\"\s*\)\s*\)")),
    ("label", re.compile(r"\.(?:text|title)\s*=\s*\"((?:\\.|[^\"\\])*)\"")),
    ("placeholder", re.compile(r"\.placeholder\s*=\s*\"((?:\\.|[^\"\\])*)\"")),
    ("accessibility_label", re.compile(r"\.accessibilityLabel\s*=\s*\"((?:\\.|[^\"\\])*)\"")),
    ("accessibility_hint", re.compile(r"\.accessibilityHint\s*=\s*\"((?:\\.|[^\"\\])*)\"")),
    ("button", re.compile(r"\bsetTitle\s*\(\s*\"((?:\\.|[^\"\\])*)\"\s*,")),
    ("alert", re.compile(r"\bUIAlertAction\s*\(\s*title\s*:\s*\"((?:\\.|[^\"\\])*)\"")),
    ("alert", re.compile(r"\bUIAlertController\s*\([^)]*\btitle\s*:\s*\"((?:\\.|[^\"\\])*)\"")),
    ("message", re.compile(r"\bNSAttributedString\s*\(\s*string\s*:\s*\"((?:\\.|[^\"\\])*)\"")),
]

SWIFT_KEYWORDS = {
    "associatedtype",
    "class",
    "deinit",
    "enum",
    "extension",
    "fileprivate",
    "func",
    "import",
    "init",
    "inout",
    "internal",
    "let",
    "open",
    "operator",
    "private",
    "precedencegroup",
    "protocol",
    "public",
    "rethrows",
    "static",
    "struct",
    "subscript",
    "typealias",
    "var",
    "break",
    "case",
    "catch",
    "continue",
    "default",
    "defer",
    "do",
    "else",
    "fallthrough",
    "for",
    "guard",
    "if",
    "in",
    "repeat",
    "return",
    "throw",
    "switch",
    "where",
    "while",
}

PLACEHOLDER_RE = re.compile(
    r"%#@[A-Za-z_][A-Za-z0-9_]*@"
    r"|%\([A-Za-z_][A-Za-z0-9_]*\)(?:lld|ld|d|f|@|s)"
    r"|%(?:\d+\$)?[-+ #0']*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|q|z|t|j)?[@a-zA-Z]"
    r"|\{\{[A-Za-z_][A-Za-z0-9_]*\}\}"
)
PLURAL_CATEGORIES = {"zero", "one", "two", "few", "many", "other"}
DEVICE_VARIATIONS = {"iphone", "ipad", "mac", "applewatch", "appletv", "vision", "other"}
VARIATION_TYPES = {"plural": PLURAL_CATEGORIES, "device": DEVICE_VARIATIONS}


def snake_case(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ascii_value)
    ascii_value = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value)
    return re.sub(r"_+", "_", ascii_value).strip("_").lower()


def upper_camel(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    if not parts:
        return "_"
    name = "".join(part[:1].upper() + part[1:].lower() for part in parts)
    return "_" + name if name[0].isdigit() else name


def lower_camel(value: str) -> str:
    name = upper_camel(value)
    if name == "_":
        return name
    return name[:1].lower() + name[1:]


def swift_identifier(name: str) -> str:
    return f"`{name}`" if name in SWIFT_KEYWORDS else name


def read_json_file(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def merge_settings(raw_settings: dict | None) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    settings.update(raw_settings or {})
    if "baseLanguages" in settings and "languages" not in (raw_settings or {}):
        settings["languages"] = settings.pop("baseLanguages")
    if "sourceLanguage" in settings and "defaultLanguage" not in (raw_settings or {}):
        settings["defaultLanguage"] = settings.pop("sourceLanguage")
    if settings["keyPattern"] != DEFAULT_SETTINGS["keyPattern"]:
        raise SystemExit("Only the key pattern {screen}_{element}_{meaning} is supported.")
    if settings["swiftApiName"] != DEFAULT_SETTINGS["swiftApiName"]:
        raise SystemExit("Only AppStrings is supported as the generated Swift API name.")
    settings["validElements"] = sorted(snake_case(element) for element in settings["validElements"])
    if isinstance(settings["languages"], str):
        settings["languages"] = [settings["languages"]]
    settings["languages"] = [str(language) for language in settings["languages"]]
    settings["defaultLanguage"] = str(settings["defaultLanguage"])
    settings["defaultScreen"] = snake_case(settings["defaultScreen"] or DEFAULT_SETTINGS["defaultScreen"])
    settings.pop("baseLanguages", None)
    settings.pop("sourceLanguage", None)
    return settings


def read_settings() -> dict:
    raw_settings: dict = {}
    if CONFIG_PATH.exists():
        raw_settings.update(read_json_file(CONFIG_PATH))
    return merge_settings(raw_settings)


def write_settings(settings: dict) -> None:
    write_json(CONFIG_PATH, settings)


def read_changes(args: argparse.Namespace) -> dict:
    if args.changes_file:
        return read_json_file(args.changes_file)
    if args.changes_json:
        return json.loads(args.changes_json)
    raise SystemExit("Provide --changes-json or --changes-file")


def ensure_translations_directory(allow_create_translations: bool) -> None:
    if CATALOG_PATH.parent.exists():
        if not CATALOG_PATH.parent.is_dir():
            raise SystemExit(f"{CATALOG_PATH.parent} exists but is not a directory")
        return
    if not allow_create_translations:
        raise SystemExit(
            "Translations folder does not exist. Please tell me the path where I should create it."
        )
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(content)
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def load_catalog(source_language: str, allow_create_translations: bool) -> dict:
    ensure_translations_directory(allow_create_translations)
    if not CATALOG_PATH.exists():
        return {"sourceLanguage": source_language, "version": "1.1", "strings": {}}
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        catalog = json.load(handle)
    if not isinstance(catalog, dict):
        raise SystemExit(f"Invalid .xcstrings root: {CATALOG_PATH}")
    catalog.setdefault("sourceLanguage", source_language)
    catalog.setdefault("version", "1.1")
    catalog.setdefault("strings", {})
    return catalog


def derive_key(item: dict, settings: dict) -> str:
    if item.get("key"):
        key = snake_case(item["key"])
    else:
        screen = snake_case(item.get("screen", settings["defaultScreen"]) or settings["defaultScreen"])
        element = snake_case(item.get("element", ""))
        meaning = snake_case(item.get("meaning", ""))
        if not element or not meaning:
            raise SystemExit(f"Missing element or meaning for item: {item}")
        if element not in settings["validElements"]:
            raise SystemExit(f"Invalid element '{element}'. Valid: {', '.join(settings['validElements'])}")
        key = f"{screen}_{element}_{meaning}"
    if not re.match(r"^[a-z][a-z0-9_]*$", key):
        raise SystemExit(f"Invalid key '{key}'. Use lowercase snake_case.")
    return key


def placeholders(value: str | None) -> list[str]:
    return sorted(match.group(0) for match in PLACEHOLDER_RE.finditer(value or ""))


def get_value(entry: dict, language: str) -> str:
    value = (
        entry.get("localizations", {})
        .get(language, {})
        .get("stringUnit", {})
        .get("value", "")
    )
    if value:
        return value
    leaves = localization_leaf_values(entry.get("localizations", {}).get(language, {}))
    return " | ".join(f"{path}: {leaves[path]}" for path in sorted(leaves))


def get_comment(entry: dict, language: str) -> str:
    return (
        entry.get("localizations", {})
        .get(language, {})
        .get("comment", "")
    ) or entry.get("comment", "")


def set_value(entry: dict, language: str, value: str, state: str = "translated", comment: str | None = None) -> None:
    localization = entry.setdefault("localizations", {}).setdefault(language, {})
    if comment:
        localization["comment"] = comment
    unit = localization.setdefault("stringUnit", {})
    unit["state"] = state
    unit["value"] = value


def variation_spec_error(path: str, message: str) -> None:
    raise SystemExit(f"Invalid variation at {path}: {message}")


def validate_variation_spec(spec: object, path: str) -> None:
    if not isinstance(spec, dict):
        variation_spec_error(path, "expected an object")
    unknown = set(spec) - {"value", "plural", "device"}
    if unknown:
        variation_spec_error(path, f"unsupported fields: {', '.join(sorted(unknown))}")
    variation_kinds = [kind for kind in VARIATION_TYPES if kind in spec]
    if len(variation_kinds) > 1:
        variation_spec_error(path, "nest plural and device rules instead of placing both at the same level")
    if "value" in spec and not isinstance(spec["value"], str):
        variation_spec_error(path, "value must be a string")
    if not variation_kinds and "value" not in spec:
        variation_spec_error(path, "provide value, plural, or device")
    for kind in variation_kinds:
        variants = spec[kind]
        if not isinstance(variants, dict) or not variants:
            variation_spec_error(path, f"{kind} must be a non-empty object")
        unknown_variants = set(variants) - VARIATION_TYPES[kind]
        if unknown_variants:
            variation_spec_error(path, f"invalid {kind} variants: {', '.join(sorted(unknown_variants))}")
        if "other" not in variants:
            variation_spec_error(path, f"{kind} requires an other fallback")
        for name, child in variants.items():
            validate_variation_spec(child, f"{path}.{kind}.{name}")


def merge_variation_node(existing: object, spec: dict, state: str) -> dict:
    node = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    if "value" in spec:
        unit = node.setdefault("stringUnit", {})
        unit["state"] = state
        unit["value"] = spec["value"]
    for kind in VARIATION_TYPES:
        if kind not in spec:
            continue
        target_variations = node.setdefault("variations", {})
        target = target_variations.setdefault(kind, {})
        for name, child in spec[kind].items():
            target[name] = merge_variation_node(target.get(name), child, state)
    return node


def localization_leaf_values(node: object, path: str = "root") -> dict[str, str]:
    if not isinstance(node, dict):
        return {}
    leaves = {}
    unit = node.get("stringUnit")
    if isinstance(unit, dict) and isinstance(unit.get("value"), str):
        leaves[path] = unit["value"]
    variations = node.get("variations", {})
    if isinstance(variations, dict):
        for kind, variants in variations.items():
            if not isinstance(variants, dict):
                continue
            for name, child in variants.items():
                leaves.update(localization_leaf_values(child, f"{path}.{kind}.{name}"))
    return leaves


def variation_shape(node: object, path: str = "root") -> set[str]:
    return set(localization_leaf_values(node, path).keys())


def validate_localization_pair(key: str, language: str, source: object, target: object) -> list[str]:
    source_values = localization_leaf_values(source)
    target_values = localization_leaf_values(target)
    issues = []
    if set(source_values) != set(target_values):
        issues.append(
            f"{key}/{language}: variation paths {sorted(target_values)} differ from source {sorted(source_values)}"
        )
    for path in sorted(set(source_values) & set(target_values)):
        source_tokens = placeholders(source_values[path])
        target_tokens = placeholders(target_values[path])
        if source_tokens != target_tokens:
            issues.append(
                f"{key}/{language}/{path}: placeholders {target_tokens} differ from source {source_tokens}"
            )
    return issues


def git_value(command: list[str]) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def report_author() -> str:
    author = os.environ.get("GIT_AUTHOR_NAME", "").strip()
    if author:
        return author
    author = git_value(["git", "config", "user.name"])
    if author:
        return author
    author = git_value(["git", "log", "-1", "--format=%an"])
    if author:
        return author
    return "Unknown"


def report_release_value(settings: dict, setting: str, environment: str) -> str:
    value = os.environ.get(environment, "").strip() or str(settings.get(setting, "")).strip()
    return value or "Unknown"


def key_parts(key: str, settings: dict) -> tuple[str, str, str]:
    for element in sorted(settings["validElements"], key=len, reverse=True):
        marker = f"_{element}_"
        if marker in key:
            screen, meaning = key.split(marker, 1)
            if screen and meaning:
                return screen, element, meaning
    return "common", "text", key


def default_comment_for(key: str, language: str, item: dict, value: str, settings: dict) -> str:
    screen, element, meaning = key_parts(key, settings)
    label = value or meaning.replace("_", " ")
    return f"{screen} {element}: {label}"


def item_comments(item: dict) -> dict:
    comments = item.get("comments", {})
    if isinstance(comments, str):
        return {"default": comments}
    if not isinstance(comments, dict):
        comments = {}
    if item.get("comment") and "default" not in comments:
        comments = dict(comments)
        comments["default"] = item["comment"]
    return comments


def apply_changes(
    changes: dict, allow_create_translations: bool, settings: dict
) -> tuple[list[str], list[str], list[Path]]:
    source_language = changes.get("defaultLanguage", changes.get("sourceLanguage", settings["defaultLanguage"]))
    catalog = load_catalog(source_language, allow_create_translations)
    strings = catalog.setdefault("strings", {})
    changed_keys = []
    events = []
    warnings = []
    author = report_author()

    for item in changes.get("items", []):
        key = derive_key(item, settings)
        if item.get("delete"):
            if key in strings:
                deleted_entry = strings[key]
                deleted_values = {
                    language: get_value(deleted_entry, language)
                    for language in deleted_entry.get("localizations", {}).keys()
                }
                del strings[key]
                changed_keys.append(key)
                events.append({
                    "status": "deleted",
                    "key": key,
                    "oldValues": deleted_values,
                    "values": {},
                    "author": author,
                })
            continue

        translations = item.get("translations", {})
        variation_translations = item.get("variations", {})
        if translations and variation_translations:
            raise SystemExit(f"Use either translations or variations for key '{key}', not both")
        if not translations and not variation_translations:
            raise SystemExit(f"No translations or variations provided for key '{key}'")
        if translations and not isinstance(translations, dict):
            raise SystemExit(f"translations must be an object for key '{key}'")
        if variation_translations and not isinstance(variation_translations, dict):
            raise SystemExit(f"variations must be an object keyed by language for key '{key}'")

        existed = key in strings
        required_languages = set(catalog_languages(catalog, settings))
        if not existed:
            provided_languages = set(translations) if translations else set(variation_translations)
            missing_languages = sorted(language for language in required_languages if language not in provided_languages)
            if missing_languages:
                raise SystemExit(
                    f"Missing translations for key '{key}': {', '.join(missing_languages)}. "
                    "Translate every configured app language before writing a new localization key."
                )

        entry = strings.setdefault(key, {})
        entry.setdefault("extractionState", "manual")
        comments = item_comments(item)
        source_comment = comments.get(source_language, comments.get("default", ""))
        if source_comment:
            entry["comment"] = source_comment

        previous_values = {
            language: get_value(entry, language)
            for language in entry.get("localizations", {}).keys()
        } if existed else {}
        if translations:
            source_value = translations.get(source_language) or get_value(entry, source_language)
            source_placeholders = placeholders(source_value)
            for language, value in translations.items():
                localization = entry.get("localizations", {}).get(language, {})
                if localization.get("variations"):
                    raise SystemExit(
                        f"{key}/{language} already uses variations. Update it with the variations contract to preserve its structure."
                    )
                target_placeholders = placeholders(value)
                if source_placeholders != target_placeholders:
                    raise SystemExit(
                        f"{key}/{language}: placeholders {target_placeholders} differ from source {source_placeholders}"
                    )
                comment = comments.get(language, comments.get("default", ""))
                if not comment:
                    comment = default_comment_for(key, language, item, value, settings)
                if language == source_language and not entry.get("comment"):
                    entry["comment"] = comment
                set_value(entry, language, value, item.get("state", "translated"), comment)
        else:
            for language, spec in variation_translations.items():
                validate_variation_spec(spec, f"{key}/{language}")
            for language, spec in variation_translations.items():
                value = next(iter(localization_leaf_values(merge_variation_node({}, spec, item.get("state", "translated"))).values()), "")
                comment = comments.get(language, comments.get("default", ""))
                if not comment:
                    comment = default_comment_for(key, language, item, value, settings)
                if language == source_language and not entry.get("comment"):
                    entry["comment"] = comment
                localization = entry.setdefault("localizations", {}).setdefault(language, {})
                if comment:
                    localization["comment"] = comment
                entry["localizations"][language] = merge_variation_node(
                    localization, spec, item.get("state", "translated")
                )
                if comment:
                    entry["localizations"][language]["comment"] = comment

            source_localization = entry.get("localizations", {}).get(source_language)
            if not source_localization:
                raise SystemExit(f"{key}: variations require a {source_language} source localization")
            issues = []
            for language, localization in entry.get("localizations", {}).items():
                if language != source_language:
                    issues.extend(validate_localization_pair(key, language, source_localization, localization))
            if issues:
                raise SystemExit("Refusing to write invalid variations:\n" + "\n".join(issues))

        changed_keys.append(key)
        event_languages = set(previous_values.keys()) | set(translations.keys())
        current_values = {
            language: get_value(entry, language)
            for language in sorted(event_languages)
        }
        events.append({
            "status": "updated" if existed else "new",
            "key": key,
            "oldValues": previous_values,
            "values": current_values,
            "author": author,
        })

    catalog["version"] = "1.1"
    catalog["strings"] = dict(sorted(strings.items()))
    settings["languages"] = catalog_languages(catalog, settings)
    issues = catalog_audit_issues(catalog, settings)
    if issues:
        raise SystemExit("Refusing to write a catalog that fails semantic audit:\n" + "\n".join(issues))
    write_json(CATALOG_PATH, catalog)
    write_settings(settings)
    write_swift_api(catalog, settings)
    report_paths = write_html_report(catalog, events, author, settings) if events else []
    return sorted(set(changed_keys)), warnings, report_paths


def require_xcrun() -> None:
    if not shutil.which("xcrun"):
        raise SystemExit("xcrun is required. This tool targets Xcode 26 String Catalog workflows only.")


def split_key(key: str, settings: dict) -> tuple[str, str]:
    screen, element, meaning = key_parts(key, settings)
    return screen, f"{element}_{meaning}"


def remove_legacy_swift_api() -> None:
    if LEGACY_SWIFT_PATH == SWIFT_PATH or not LEGACY_SWIFT_PATH.exists():
        return
    try:
        content = LEGACY_SWIFT_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if "Auto-generated by xcode-localizer" in content[:512]:
        LEGACY_SWIFT_PATH.unlink()


def write_swift_api(catalog: dict, settings: dict) -> None:
    remove_legacy_swift_api()
    keys = sorted(catalog.get("strings", {}).keys())
    grouped: dict[str, list[tuple[str, str]]] = {}
    for key in keys:
        screen, name = split_key(key, settings)
        grouped.setdefault(screen, []).append((name, key))

    lines = [
        "// Auto-generated by xcode-localizer. Do not edit.",
        "",
        "import Foundation",
        "",
        "#if SWIFT_PACKAGE",
        "private let resourceBundle = Foundation.Bundle.module",
        "@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)",
        "private let resourceBundleDescription = LocalizedStringResource.BundleDescription.atURL(resourceBundle.bundleURL)",
        "#else",
        "private class ResourceBundleClass {}",
        "@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)",
        "private let resourceBundleDescription = LocalizedStringResource.BundleDescription.forClass(ResourceBundleClass.self)",
        "#endif",
        "",
        "@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)",
        "public enum AppStrings {",
    ]

    for screen in sorted(grouped.keys()):
        lines.append(f"    public enum {upper_camel(screen)} {{")
        used_names = set()
        for name, key in grouped[screen]:
            swift_name = lower_camel(name)
            original = swift_name
            index = 2
            while swift_name in used_names:
                swift_name = f"{original}{index}"
                index += 1
            used_names.add(swift_name)
            lines.extend([
                f"        public static let {swift_identifier(swift_name)} = LocalizedStringResource(\"{key}\", table: \"Localizable\", bundle: resourceBundleDescription)",
                "",
            ])
        if lines[-1] == "":
            lines.pop()
        lines.append("    }")
        lines.append("")

    if lines[-1] == "":
        lines.pop()
    lines.append("}")
    SWIFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(SWIFT_PATH, "\n".join(lines) + "\n")


def catalog_languages(catalog: dict, settings: dict) -> list[str]:
    source_language = catalog.get("sourceLanguage", "en")
    languages = {source_language, *settings["languages"]}
    for entry in catalog.get("strings", {}).values():
        languages.update(entry.get("localizations", {}).keys())
    return [source_language] + sorted(language for language in languages if language != source_language)


def localization_structure_issues(key: str, language: str, node: object, path: str = "root") -> list[str]:
    prefix = f"{key}/{language}/{path}"
    if not isinstance(node, dict):
        return [f"{prefix}: localization node must be an object"]
    issues = []
    unit = node.get("stringUnit")
    if unit is not None:
        if not isinstance(unit, dict) or not isinstance(unit.get("value"), str):
            issues.append(f"{prefix}: stringUnit requires a string value")
        elif not isinstance(unit.get("state"), str):
            issues.append(f"{prefix}: stringUnit requires a state")
    variations = node.get("variations")
    if variations is not None:
        if not isinstance(variations, dict):
            issues.append(f"{prefix}: variations must be an object")
        else:
            for kind, variants in variations.items():
                if kind not in VARIATION_TYPES:
                    continue
                if not isinstance(variants, dict) or not variants:
                    issues.append(f"{prefix}.{kind}: variations must be a non-empty object")
                    continue
                unknown = set(variants) - VARIATION_TYPES[kind]
                if unknown:
                    issues.append(f"{prefix}.{kind}: unsupported variants {', '.join(sorted(unknown))}")
                if "other" not in variants:
                    issues.append(f"{prefix}.{kind}: missing other fallback")
                for name, child in variants.items():
                    issues.extend(localization_structure_issues(key, language, child, f"{path}.{kind}.{name}"))
    if unit is None and not variations:
        issues.append(f"{prefix}: localization has neither stringUnit nor variations")
    return issues


def catalog_audit_issues(catalog: object, settings: dict) -> list[str]:
    if not isinstance(catalog, dict):
        return ["catalog root must be an object"]
    strings = catalog.get("strings")
    if not isinstance(strings, dict):
        return ["catalog strings must be an object"]
    source_language = catalog.get("sourceLanguage")
    if not isinstance(source_language, str) or not source_language:
        return ["catalog sourceLanguage must be a non-empty string"]

    issues = []
    expected_languages = set(catalog_languages(catalog, settings))
    for key, entry in strings.items():
        if not isinstance(key, str) or not re.match(r"^[a-z][a-z0-9_]*$", key):
            issues.append(f"{key}: key must use lowercase snake_case")
        if not isinstance(entry, dict):
            issues.append(f"{key}: entry must be an object")
            continue
        localizations = entry.get("localizations")
        if not isinstance(localizations, dict):
            issues.append(f"{key}: localizations must be an object")
            continue
        missing_languages = expected_languages - set(localizations)
        if missing_languages:
            issues.append(f"{key}: missing localizations for {', '.join(sorted(missing_languages))}")
        source = localizations.get(source_language)
        if source is None:
            issues.append(f"{key}: missing source localization {source_language}")
            continue
        for language, localization in localizations.items():
            issues.extend(localization_structure_issues(key, language, localization))
        source_values = localization_leaf_values(source)
        if not source_values:
            issues.append(f"{key}/{source_language}: source localization has no string values")
            continue
        for language, localization in localizations.items():
            if language != source_language:
                issues.extend(validate_localization_pair(key, language, source, localization))
    return issues


def audit_catalog() -> int:
    if not CATALOG_PATH.exists():
        print(f"Localization audit failed: missing {CATALOG_PATH}", file=sys.stderr)
        return 1
    try:
        catalog = read_json_file(CATALOG_PATH)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Localization audit failed: {error}", file=sys.stderr)
        return 1
    issues = catalog_audit_issues(catalog, read_settings())
    if issues:
        print("Localization audit failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print("Localization semantic audit passed")
    return 0


def swift_literal_value(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def swift_files(source_root: Path) -> list[Path]:
    if not source_root.exists():
        raise SystemExit(f"Source root does not exist: {source_root}")
    if source_root.is_file():
        return [source_root] if source_root.suffix == ".swift" else []
    files = []
    for root, dirs, filenames in os.walk(source_root):
        dirs[:] = [directory for directory in dirs if directory not in SOURCE_EXCLUDED_DIRS]
        for filename in filenames:
            if filename.endswith(".swift"):
                files.append(Path(root) / filename)
    return sorted(files)


def swift_api_reference_map(catalog: dict, settings: dict) -> dict[str, str]:
    references = {}
    grouped: dict[str, dict[str, str]] = {}
    for key in catalog.get("strings", {}):
        screen, name = split_key(key, settings)
        grouped.setdefault(upper_camel(screen), {})[lower_camel(name)] = key
    for screen, names in grouped.items():
        for property_name, key in names.items():
            references[f"AppStrings.{screen}.{property_name}"] = key
    return references


def used_localization_keys(files: list[Path], catalog: dict, settings: dict) -> set[str]:
    catalog_keys = set(catalog.get("strings", {}))
    api_references = swift_api_reference_map(catalog, settings)
    used = set()
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for reference, key in api_references.items():
            if reference in content:
                used.add(key)
        for line in content.splitlines():
            if not any(api_name in line for api_name in LOCALIZATION_API_NAMES):
                continue
            for match in SWIFT_STRING_RE.finditer(line):
                value = swift_literal_value(match.group(1))
                if value in catalog_keys:
                    used.add(value)
    return used


def visible_text_candidate(value: str, catalog_keys: set[str]) -> bool:
    text = value.strip()
    if not text or text in catalog_keys:
        return False
    if len(text) < 2 or len(text) > 120:
        return False
    if re.fullmatch(r"[A-Za-z0-9_.-]+", text) and ("_" in text or "." in text):
        return False
    if re.search(r"https?://|^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+$", text):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ]", text):
        return False
    return True


def screen_from_path(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"(ViewController|Controller|View|Screen|Scene)$", "", stem)
    return snake_case(stem or "common") or "common"


def proposed_key(path: Path, element: str, text: str, catalog: dict, settings: dict, claimed: set[str]) -> str:
    screen = screen_from_path(path)
    if element not in settings["validElements"]:
        element = "text"
    words = snake_case(text)
    words = "_".join(words.split("_")[:6]) or "copy"
    base = f"{screen}_{element}_{words}"
    key = base
    index = 2
    existing = set(catalog.get("strings", {}))
    while key in existing or key in claimed:
        key = f"{base}_{index}"
        index += 1
    claimed.add(key)
    return key


def non_localized_text_candidates(files: list[Path], catalog: dict, settings: dict) -> list[dict]:
    catalog_keys = set(catalog.get("strings", {}))
    claimed: set[str] = set()
    candidates = []
    seen: set[tuple[Path, int, str]] = set()
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for element, pattern in NON_LOCALIZED_PATTERNS:
                for match in pattern.finditer(line):
                    text = swift_literal_value(match.group(1)).strip()
                    marker = (path, line_number, text)
                    if marker in seen or not visible_text_candidate(text, catalog_keys):
                        continue
                    seen.add(marker)
                    candidates.append({
                        "path": path.resolve(),
                        "line": line_number,
                        "text": text,
                        "proposedKey": proposed_key(path, element, text, catalog, settings, claimed),
                    })
    return candidates


def missing_translation_rows(catalog: dict, settings: dict) -> list[dict]:
    languages = catalog_languages(catalog, settings)
    rows = []
    for key, entry in sorted(catalog.get("strings", {}).items()):
        localizations = entry.get("localizations", {}) if isinstance(entry, dict) else {}
        missing = []
        existing = {}
        for language in languages:
            value = get_value(entry, language) if isinstance(entry, dict) else ""
            state = localizations.get(language, {}).get("stringUnit", {}).get("state", "")
            if not value or state == "needs_review":
                missing.append(language)
            else:
                existing[language] = value
        if missing:
            rows.append({"key": key, "missing": missing, "existing": existing})
    return rows


def print_repository_audit(source_root: Path) -> int:
    settings = read_settings()
    catalog = load_catalog(settings["defaultLanguage"], allow_create_translations=False)
    files = swift_files(source_root)
    missing_rows = missing_translation_rows(catalog, settings)
    non_localized = non_localized_text_candidates(files, catalog, settings)
    used_keys = used_localization_keys(files, catalog, settings)
    unused_keys = sorted(set(catalog.get("strings", {})) - used_keys)
    languages = catalog_languages(catalog, settings)
    default_language = catalog.get("sourceLanguage", settings["defaultLanguage"])

    print("Missing translations")
    if not missing_rows:
        print("- None")
    for row in missing_rows:
        print(f"- Key: {row['key']}")
        print(f"  Missing languages: {', '.join(row['missing'])}")
        print("  Existing translations:")
        for language, value in row["existing"].items():
            print(f"  - {language}: {value}")

    print("\nNon-localized UI text")
    if not non_localized:
        print("- None")
    for item in non_localized:
        print(f"- File: {item['path']}:{item['line']}")
        print(f"  Text: {item['text']}")
        print(f"  Proposed key: {item['proposedKey']}")
        print("  Proposed translations:")
        for language in languages:
            value = item["text"] if language == default_language else "[agent translation required]"
            print(f"  - {language}: {value}")

    print("\nPossibly unused localization keys")
    if not unused_keys:
        print("- None")
    for key in unused_keys:
        print(f"- {key}")

    return 0


def event_languages(catalog: dict, events: list[dict], settings: dict) -> list[str]:
    languages = set(catalog_languages(catalog, settings))
    for event in events:
        languages.update(event.get("values", {}).keys())
        languages.update(event.get("oldValues", {}).keys())
    source_language = catalog.get("sourceLanguage", "en")
    return [source_language] + sorted(language for language in languages if language != source_language)


def page_html(title: str, body: str) -> str:
    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <meta name="xcode-localizer-app-version" content="{html.escape(REPORT_APP_VERSION, quote=True)}">',
        f'  <meta name="xcode-localizer-app-build" content="{html.escape(REPORT_APP_BUILD, quote=True)}">',
        f"  <title>{html.escape(title)}</title>",
        "  <style>",
        "    :root { color-scheme: light; --swift-orange: #f05138; --swift-orange-dark: #d84832; --ink: #1d1d1f; --muted: #5f5f67; --line: #e5e5ea; --surface: #ffffff; --surface-alt: #f5f5f7; --header: #2b2b31; }",
        "    * { box-sizing: border-box; }",
        "    body { margin: 0; color: var(--ink); background: linear-gradient(180deg, #ffffff 0%, #f7f7f9 46%, #ffffff 100%); font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif; font-size: 16px; line-height: 1.5; }",
        "    main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 52px 0 64px; }",
        "    h1 { margin: 0 0 8px; font-size: 38px; line-height: 1.08; letter-spacing: 0; font-weight: 700; }",
        "    h1::before { content: ''; display: block; width: 48px; height: 5px; margin: 0 0 18px; border-radius: 5px; background: var(--swift-orange); }",
        "    h2 { margin: 34px 0 12px; font-size: 22px; line-height: 1.2; letter-spacing: 0; font-weight: 650; }",
        "    h3 { margin: 18px 0 10px; font-size: 16px; line-height: 1.25; font-weight: 650; color: var(--muted); }",
        "    p { margin: 0 0 20px; color: var(--muted); }",
        "    a { color: #0b61a4; text-decoration-thickness: 1px; text-underline-offset: 3px; }",
        "    .actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 4px 0 26px; }",
        "    .actions-left { display: inline-flex; flex-wrap: nowrap; align-items: center; gap: 10px; }",
        "    a.button, button.option { display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 9px 14px; border: 0; border-radius: 6px; background: var(--swift-orange); color: #fff; font: inherit; font-weight: 600; text-decoration: none; box-shadow: 0 10px 24px rgba(240, 81, 56, 0.18); cursor: pointer; }",
        "    a.button:hover, button.option:hover { background: var(--swift-orange-dark); }",
        "    input.filter, select.filter { min-height: 38px; width: min(260px, 100%); padding: 8px 12px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--ink); font: inherit; box-shadow: 0 8px 18px rgba(0, 0, 0, 0.04); }",
        "    .view-nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }",
        "    button.option { min-height: 34px; padding: 7px 12px; background: #ffffff; color: var(--ink); border: 1px solid var(--line); box-shadow: none; }",
        "    button.option[aria-pressed='true'] { background: var(--swift-orange); border-color: var(--swift-orange); color: #fff; box-shadow: 0 10px 24px rgba(240, 81, 56, 0.18); }",
        "    button.option:hover { background: #fff4f1; color: var(--ink); }",
        "    button.option[aria-pressed='true']:hover { background: var(--swift-orange-dark); color: #fff; }",
        "    [hidden] { display: none !important; }",
        "    ul { margin: 0 0 18px; padding-left: 22px; }",
        "    li { margin: 7px 0; }",
        "    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: 0 18px 44px rgba(0, 0, 0, 0.06); }",
        "    table { width: 100%; border-collapse: collapse; font-family: 'SF Mono', ui-monospace, Menlo, monospace; font-size: 13px; min-width: 760px; }",
        "    th, td { border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: middle; font-family: inherit; font-size: inherit; }",
        "    th { background: var(--header); font-weight: 650; color: #fff; position: sticky; top: 0; }",
        "    tr:nth-child(even) td { background: #fbfbfd; }",
        "    tr:last-child td { border-bottom: 0; }",
        "    td.cell-status, td.cell-key { font-weight: 600; color: var(--swift-orange); white-space: nowrap; }",
        "    th.cell-action, td.cell-action { text-align: right; }",
        "    .button-review { min-height: 32px; padding: 6px 11px; box-shadow: none; white-space: nowrap; }",
        "    .empty-filter { margin: 34px 0; padding: 26px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--muted); text-align: center; box-shadow: 0 18px 44px rgba(0, 0, 0, 0.06); }",
        "    .section-note { margin-top: -6px; }",
        "    @media (max-width: 720px) { main { width: min(100% - 24px, 1180px); padding-top: 30px; } h1 { font-size: 30px; } .actions { align-items: stretch; flex-direction: column; } table { font-size: 13px; } th, td { padding: 9px 10px; } }",
        "  </style>",
        "  <script>",
"    function showView(id) {",
"      document.querySelectorAll('[data-view]').forEach(function(view) { view.hidden = view.id !== id; });",
"      document.querySelectorAll('[data-target]').forEach(function(button) { button.setAttribute('aria-pressed', button.dataset.target === id ? 'true' : 'false'); });",
"      var keyDescriptionsButton = document.querySelector('[data-key-descriptions-button]');",
"      if (keyDescriptionsButton) { keyDescriptionsButton.hidden = id !== 'view-all'; }",
"    }",
"    function filterRows() {",
"      var dateValue = (document.querySelector('[data-date-filter]') || {}).value || '';",
"      var authorValue = ((document.querySelector('[data-author-filter]') || {}).value || '').trim().toLowerCase();",
"      var visibleRows = 0;",
"      document.querySelectorAll('[data-filter-row]').forEach(function(row) {",
"        var dateMatches = dateValue === '' || row.dataset.date === dateValue;",
"        var authorMatches = authorValue === '' || row.dataset.author.indexOf(authorValue) !== -1;",
"        row.hidden = !(dateMatches && authorMatches);",
"        if (!row.hidden) { visibleRows += 1; }",
"      });",
"      var empty = document.querySelector('[data-empty-filter-message]');",
"      if (empty) { empty.hidden = visibleRows !== 0 || (dateValue === '' && authorValue === ''); }",
"      document.querySelectorAll('[data-filter-table]').forEach(function(table) { table.hidden = visibleRows === 0 && (dateValue !== '' || authorValue !== ''); });",
"    }",
"    document.addEventListener('DOMContentLoaded', function() {",
"      document.querySelectorAll('[data-target]').forEach(function(button) { button.addEventListener('click', function() { showView(button.dataset.target); }); });",
"      document.querySelectorAll('[data-date-filter]').forEach(function(input) { input.addEventListener('change', filterRows); });",
"      document.querySelectorAll('[data-author-filter]').forEach(function(input) { input.addEventListener('input', filterRows); });",
"      document.querySelectorAll('[data-clear-date]').forEach(function(btn) { btn.addEventListener('click', function() { var dateInput = document.querySelector('[data-date-filter]'); if (dateInput) { dateInput.value = ''; dateInput.dispatchEvent(new Event('change')); } }); });",
"    });",
"  </script>",
        "</head>",
        "<body>",
        "<main>",
        body,
        "</main>",

        "  <footer class=\"site-footer\">",
        "    <div style=\"max-width:1180px; margin: 18px auto 52px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; text-align:center;\">",
        "      Generated by <a href=\"https://github.com/jorgemrht/xcode-localizer\">xcode-localizer</a> — developed by <a href=\"https://github.com/jorgemrht\">jorgemrht</a>",
        "    </div>",
        "  </footer>",
        "</body>",
        "</html>",
        "",
    ])


def render_table(header_cells: list[str], rows: list[list]) -> str:
    def cell_class(header):
        if header == "status":
            return ' class="cell-status"'
        if header == "key":
            return ' class="cell-key"'
        return ""

    table_rows = [
        "      <tr>"
        + "".join(
            f"<td{cell_class(header_cells[index])}>{html.escape(str(cell))}</td>"
            for index, cell in enumerate(row)
        )
        + "</tr>"
        for row in rows
    ]
    return "\n".join([
        "  <div class=\"table-wrap\">",
        "    <table>",
        "      <thead>",
        "        <tr>" + "".join(f"<th{cell_class(cell)}>{html.escape(cell)}</th>" for cell in header_cells) + "</tr>",
        "      </thead>",
        "      <tbody>",
        *table_rows,
        "      </tbody>",
        "    </table>",
        "  </div>",
    ])


def render_change_report(catalog: dict, events: list[dict], generated_at: str, settings: dict) -> str:
    languages = event_languages(catalog, events, settings)
    header_cells = ["status", "key"]
    for language in languages:
        header_cells.extend([f"{language} old", language])
    header_cells.append("author")
    rows = []
    for event in events:
        key = event["key"]
        entry = catalog.get("strings", {}).get(key, {})
        values = event.get("values", {})
        old_values = event.get("oldValues", {})
        row = [event["status"], key]
        for language in languages:
            row.extend([
                old_values.get(language, ""),
                values.get(language, get_value(entry, language)),
            ])
        row.append(event.get("author", ""))
        rows.append(row)

    body = "\n".join([
        "  <h1>Xcode Localizer Report</h1>",
        f"  <p>Generated on {html.escape(generated_at)}</p>",
        '  <div class="actions"><span></span><a class="button" href="historyofchanges.html">History of changes</a></div>',
        render_table(header_cells, rows),
    ])
    return page_html("Xcode Localizer Report", body)


def current_rows(catalog: dict, languages: list[str], author: str) -> list[list]:
    rows = []
    for key, entry in sorted(catalog.get("strings", {}).items()):
        rows.append([
            key,
            *(get_value(entry, language) for language in languages),
            author,
        ])
    return rows


def render_grouped_tables(groups: list[tuple], header_cells: list[str]) -> str:
    sections = []
    for title, rows in groups:
        sections.append(f"    <h2>{html.escape(title)}</h2>")
        sections.append(render_table(header_cells, rows))
    return "\n".join(sections)


def render_grouped_catalog_and_description_tables(
    groups: list[tuple[str, list[list]]],
    description_groups: dict[str, list[list]],
    catalog_header: list[str],
    description_header: list[str],
) -> str:
    sections = []
    for title, rows in groups:
        sections.append(f"    <h2>{html.escape(title)}</h2>")
        sections.append(render_table(catalog_header, rows))
        sections.append("    <h3>Key descriptions</h3>")
        sections.append(render_table(description_header, description_groups.get(title, [])))
    return "\n".join(sections)


def render_current_report(catalog: dict, generated_at: str, author: str, settings: dict) -> str:
    languages = catalog_languages(catalog, settings)
    header_cells = ["key", *languages, "author"]
    rows = current_rows(catalog, languages, author)
    by_pattern = {}
    by_screen = {}
    by_element = {}
    descriptions_by_pattern = {}
    descriptions_by_screen = {}
    descriptions_by_element = {}
    description_rows = []
    for key, entry in sorted(catalog.get("strings", {}).items()):
        screen, element, _meaning = key_parts(key, settings)
        pattern_group = f"{screen} / {element}"
        catalog_row = [
            key,
            *(get_value(entry, language) for language in languages),
            author,
        ]
        description_row = [
            key,
            *(get_comment(entry, language) for language in languages),
            author,
        ]
        by_pattern.setdefault(pattern_group, []).append(catalog_row)
        by_screen.setdefault(screen, []).append(catalog_row)
        by_element.setdefault(element, []).append(catalog_row)
        descriptions_by_pattern.setdefault(pattern_group, []).append(description_row)
        descriptions_by_screen.setdefault(screen, []).append(description_row)
        descriptions_by_element.setdefault(element, []).append(description_row)
        description_rows.append(description_row)

    def sorted_groups(groups):
        return [(title, groups[title]) for title in sorted(groups.keys())]

    description_header = ["key", *(f"{language} description" for language in languages), "author"]
    body = "\n".join([
        "  <h1>Xcode Localizer - Current localizations</h1>",
        f"  <p>Last time generated: {html.escape(generated_at)}</p>",
        '  <div class="actions"><div class="actions-left"><a class="button" href="#key-descriptions" data-key-descriptions-button>Go To Key descriptions</a></div><a class="button" href="historyofchanges.html">History of changes</a></div>',
        '  <div class="view-nav" aria-label="Report views">',
        '    <button class="option" type="button" data-target="view-all" aria-pressed="true">All keys</button>',
        '    <button class="option" type="button" data-target="view-pattern" aria-pressed="false">By key pattern</button>',
        '    <button class="option" type="button" data-target="view-screen" aria-pressed="false">By screen</button>',
        '    <button class="option" type="button" data-target="view-element" aria-pressed="false">By element</button>',
        "  </div>",
        '  <section id="view-all" class="view" data-view>',
        "    <h2>All keys</h2>",
        '    <p class="section-note">Alphabetically ordered by key.</p>',
        render_table(header_cells, rows),
        '    <section id="key-descriptions">',
        "      <h2>Key descriptions</h2>",
        render_table(description_header, description_rows),
        "    </section>",
        "  </section>",
        '  <section id="view-pattern" class="view" data-view hidden>',
        "    <h2>By key pattern</h2>",
        '    <p class="section-note">Grouped by the `{screen}_{element}_{meaning}` screen and element parts.</p>',
        render_grouped_catalog_and_description_tables(sorted_groups(by_pattern), descriptions_by_pattern, header_cells, description_header),
        "  </section>",
        '  <section id="view-screen" class="view" data-view hidden>',
        "    <h2>By screen</h2>",
        '    <p class="section-note">Grouped by the `{screen}` part of the `{screen}_{element}_{meaning}` key.</p>',
        render_grouped_catalog_and_description_tables(sorted_groups(by_screen), descriptions_by_screen, header_cells, description_header),
        "  </section>",
        '  <section id="view-element" class="view" data-view hidden>',
        "    <h2>By element</h2>",
        '    <p class="section-note">Grouped by the `{element}` part of the `{screen}_{element}_{meaning}` key.</p>',
        render_grouped_catalog_and_description_tables(sorted_groups(by_element), descriptions_by_element, header_cells, description_header),
        "  </section>",
    ])
    return page_html("Xcode Localizer - Current localizations", body)


def history_groups() -> dict[str, list[str]]:
    groups = {}
    if not REPORTS_DIR.exists():
        return groups
    for path in sorted(REPORTS_DIR.glob("*-xcode-localizer.html")):
        match = CHANGE_REPORT_RE.match(path.name)
        if not match:
            continue
        day, month, year, _time = match.groups()
        groups.setdefault(f"{day}-{month}-{year}", []).append(path.name)
    dated_groups = []
    for label, filenames in groups.items():
        day, month, year = (int(part) for part in label.split("-"))
        dated_groups.append(((year, month, day), label, sorted(filenames)))
    return {
        label: filenames
        for _date, label, filenames in sorted(dated_groups, reverse=True)
    }


def report_author_from_html(filename: str) -> str:
    path = REPORTS_DIR / filename
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "Unknown"
    row_match = re.search(r"<th>author</th>.*?<tbody>.*?<tr>(.*?)</tr>", content, re.S)
    if not row_match:
        return "Unknown"
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row_match.group(1), re.S)
    if not cells:
        return "Unknown"
    author = html.unescape(re.sub(r"<[^>]+>", "", cells[-1])).strip()
    return author or "Unknown"


def report_release_from_html(filename: str) -> tuple[str, str]:
    path = REPORTS_DIR / filename
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "Unknown", "Unknown"

    def metadata(name: str) -> str:
        match = re.search(rf'<meta name="{name}" content="([^"]*)">', content)
        return html.unescape(match.group(1)).strip() if match else "Unknown"

    return metadata("xcode-localizer-app-version"), metadata("xcode-localizer-app-build")


def filename_sort_key(filename: str) -> tuple[int, int, int, str]:
    match = CHANGE_REPORT_RE.match(filename)
    if not match:
        return (0, 0, 0, filename)
    day, month, year, timestamp = match.groups()
    return (int(year), int(month), int(day), timestamp)


def display_datetime_from_filename(filename: str) -> tuple[str, str]:
    match = CHANGE_REPORT_RE.match(filename)
    if not match:
        label = filename.removesuffix(".html")
        return label, ""
    day, month, year, timestamp = match.groups()
    time = f"{timestamp[0:2]}:{timestamp[2:4]}:{timestamp[4:6]}"
    return f"{day}-{month}-{year} {time}", f"{year}-{month}-{day}"


def history_rows(filenames: list[str]) -> list[list[str]]:
    rows = []
    for filename in sorted(filenames, key=filename_sort_key, reverse=True):
        label = filename.removesuffix(".html")
        escaped_label = html.escape(label)
        display_date, iso_date = display_datetime_from_filename(filename)
        version, build = report_release_from_html(filename)
        rows.append([
            html.escape(display_date),
            html.escape(version),
            html.escape(build),
            html.escape(report_author_from_html(filename)),
            f'<a class="button button-review" href="{html.escape(filename)}" aria-label="Review {escaped_label}">↗ Review</a>',
            iso_date,
        ])
    return rows


def render_html_table(header_cells: list[str], rows: list[list[str]]) -> str:
    def cell_class(index: int) -> str:
        return ' class="cell-action"' if index == len(header_cells) - 1 else ""

    table_rows = [
        f'      <tr data-filter-row data-date="{html.escape(row[-1])}" data-author="{row[3].lower()}">'
        + "".join(f"<td{cell_class(index)}>{cell}</td>" for index, cell in enumerate(row[:len(header_cells)]))
        + "</tr>"
        for row in rows
    ]
    return "\n".join([
        "  <div class=\"table-wrap\" data-filter-table>",
        "    <table>",
        "      <thead>",
        "        <tr>" + "".join(f"<th{cell_class(index)}>{html.escape(cell)}</th>" for index, cell in enumerate(header_cells)) + "</tr>",
        "      </thead>",
        "      <tbody>",
        *table_rows,
        "      </tbody>",
        "    </table>",
        "  </div>",
    ])


def render_history_report(generated_at: str) -> str:
    groups = history_groups()
    date_options = "".join(
        f'<option value="{year}-{month}-{day}">{day}-{month}-{year}</option>'
        for day, month, year in (label.split("-") for label in groups.keys())
    )
    all_filenames = [filename for filenames in groups.values() for filename in filenames]
    sections = [
        "  <h1>History of changes</h1>",
        f"  <p>Last time generated: {html.escape(generated_at)}</p>",
        f'  <div class="actions"><div class="actions-left"><input class="filter" type="date" aria-label="Filter by date" data-date-filter list="history-dates"><button class="option" type="button" data-clear-date aria-label="Clear date">✕</button><datalist id="history-dates">{date_options}</datalist><input class="filter" type="search" placeholder="Filter by author" aria-label="Filter by author" data-author-filter></div><a class="button" href="latest.html">Current localizations</a></div>',
    ]
    if not groups:
        sections.append("  <p>No change reports yet.</p>")
    else:
        sections.append('  <p class="empty-filter" data-empty-filter-message hidden>No localization text was generated for that date or author.</p>')
        sections.append(render_html_table(["date", "version", "build", "author", ""], history_rows(all_filenames)))
    return page_html("History of changes", "\n".join(sections))


def unique_change_report_path(now: dt.datetime) -> Path:
    base = now.strftime("%d-%m-%Y-%H%M%S")
    path = REPORTS_DIR / f"{base}-xcode-localizer.html"
    index = 2
    while path.exists():
        path = REPORTS_DIR / f"{base}-{index}-xcode-localizer.html"
        index += 1
    return path


def write_html_report(catalog: dict, events: list[dict], author: str, settings: dict) -> list[Path]:
    global REPORT_APP_VERSION, REPORT_APP_BUILD
    REPORT_APP_VERSION = report_release_value(settings, "appVersion", "MARKETING_VERSION")
    REPORT_APP_BUILD = report_release_value(settings, "appBuild", "CURRENT_PROJECT_VERSION")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()
    generated_at = now.strftime("%d-%m-%Y %H:%M:%S")
    timestamped = unique_change_report_path(now)
    atomic_write_text(timestamped, render_change_report(catalog, events, generated_at, settings))
    atomic_write_text(LATEST_REPORT_PATH, render_current_report(catalog, generated_at, author, settings))
    atomic_write_text(HISTORY_REPORT_PATH, render_history_report(generated_at))
    return [LATEST_REPORT_PATH, HISTORY_REPORT_PATH, timestamped]


def validate_catalog() -> int:
    require_xcrun()
    commands = [
        ["xcrun", "xcstringstool", "print", str(CATALOG_PATH)],
    ]
    with tempfile.TemporaryDirectory(prefix="xcode-localizer-") as tmpdir:
        commands.append(
            ["xcrun", "xcstringstool", "compile", str(CATALOG_PATH), "--output-directory", tmpdir, "--dry-run"]
        )
        for command in commands:
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                sys.stderr.write(result.stderr)
                return result.returncode
    print("xcstringstool validation passed")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Xcode 26 localization changes to Translations only")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--changes-json")
    apply_parser.add_argument("--changes-file")
    apply_parser.add_argument("--allow-create-translations", action="store_true")
    apply_parser.add_argument("--skip-validation", action="store_true")

    subparsers.add_parser("validate")
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--skip-xcode-validation", action="store_true")
    repository_audit_parser = subparsers.add_parser("repository-audit")
    repository_audit_parser.add_argument("--source-root", default=".")

    args = parser.parse_args()
    if args.command == "apply":
        changed_keys, warnings, report_paths = apply_changes(read_changes(args), args.allow_create_translations, read_settings())
        if not args.skip_validation:
            code = validate_catalog()
            if code != 0:
                raise SystemExit(code)
        outputs = [CATALOG_PATH.resolve(), SWIFT_PATH.resolve(), CONFIG_PATH.resolve(), *(path.resolve() for path in report_paths)]
        print("Updated localization outputs: " + ", ".join(str(path) for path in outputs))
        print(f"Updated keys: {', '.join(changed_keys) if changed_keys else 'none'}")
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return

    if args.command == "validate":
        raise SystemExit(validate_catalog())

    if args.command == "audit":
        semantic_code = audit_catalog()
        xcode_code = 0 if args.skip_xcode_validation else validate_catalog()
        raise SystemExit(1 if semantic_code or xcode_code else 0)

    if args.command == "repository-audit":
        raise SystemExit(print_repository_audit(Path(args.source_root)))


if __name__ == "__main__":
    main()
