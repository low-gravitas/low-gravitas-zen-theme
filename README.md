Low Gravitas Zen themes
=======================

A collection of dark color themes designed for high contrast and reduced blue light. Visibility should be high and eye strain low. The original theme was based on Zenburn, but has evolved quite a bit since then.

There are currently themes for:

* Visual Studio Code
* IntelliJ IDEs (tested with RubyMine and IDEA, but should work with all of them)
* Ghostty terminal
* iTerm2
* Warp terminal

If you want to fork and/or contribute, pull requests and issues are welcome.

Installation
------------

### Visual Studio Code

NOTE: The VS Code theme folder is named as it is to make installation a bit easier. The other apps don't need the long name to properly be recognized.

1. Clone the repository or at least download the `low-gravitas-zen-vscode` folder contents.
2. Copy (symlink might work) the `low-gravitas-zen-vscode` folder to your VS Code extensions folder. This is usually `~/.vscode/extensions` on macOS and Linux and `%USERPROFILE%\.vscode\extensions` on Windows.
3. Restart VS Code if prompted.
4. Open the command palette (Cmd+Shift+P on macOS, Ctrl+Shift+P on Windows and Linux) and search for `Preferences: Color Theme`.
5. Select `Low Gravitas Zen` from the list.

### IntelliJ IDEs

Download the `low-gravitas-zen.jar` from the [releases page](https://github.com/low-gravitas/low-gravitas-zen-theme/releases). Then:

1. Open the IntelliJ IDE you want to install the theme in.
2. Open the settings (Cmd+, on macOS, Ctrl+Alt+S on Windows and Linux).
3. Go to the "Plugins" section.
4. Click the gear icon and select "Install Plugin from Disk...".
5. Find the `low-gravitas-zen.jar` file and select it.
6. Restart the IDE if prompted.

Supports IntelliJ 2023.1 through 2025.3 (including Islands theme).

### Ghostty

1. Clone the repository or download the `ghostty/LowGravitasZen` file.
2. Copy it to your Ghostty themes directory: `~/.config/ghostty/themes/`
3. Set `theme = LowGravitasZen` in your Ghostty config (`~/.config/ghostty/config`).

### iTerm2

1. Clone the repository or download the `iTerm2/LowGravitasZen.itermcolors` file.
2. Open iTerm2.
3. Open the iTerm2 preferences (Cmd+,).
4. Go to the "Profiles" section.
5. Click the "Colors" tab.
6. Click the "Color Presets" dropdown.
7. Click "Import".
8. Find the `LowGravitasZen.itermcolors` file and select it.

### Warp terminal

1. Clone the repository or download the `warp/low_gravitas_zen_theme.yaml` file.
2. Create the Warp themes directory if it doesn't exist. This is usually `~/.warp/themes` on macOS and `${XDG_DATA_HOME:-$HOME/.local/share}/warp-terminal/themes/` on Linux.
3. Copy the `low_gravitas_zen_theme.yaml` file to the Warp themes directory.
4. Open Warp.
5. Open the Warp preferences (Cmd+,).
6. Go to the "Appearance" section.
7. Click the "Current Theme" area.
8. Select "Low Gravitas Zen" from the list in the left pane.
