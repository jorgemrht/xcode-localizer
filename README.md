<h1 align="center">Xcode Localizer</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Xcode-26+-147EFB.svg?logo=xcode&logoColor=white" alt="Requires Xcode 26 and later." />
  <img src="https://img.shields.io/badge/swift-6+-8e44ad.svg" alt="Requires Swift 6 and later." />
  <img src="https://img.shields.io/badge/iOS-16+-2980b9.svg" alt="Designed for iOS 16 and later." />
  <img src="https://img.shields.io/badge/Agent%20Skills-compatible-F05138" alt="Agent Skills">
  <a href="https://twitter.com/jorgemrht">
    <img src="https://img.shields.io/badge/Contact-@jorgemrht-95a5a6.svg?style=flat" alt="Twitter: @jorgemrht" />
  </a>
  <img src="https://github.com/jorgemrht/xcode-localizer/actions/workflows/validate-skill.yml/badge.svg" alt="Tests">
</p>

Xcode 26 String Catalog localization for AI coding tools — because agents touch UI when asked for copy. This skill isolates localization work to `Translations/`, enforces consistent keys, generates a typed Swift API, and produces reviewable HTML change reports.

Supports the Agent Skills open format.

## Requirements
Python 3.14+ is required. On macOS, install it with [Homebrew](https://brew.sh):

```bash
brew install python@3.14
```

## Features
* **Scope isolation** — never touches app source, SwiftUI views, or Xcode project files. Only `Translations/`.
* **Consistent keys** — enforces `{screen}_{element}_{meaning}` convention. No arbitrary keys like `btn_1`.
* **Typed Swift API** — generates `AppStrings.swift` with `LocalizedStringResource`, not `NSLocalizedString`.
* **All-language coverage** — new keys require translations for every configured language before writing.
* **Placeholder validation** — catches mismatched `%@` or `%d` between languages.
* **HTML change reports** — timestamped diffs with old/new values side by side. `latest.html` is always current source-of-truth.
* **Persistent config** — languages, elements, and settings saved in `xcode-localizer.config.json`.

## Quick Start
```bash
npx skills add https://github.com/jorgemrht/xcode-localizer --skill xcode-localizer
```

Then ask your agent:
> Use xcode-localizer to add the login button in English and Spanish.

Or clone this repository and drop `xcode-localizer/` into your tool's skills directory.

## Example Prompts
Use xcode-localizer to add the login screen username placeholder.
English: Username  Spanish: Usuario  Italian: Nome utente

Use xcode-localizer to add the onboarding title in English, Spanish, and French.
English: Welcome  Spanish: Bienvenido  French: Bienvenue

Use xcode-localizer to add the settings screen title in English and Spanish.
English: Settings  Spanish: Configuración

Use xcode-localizer to add Italian and French to the project languages.

Use xcode-localizer to delete the login_placeholder_username key.

## Using Local LLMs on macOS

This skill works with any agent that supports the Agent Skills format. On macOS, you can run your LLM entirely on-device — your app strings and translations never leave your machine.

**Why go local?** Privacy (no cloud round-trips), zero API cost, offline support, and faster iteration without rate limits.

**Recommended tools:**
* [Ollama](https://ollama.com) — one-command install, runs models locally via CLI or HTTP.
* [LM Studio](https://lmstudio.ai) — desktop app with an OpenAI-compatible local server.
* [Apple MLX](https://github.com/ml-explore/mlx-lm) — optimized for Apple Silicon.

**Recommended models for translation:**
* [Llama 3](https://ollama.com/library/llama3) — strong general multilingual support.
* [Mistral](https://ollama.com/library/mistral) — fast and accurate, especially for European languages.
* [Qwen 2.5](https://ollama.com/library/qwen2.5) — excellent for CJK and multilingual code.

**Quick start with Ollama:**
```bash
brew install ollama
ollama pull llama3
```

Then point your agent to the local Ollama endpoint and trigger the skill as usual.

## Skill Structure
```text
xcode-localizer/
  SKILL.md                         # Routing logic and output requirements
  agents/
    claude.yaml                    # Claude Code agent config
    copilot.yaml                   # GitHub Copilot agent config
    gemini.yaml                    # Gemini CLI agent config
    openai.yaml                    # OpenAI / Codex agent config
    qwen.yaml                      # Qwen agent config
  references/
    key-convention.md              # Key naming convention and element mapping
    xcode26-xcstrings.md           # Xcode 26 String Catalog format notes
  scripts/
    apply_xcstrings_changes.py     # Core script — writes xcstrings, Swift, reports
tests/
  test_script.py                   # Automated tests
```

## Contributing
Contributions are welcome! This repository follows the [Agent Skills](https://agentskills.io/home) open format, which has specific structural requirements.

We strongly recommend using AI assistance for contributions:

* Use the [skill-creator skill](https://github.com/efremidze/skill-creator) with Claude to ensure proper formatting

This helps maintain the Agent Skills format and ensures your contribution works correctly with AI agents.



All work must be licensed under the MIT license so it can benefit the most people.

Please ensure you abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## About the author
Created by Jorgemrht.

This skill is maintained to reflect the latest Xcode 26 String Catalog best practices and will be updated as the localization ecosystem evolves.

## License
This skill is open-source and available under the MIT License. See [LICENSE](LICENSE) for details.
