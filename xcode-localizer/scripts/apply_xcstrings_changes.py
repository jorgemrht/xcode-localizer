#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import json
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
REPORTS_DIR = Path("Translations/reports")

VALID_ELEMENTS = {
    "button",
    "text",
    "title",
    "subtitle",
    "placeholder",
    "error",
    "alert",
    "accessibility_label",
}

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
    r"(%\([A-Za-z_][A-Za-z0-9_]*\)(?:lld|ld|d|f|@|s))|(%(?:lld|ld|d|f|@|s))|(\{\{[A-Za-z_][A-Za-z0-9_]*\}\})"
)


def snake_case(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", ascii_value)
    ascii_value = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value)
    return re.sub(r"_+", "_", ascii_value).strip("_").lower()


def upper_camel(value):
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    if not parts:
        return "_"
    name = "".join(part[:1].upper() + part[1:].lower() for part in parts)
    return "_" + name if name[0].isdigit() else name


def lower_camel(value):
    name = upper_camel(value)
    if name == "_":
        return name
    return name[:1].lower() + name[1:]


def swift_identifier(name):
    return f"`{name}`" if name in SWIFT_KEYWORDS else name


def read_changes(args):
    if not args.changes_json:
        raise SystemExit("Provide --changes-json")
    return json.loads(args.changes_json)


def ensure_translations_directory(allow_create_translations):
    if CATALOG_PATH.parent.exists():
        if not CATALOG_PATH.parent.is_dir():
            raise SystemExit(f"{CATALOG_PATH.parent} exists but is not a directory")
        return
    if not allow_create_translations:
        raise SystemExit(
            "Translations folder does not exist. Where do you want me to create it? Recommended: ./Translations"
        )
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def load_catalog(source_language, allow_create_translations):
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


def derive_key(item):
    if item.get("key"):
        key = snake_case(item["key"])
    else:
        screen = snake_case(item.get("screen", "common") or "common")
        element = snake_case(item.get("element", ""))
        meaning = snake_case(item.get("meaning", ""))
        if not element or not meaning:
            raise SystemExit(f"Missing element or meaning for item: {item}")
        if element not in VALID_ELEMENTS:
            raise SystemExit(f"Invalid element '{element}'. Valid: {', '.join(sorted(VALID_ELEMENTS))}")
        key = f"{screen}_{element}_{meaning}"
    if not re.match(r"^[a-z][a-z0-9_]*$", key):
        raise SystemExit(f"Invalid key '{key}'. Use lowercase snake_case.")
    return key


def placeholders(value):
    return sorted(match.group(0) for match in PLACEHOLDER_RE.finditer(value or ""))


def get_value(entry, language):
    return (
        entry.get("localizations", {})
        .get(language, {})
        .get("stringUnit", {})
        .get("value", "")
    )


def set_value(entry, language, value, state="translated"):
    localization = entry.setdefault("localizations", {}).setdefault(language, {})
    unit = localization.setdefault("stringUnit", {})
    unit["state"] = state
    unit["value"] = value


def apply_changes(changes, allow_create_translations):
    source_language = changes.get("sourceLanguage", "en")
    catalog = load_catalog(source_language, allow_create_translations)
    strings = catalog.setdefault("strings", {})
    changed_keys = []
    events = []
    warnings = []

    for item in changes.get("items", []):
        key = derive_key(item)
        if item.get("delete"):
            if key in strings:
                del strings[key]
                changed_keys.append(key)
                events.append({"status": "deleted", "key": key})
            continue

        translations = item.get("translations", {})
        if not translations:
            raise SystemExit(f"No translations provided for key '{key}'")

        existed = key in strings
        entry = strings.setdefault(key, {})
        entry.setdefault("extractionState", "manual")
        if item.get("comment"):
            entry["comment"] = item["comment"]

        source_value = translations.get(source_language) or get_value(entry, source_language)
        source_placeholders = placeholders(source_value)

        for language, value in translations.items():
            target_placeholders = placeholders(value)
            if source_placeholders and target_placeholders != source_placeholders:
                warning = f"{key}/{language}: placeholders {target_placeholders} differ from source {source_placeholders}"
                warnings.append(warning)
            set_value(entry, language, value, item.get("state", "translated"))

        changed_keys.append(key)
        events.append({"status": "updated" if existed else "new", "key": key})

    catalog["version"] = "1.1"
    catalog["strings"] = dict(sorted(strings.items()))
    write_json(CATALOG_PATH, catalog)
    write_swift_api(catalog)
    report_paths = write_html_report(catalog, events) if events else []
    return sorted(set(changed_keys)), warnings, report_paths


def require_xcrun():
    if not shutil.which("xcrun"):
        raise SystemExit("xcrun is required. This tool targets Xcode 26 String Catalog workflows only.")


def split_key(key):
    for element in sorted(VALID_ELEMENTS, key=len, reverse=True):
        marker = f"_{element}_"
        if marker in key:
            screen, meaning = key.split(marker, 1)
            if screen and meaning:
                return screen, f"{element}_{meaning}"
    return "common", key


