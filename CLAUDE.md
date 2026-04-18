# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Low Gravitas is a collection of dark and light color themes designed for high contrast and reduced blue light. The palette originally derived from Zenburn but has diverged significantly. Themes exist for multiple editors and terminals, all generated from a single palette source of truth.

## Repository Structure

- **`palette.toml`** — Single source of truth for all colors. Edit this to change any color.
- **`generate.py`** — Generates all theme files from `palette.toml`. Run `python3 generate.py` to regenerate.
- **`low-gravitas-theme-vscode/`** — VS Code extension (`package.json` + `themes/*.json`). Version in `package.json`.
- **`intellij/`** — IntelliJ plugin (`plugin.xml` + theme JSON + color scheme XML). Version in `plugin.xml`. Built via GitHub Actions into a `.jar` on release.
- **`iTerm2/`** — `.itermcolors` plist files (dark + light).
- **`warp/`** — YAML theme files (dark + light).
- **`ghostty/`** — Ghostty config-format theme files (dark + light).
- **`site/`** — Source templates for CSS and code-sample assets (consumed by the hub repo).
- **`dist/`** — Generated release artifacts (gitignored). Built by `python3 generate.py --artifacts`.

## Theme Generation

All theme files are **generated** — do not edit them directly. Instead:

1. Edit `palette.toml` to change colors
2. Run `python3 generate.py` to regenerate all themes
3. Run `python3 generate.py --check` to verify generated files match expectations

Generator CLI:
```bash
python3 generate.py                     # Generate all themes, both variants
python3 generate.py --variant dark      # Dark only
python3 generate.py --editor vscode     # VS Code only
python3 generate.py --check             # Verify generated files match committed
python3 generate.py --seed-light        # Print light palette candidates
python3 generate.py --artifacts          # Generate release artifacts (CSS, palette.json, code-samples) into dist/
```

## Versioning

All themes share a single version number defined in `palette.toml` `[meta]` section. When bumping, also update:
- `low-gravitas-theme-vscode/package.json` (`version` field)
- `intellij/resources/META-INF/plugin.xml` (`<version>` element)
- `CHANGELOG.md` (root)
- `low-gravitas-theme-vscode/CHANGELOG.md`

Then run `python3 generate.py` to update version headers in generated files.

## Key Conventions

- Color values should maintain the theme's design goals: high contrast, warm tones, minimal blue light in large background areas.
- `palette.toml` is the canonical color source. Never edit generated theme files directly.
- The IntelliJ plugin has version compatibility bounds in `plugin.xml` (`since-build` / `until-build`) that need updating for new IDE releases.
- Validation: `python3 generate.py --check` for structural correctness, plus manual visual inspection.

## Releases

Releases are created as GitHub tags. The GitHub Actions workflow builds the IntelliJ `.jar` plugin, generates release artifacts into `dist/`, and attaches everything to the release. The demo site lives in the hub repo (low-gravitas.github.io) and fetches these artifacts.
