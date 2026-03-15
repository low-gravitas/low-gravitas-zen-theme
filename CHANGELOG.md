# Changelog

All notable changes to the Low Gravitas Zen theme collection will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-03-14

### Added

- Light mode variants for all themes (VS Code, IntelliJ, Ghostty, Warp, iTerm2)
- `palette.toml` as single source of truth for all colors
- `generate.py` to generate all theme files from the palette
- Demo site at `docs/index.html` with palette swatches and code samples
- GitHub Actions workflow for Pages deployment
- `--check` mode to verify generated files match committed versions
- `--seed-light` utility for computing light palette candidates via LCH inversion

### Changed

- All theme files are now generated from `palette.toml` instead of hand-edited
- IntelliJ release JAR now includes light theme files

## [1.1.0] - 2026-03-14

### Added

- Ghostty terminal theme
- VS Code: new color tokens for features added since mid-2024 (tab selected states, activity bar top layout, SCM graph, git blame, ghost text, inline chat/edit, chat panel, sticky scroll, diff editor unchanged regions, multi-diff editor, terminal command guide)
- VS Code: rainbow indent guides and bracket pair coloring
- IntelliJ: Islands theme support for 2025.3+

### Changed

- Unified ANSI terminal palette across all themes (VS Code, iTerm2, Ghostty, Warp) to match
- Unified background color to `#100c00` across all themes
- IntelliJ: console output colors updated from Darcula defaults to match theme palette
- IntelliJ: version compatibility extended through 2025.3 (build 253)
- IntelliJ: plugin version bumped to 1.1.0
- VS Code: alpha transparency on merge, minimap, and inactive selection overlays
- VS Code: visible yellow active tab border

### Fixed

- VS Code: repository URL typo in package.json
- VS Code: `vsce` script typo in package.json

## [1.0.0] - 2024-04-08

- Initial combined theme repository with VS Code, IntelliJ, iTerm2, and Warp themes