def remove_legacy_swift_api():
    if LEGACY_SWIFT_PATH == SWIFT_PATH or not LEGACY_SWIFT_PATH.exists():
        return
    try:
        content = LEGACY_SWIFT_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if "Auto-generated by xcode-localizer" in content[:512]:
        LEGACY_SWIFT_PATH.unlink()


def write_swift_api(catalog):
    remove_legacy_swift_api()
    keys = sorted(catalog.get("strings", {}).keys())
    grouped = {}
    for key in keys:
        screen, name = split_key(key)
        grouped.setdefault(screen, []).append((name, key))

    timestamp = dt.datetime.now().strftime("%b %d, %Y at %H:%M")
    lines = [
        "// Auto-generated by xcode-localizer. Do not edit.",
        f"// Generated on: {timestamp}",
        "",
        "import Foundation",
        "",
        "#if SWIFT_PACKAGE",
        "private let resourceBundle = Foundation.Bundle.module",
        "@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)",
        "private nonisolated let resourceBundleDescription = LocalizedStringResource.BundleDescription.atURL(resourceBundle.bundleURL)",
        "#else",
        "private class ResourceBundleClass {}",
        "@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)",
        "private nonisolated let resourceBundleDescription = LocalizedStringResource.BundleDescription.forClass(ResourceBundleClass.self)",
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
    SWIFT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def catalog_languages(catalog):
    source_language = catalog.get("sourceLanguage", "en")
    languages = {source_language}
    for entry in catalog.get("strings", {}).values():
        languages.update(entry.get("localizations", {}).keys())
    return [source_language] + sorted(language for language in languages if language != source_language)


def render_html_report(catalog, events, generated_at):
    languages = catalog_languages(catalog)
    header_cells = ["status", "key", *languages]
    rows = []
    for event in events:
        key = event["key"]
        entry = catalog.get("strings", {}).get(key, {})
        cells = [
            event["status"],
            key,
            *(get_value(entry, language) if event["status"] != "deleted" else "" for language in languages),
        ]
        rows.append(
            "      <tr>"
            + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells)
            + "</tr>"
        )

    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>Xcode Localizer Report</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #1d1d1f; }",
        "    h1 { font-size: 22px; margin: 0 0 8px; }",
        "    p { margin: 0 0 18px; color: #515154; }",
        "    table { width: 100%; border-collapse: collapse; font-size: 14px; }",
        "    th, td { border: 1px solid #d2d2d7; padding: 8px 10px; text-align: left; vertical-align: top; }",
        "    th { background: #f5f5f7; font-weight: 600; }",
        "    tr:nth-child(even) td { background: #fbfbfd; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Xcode Localizer Report</h1>",
        f"  <p>Generated on {html.escape(generated_at)}</p>",
        "  <table>",
        "    <thead>",
        "      <tr>" + "".join(f"<th>{html.escape(cell)}</th>" for cell in header_cells) + "</tr>",
        "    </thead>",
        "    <tbody>",
        *rows,
        "    </tbody>",
        "  </table>",
        "</body>",
        "</html>",
        "",
    ])


def write_html_report(catalog, events):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    filename = now.strftime("%Y-%m-%d-%H%M%S-l10n.html")
    html_text = render_html_report(catalog, events, generated_at)
    latest = REPORTS_DIR / "latest.html"
    timestamped = REPORTS_DIR / filename
    latest.write_text(html_text, encoding="utf-8")
    timestamped.write_text(html_text, encoding="utf-8")
    return [latest, timestamped]


def validate_catalog():
    require_xcrun()
    commands = [
        ["xcrun", "xcstringstool", "print", str(CATALOG_PATH)],
        ["xcrun", "xcstringstool", "compile", str(CATALOG_PATH), "--output-directory", tempfile.mkdtemp(prefix="xcode-localizer-"), "--dry-run"],
    ]
    for command in commands:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            return result.returncode
    print("xcstringstool validation passed")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Apply Xcode 26 localization changes to Translations only")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--changes-json", required=True)
    apply_parser.add_argument("--allow-create-translations", action="store_true")
    apply_parser.add_argument("--skip-validation", action="store_true")

    subparsers.add_parser("validate")

    args = parser.parse_args()
    if args.command == "apply":
        changed_keys, warnings, report_paths = apply_changes(read_changes(args), args.allow_create_translations)
        if not args.skip_validation:
            code = validate_catalog()
            if code != 0:
                raise SystemExit(code)
        outputs = [CATALOG_PATH.resolve(), SWIFT_PATH.resolve(), *(path.resolve() for path in report_paths)]
        print("Updated localization outputs: " + ", ".join(str(path) for path in outputs))
        print(f"Updated keys: {', '.join(changed_keys) if changed_keys else 'none'}")
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return

    if args.command == "validate":
        raise SystemExit(validate_catalog())


if __name__ == "__main__":
    main()
