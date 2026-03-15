# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Low Gravitas Zen is a collection of dark color themes designed for high contrast and reduced blue light. The palette originally derived from Zenburn but has diverged significantly. Themes exist for multiple editors and terminals, each in its own directory with platform-specific format.

## Repository Structure

Each directory is an independent theme definition — there is no shared code or dependencies between them:

- **`low-gravitas-zen-vscode/`** — VS Code extension (`package.json` + `themes/*.json`). Version in `package.json`.
- **`intellij/`** — IntelliJ plugin (`plugin.xml` + theme JSON + color scheme XML). Version in `plugin.xml`. Built via GitHub Actions into a `.jar` on release.
- **`iTerm2/`** — Single `.itermcolors` plist file.
- **`warp/`** — Single YAML theme file (version in comment header).
- **`ghostty/`** — Single Ghostty config-format theme file (version in comment header).

## Versioning

All themes share a single version number. When bumping, update:
- `low-gravitas-zen-vscode/package.json` (`version` field)
- `intellij/resources/META-INF/plugin.xml` (`<version>` element)
- `warp/low_gravitas_zen_theme.yaml` (comment header)
- `ghostty/LowGravitasZen` (comment header)
- `CHANGELOG.md` (root)
- `low-gravitas-zen-vscode/CHANGELOG.md`

## Key Conventions

- Color values should maintain the theme's design goals: high contrast, warm tones, minimal blue light in large background areas.
- The VS Code theme is the canonical color source. Terminal themes and IntelliJ console colors should match the VS Code terminal ANSI palette.
- The IntelliJ plugin has version compatibility bounds in `plugin.xml` (`since-build` / `until-build`) that need updating for new IDE releases.
- There is no test suite or linter — validation is manual (install and visually inspect).

## Releases

Releases are created as GitHub tags. The GitHub Actions workflow builds the IntelliJ `.jar` plugin and attaches it to the release as an asset.
