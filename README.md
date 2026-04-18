Low Gravitas themes
===================

A collection of dark and light color themes designed for high contrast and reduced blue light. Visibility should be high and eye strain low.

There are currently themes for:

* Visual Studio Code
* IntelliJ IDEs (tested with RubyMine and IDEA, but should work with all of them)
* Ghostty terminal
* iTerm2
* Warp terminal

All theme files are available on the [releases page](https://github.com/low-gravitas/low-gravitas-theme/releases). Pull requests and issues are welcome.

Installation
------------

### Visual Studio Code

1. Download the `low-gravitas-theme-vscode` folder from this repo (or clone it).
2. Copy it to your VS Code extensions folder: `~/.vscode/extensions` on macOS/Linux, `%USERPROFILE%\.vscode\extensions` on Windows.
3. Restart VS Code if prompted.
4. Open the command palette (Cmd+Shift+P / Ctrl+Shift+P) and search for `Preferences: Color Theme`.
5. Select `Low Gravitas` or `Low Gravitas Light`.

### IntelliJ IDEs

Download `low-gravitas.jar` from the [releases page](https://github.com/low-gravitas/low-gravitas-theme/releases).

1. Open Settings (Cmd+, / Ctrl+Alt+S) > Plugins.
2. Click the gear icon > "Install Plugin from Disk...".
3. Select the `low-gravitas.jar` file.
4. Restart the IDE if prompted.

Supports IntelliJ 2023.1 through 2025.3 (including Islands theme).

### Ghostty

Download `LowGravitas` (or `LowGravitasLight`) from the [releases page](https://github.com/low-gravitas/low-gravitas-theme/releases).

1. Copy it to `~/.config/ghostty/themes/`.
2. Set `theme = LowGravitas` in your Ghostty config (`~/.config/ghostty/config`).

### iTerm2

Download `LowGravitas.itermcolors` (or `LowGravitasLight.itermcolors`) from the [releases page](https://github.com/low-gravitas/low-gravitas-theme/releases).

1. Open iTerm2 preferences (Cmd+,) > Profiles > Colors.
2. Click "Color Presets" > "Import".
3. Select the `.itermcolors` file.

### Warp terminal

Download `low_gravitas_theme.yaml` (or `low_gravitas_light_theme.yaml`) from the [releases page](https://github.com/low-gravitas/low-gravitas-theme/releases).

1. Copy it to `~/.warp/themes` on macOS or `${XDG_DATA_HOME:-$HOME/.local/share}/warp-terminal/themes/` on Linux.
2. Open Warp preferences (Cmd+,) > Appearance > Current Theme.
3. Select "Low Gravitas" from the list.

Integration assets
------------------

Each release also includes assets for integrating the palette into other tools or sites:

- **`palette.json`** — All palette colors as a machine-readable JSON file. Useful for generating themes for editors or tools not listed above.
- **`low-gravitas.css`** — Prebuilt CSS stylesheet with color variables for both dark and light variants. Drop it in to style a web page with the Low Gravitas palette.
- **`code-samples.html`** — Pre-rendered syntax-highlighted code snippets in both variants, used by the [Low Gravitas site](https://low-gravitas.github.io) for previews.
