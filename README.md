# Xcode Localizer

![Xcode 26](https://img.shields.io/badge/Xcode-26-147EFB?logo=xcode&logoColor=white)
![macOS 26](https://img.shields.io/badge/macOS-26-000000?logo=apple&logoColor=white)
![iOS 16+](https://img.shields.io/badge/iOS-16%2B-000000?logo=apple&logoColor=white)
![Swift 6.0+](https://img.shields.io/badge/Swift-6.0%2B-F05138?logo=swift&logoColor=white)
![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-3776AB?logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-F05138)
![CI](https://github.com/jorgemrht/xcode-localizer/actions/workflows/validate-skill.yml/badge.svg)

An [Agent Skill](https://agentskills.io) that creates and updates Xcode 26 String Catalog localization artifacts — and nothing else. No UI edits, no project file changes, no source modifications.

Works with Claude Code, Codex, Gemini CLI, GitHub Copilot, Qwen, Cursor, and any tool that supports the Agent Skills format.

Find more agent skills for Swift and Apple platform development at [Swift Agent Skills](https://github.com/twostraws/swift-agent-skills).

## Who this is for

- **iOS / macOS developers** who want an agent to manage `Localizable.xcstrings` without touching UI code.
- **Teams adding new languages** who need every new key covered in all configured languages before it lands.
- **Projects migrating from `.strings` / `.stringsdict`** to the Xcode 26 String Catalog format.
- **Privacy-conscious developers** who want translations to stay on-device using a local LLM (see [Using local LLMs on macOS](#using-local-llms-on-macos)).

## Install

```bash
npx skills add https://github.com/jorgemrht/xcode-localizer --skill xcode-localizer
```

No Node? Install it first:

```bash
brew install node
```

## Requirements

- Python `3.14+` is required to run `xcode-localizer/scripts/apply_xcstrings_changes.py`.
- On macOS, install it with Homebrew:

```bash
brew install python@3.14
python3 --version
```

- For tests, use a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest tests/ -v
```

## Usage

### Claude Code

```
/xcode-localizer Add the login screen username placeholder in English and Spanish.
```

### Codex / ChatGPT

```
$xcode-localizer Add the login button. English: Log in. Spanish: Entrar.
```

### Gemini CLI

```
@xcode-localizer Add the settings title in English, Spanish, and French.
```

### GitHub Copilot

```
#xcode-localizer Add the profile screen error message for invalid email.
```

### Natural language (any tool)

```
Use the xcode-localizer skill to add the onboarding screen title in English and German.
```

### Manual install

```bash
cp -R xcode-localizer /path/to/your/agent/skills/xcode-localizer
```

Place the folder where your tool reads skills. For Codex: `$CODEX_HOME/skills/`; for Claude Code: the skills directory in your project or user config; for Cursor, Gemini CLI, and others, follow their official documentation.

## What it covers

| # | Feature | What it prevents |
|---|---------|------------------|
| 1 | Strict `Translations/` scope | Agent editing SwiftUI views or `.xcodeproj` files |
| 2 | Stable `{screen}_{element}_{meaning}` keys | Arbitrary keys like `btn_1` or `screen_login_label` |
| 3 | Xcode 26 String Catalog format | Legacy `.strings`, `.stringsdict`, or `.xcloc` output |
| 4 | Typed `AppStrings.swift` wrapper | `NSLocalizedString` calls scattered across the codebase |
| 5 | All-language coverage on new keys | Partial catalogs with missing translations |
| 6 | Placeholder consistency check | Mismatched `%@` or `%d` between languages |
| 7 | HTML change reports with old/new values | Silent overwrites with no review trail |
| 8 | `historyofchanges.html` day-grouped index | Lost history of what changed and when |
| 9 | `xcode-localizer.config.json` persistence | Settings re-entered on every invocation |
| 10 | Git author attribution | Unknown authorship in change reports |

## What makes this skill different

**Scope isolation.** The skill hard-codes a check before every action: is the request about `Translations/`? If the user asks for localized text, the agent must not open a single Swift, Storyboard, or Xcode project file. This targets the most common agent mistake: touching UI when asked for copy.

**Xcode 26 only.** No compatibility shims for older Xcode versions. The skill generates `sourceLanguage`/`version: "1.1"` String Catalogs and a `LocalizedStringResource`-based Swift API that matches what Xcode 26 generates itself — avoiding duplicate symbol errors.

**Reviewable by humans.** Every localization update produces a timestamped HTML change report showing the previous and new value for every language, side by side. `latest.html` is always the current source-of-truth view.

**Python stdlib only.** The bundled `apply_xcstrings_changes.py` script uses no third-party packages (requires Python 3.14+). Drop it into any CI environment without a `pip install` step.

## Using local LLMs on macOS

This skill works with any tool that supports the Agent Skills format. On macOS, you can run your LLM entirely on-device — your app strings and translations never leave your machine.

### Why go local?

| Benefit | Details |
|---------|---------|
| **Privacy** | Your app strings, keys, and translations stay on your device. No cloud service sees your content. |
| **No API cost** | Zero token usage. Translate as many strings as you need, for free. |
| **Works offline** | No internet connection required once the model is downloaded. |
| **Fast iteration** | No rate limits or latency from cloud round-trips. |

### Recommended local model runners

| Tool | Description |
|------|-------------|
| [Ollama](https://ollama.com) | Open-source LLM runner for macOS. One-command install, runs models locally via CLI or HTTP. Integrates with Cursor, Continue.dev, and other Agent Skills-compatible tools. |
| [LM Studio](https://lmstudio.ai) | Desktop app for downloading and running LLMs locally. Exposes an OpenAI-compatible local server. |
| [Apple MLX](https://github.com/ml-explore/mlx-lm) | Apple's ML framework, optimised for Apple Silicon. Runs models directly on your Mac with `mlx_lm.generate`. |

### Recommended models for translation

These models perform well on multilingual translation tasks:

| Model | Strengths |
|-------|-----------|
| [Llama 3](https://ollama.com/library/llama3) | Meta's open flagship. Strong general multilingual support. |
| [Mistral](https://ollama.com/library/mistral) | Fast, accurate, especially for European languages. |
| [Qwen 2.5](https://ollama.com/library/qwen2.5) | Excellent for CJK (Chinese, Japanese, Korean) and multilingual code. |
| [DeepSeek R1](https://ollama.com/library/deepseek-r1) | Strong reasoning quality, good for nuanced translation. |

### Quick start with Ollama

```bash
# Install Ollama
brew install ollama

# Pull a model optimised for translation
ollama pull llama3

# Point Cursor or Continue.dev at your local Ollama endpoint
# then trigger the skill as usual:
# /xcode-localizer Add the onboarding title in English, Spanish, and French.
```

> **Note:** Any agent that supports the Agent Skills format and can connect to a local OpenAI-compatible endpoint (Ollama, LM Studio) will work with this skill.

## Example session

Request:
```
Use the xcode-localizer skill to add the login screen username placeholder.
English: Username  Spanish: Usuario  Italian: Nome utente
```

The skill creates or updates:

```text
Translations/Localizable.xcstrings         ← adds login_placeholder_username
Translations/AppStrings.swift              ← AppStrings.Login.placeholderUsername
Translations/xcode-localizer.config.json  ← records en, es, it
Translations/reports/latest.html          ← full catalog view
Translations/reports/historyofchanges.html ← day-grouped change index
Translations/reports/13-04-2026-143022-xcode-localizer.html  ← timestamped diff
```

Generated Swift:

```swift
// AppStrings.Login.placeholderUsername
Text(AppStrings.Login.placeholderUsername)
```

Generated catalog entry:

```json
"login_placeholder_username": {
  "comment": "Login username placeholder.",
  "extractionState": "manual",
  "localizations": {
    "en": { "stringUnit": { "state": "translated", "value": "Username" } },
    "es": { "stringUnit": { "state": "translated", "value": "Usuario" } },
    "it": { "stringUnit": { "state": "translated", "value": "Nome utente" } }
  }
}
```

## Generated files

```text
Translations/
├── Localizable.xcstrings
├── AppStrings.swift
├── xcode-localizer.config.json
└── reports/
    ├── latest.html
    ├── historyofchanges.html
    └── <dd-mm-yyyy-HHMMSS>-xcode-localizer.html
```

The skill never creates or modifies anything outside `Translations/`.

## Default configuration

Created automatically on first use:

```json
{
  "defaultLanguage": "en",
  "languages": ["en", "es"],
  "defaultScreen": "common",
  "validElements": [
    "accessibility_hint", "accessibility_label", "alert", "button",
    "context_menu", "empty_state", "error", "label", "link", "message",
    "navigation_title", "picker", "placeholder", "subtitle", "success",
    "tab", "text", "title", "toggle", "toolbar", "warning"
  ],
  "keyPattern": "{screen}_{element}_{meaning}",
  "swiftApiName": "AppStrings"
}
```

To add languages or elements, edit `Translations/xcode-localizer.config.json` directly or ask the skill:

```
Use the xcode-localizer skill to add Italian and French to the project languages.
```

## Running the script directly

```bash
python3 xcode-localizer/scripts/apply_xcstrings_changes.py apply \
  --allow-create-translations \
  --changes-json '{"items":[{"screen":"login","element":"button","meaning":"sign_in","translations":{"en":"Sign in","es":"Iniciar sesión"}}]}'
```

Validate the catalog:

```bash
python3 xcode-localizer/scripts/apply_xcstrings_changes.py validate
```

`validate` also requires Xcode command-line tools (`xcrun`).

## Skill structure

```text
xcode-localizer/
├── SKILL.md
├── agents/
│   ├── claude.yaml
│   ├── copilot.yaml
│   ├── gemini.yaml
│   ├── openai.yaml
│   └── qwen.yaml
├── references/
│   ├── key-convention.md
│   └── xcode26-xcstrings.md
└── scripts/
    └── apply_xcstrings_changes.py
tests/
└── test_script.py
```

## Validation

Validate the skill format:

```bash
npx skills-ref validate xcode-localizer/
```

Run automated tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest tests/ -v
```

CI runs both on every pull request and push to `main`.

## Contributing

I welcome all contributions, whether that's adding new checks, improving existing checks, or editing this README — everyone is welcome!

Keep changes focused on Xcode 26 String Catalog localization:

- Keep `SKILL.md` and reference files consistent.
- Keep your Markdown concise. There is a token cost to using skills, particularly with `SKILL.md`, so please respect the token budgets of users.
- Do not add UI editing, Xcode project integration, or legacy format support.
- Do not add generic localization theory that agents already know; focus on Xcode 26-specific patterns and edge cases.
- Run `npx skills-ref validate xcode-localizer/` and `pytest tests/` before submitting.
- All contributions must be licensed under MIT.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## License

MIT. See [LICENSE](LICENSE) for details.

By [Jorgemrht](https://github.com/jorgemrht). Inspired by the [Swift Agent Skills](https://github.com/twostraws/swift-agent-skills) community.
