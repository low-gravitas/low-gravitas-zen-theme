Low Gravitas Zen themes
=======================

This repository contains a collection of themes for different applications. The themes are designed to be reasonably high in contrast and low in blue light. This should make visibility pretty high and reduce eye strain. The original theme was based on Zenburn, but has evolved quite a bit since then.

There are currently themes for:

* Visual Studio Code
* IntelliJ IDEs (tested with RubyMine and IDEA, but should work with all of them)
* iTerm2
* Warp terminal

They are all still pretty lightly tested. iTerm2 and VS Code see the most usage thus far and are the least likely to have issues. IntelliJ is the most complex and one of the newest so is most likely to have questionable choices.

If you want to fork and/or contribute, I'm open to pull requests and reading any filed issues. That said, not a ton of time is spent on these, so no guarantees of a response are made.

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

There are two options to install the IntelliJ themes. The first is to look for the low-gravitas-zen.jar in the releases section of the repository. If you do this, you can skip to step 4.

1. Clone the repository or at least download the `intellij` folder contents.
2. Open the folder in IntelliJ IDEA (other IDEs do not support plugin development and may not work).
3. Go to the "Build" menu and select "Rebuild Project" and then "Prepare Plugin Module 'low-gravitas-zen' For Deployment".
4. Find the `low-gravitas-zen.jar` file in the `out` folder of the project. (Or the download location if you downloaded the jar directly.)
5. Open the IntelliJ IDE you want to install the theme in.
6. Open the settings (Cmd+, on macOS, Ctrl+Alt+S on Windows and Linux).
7. Go to the "Plugins" section.
8. Click the gear icon and select "Install Plugin from Disk...".
9. Find the `low-gravitas-zen.jar` file and select it.
10. Restart the IDE if prompted.

### iTerm2

1. Clone the repository or at least download the `LowGravitasZen.itermcolors` file.
2. Open iTerm2.
3. Open the iTerm2 preferences (Cmd+,).
4. Go to the "Profiles" section.
5. Click the "Colors" tab.
6. Click the "Color Presets" dropdown.
7. Click "Import".
8. Find the `LowGravitasZen.itermcolors` file and select it.

### Warp terminal

1. Clone the repository or at least download the `low-gravitas-zen-theme.yaml` file.
2. Create the Warp themes directory if it doesn't exist. This is usually `~/.warp/themes` on macOS and `${XDG_DATA_HOME:-$HOME/.local/share}/warp-terminal/themes/` Linux.
3. Copy the `low-gravitas-zen-theme.yaml` file to the Warp themes directory.
4. Open Warp.
4. Open the Warp preferences (Cmd+,).
5. Go to the "Appearance" section.
6. Click the "Current Theme" area.
7. Select "Low Gravitas Zen" from the list in the left pane.




