---
description: "Release a new version of the Zen theme — regenerate themes, bump versions, update changelogs, tag, verify, and update the hub"
---

# Release Process for Low Gravitas Zen Theme

Ask the user for the new version number (e.g. "1.4.0") and a summary of what changed. Store these as $VERSION and $CHANGES for use throughout.

## Step 1: Regenerate themes and verify consistency

Run the generator to ensure all themes reflect the current palette:

```
python3 generate.py
```

Then validate that generated files match:

```
python3 generate.py --check
```

If `--check` fails, stop and report the inconsistency before proceeding.

## Step 2: Generate release artifacts

```
python3 generate.py --artifacts
```

Verify the `dist/` directory contains these three files:
- `dist/low-gravitas-zen.css`
- `dist/palette.json`
- `dist/code-samples.html`

List the directory contents to confirm. If any are missing, stop and investigate.

## Step 3: Bump the version in ALL locations

Update the version string in each of these files:

1. **`palette.toml`** — in the `[meta]` section, update `version = "$VERSION"`
2. **`low-gravitas-zen-vscode/package.json`** — update the `"version"` field to `"$VERSION"`
3. **`intellij/resources/META-INF/plugin.xml`** — update the `<version>` element to `<version>$VERSION</version>`

After updating all three, re-run the generator so version headers in generated files are updated:

```
python3 generate.py
```

## Step 4: Update changelogs

Add a new section at the top of both changelog files, following the Keep a Changelog format. Use the date from today and the changes the user described.

**Root `CHANGELOG.md`** — add a section like:

```
## [$VERSION] - YYYY-MM-DD

### Changed
- (description of changes)
```

**`low-gravitas-zen-vscode/CHANGELOG.md`** — add the same section, tailored to VS Code if needed.

Use Added/Changed/Fixed/Removed subsections as appropriate for the changes.

## Step 5: Final validation

Run the check one more time to confirm everything is consistent after the version bump:

```
python3 generate.py --check
```

If this fails, fix any issues before proceeding.

## Step 6: Commit

Stage all changed files and commit with the message `v$VERSION`. Do not add a Co-Authored-By trailer.

```
git -C . add -A
git -C . commit -m "v$VERSION"
```

## Step 7: Push main

```
git -C . push origin main
```

## Step 8: Tag and push the tag

Create the release tag and push it. This triggers the release workflow in `.github/workflows/release.yml`.

```
git -C . tag v$VERSION
git -C . push origin v$VERSION
```

## Step 9: Verify the release

Wait for the GitHub Actions workflow to complete. Check its status:

```
gh run list --limit 1
```

If the run is still in progress, wait and re-check until it completes. Once finished, verify the release assets:

```
gh release view v$VERSION --json assets -q '.assets[].name'
```

Confirm these assets are present:
- `low-gravitas-zen.css`
- `palette.json`
- `code-samples.html`
- `low-gravitas-zen.jar`
- Ghostty, iTerm2, and Warp theme files

Report any missing assets to the user.

## Step 10: Bump the hub

Remind the user to update the hub repo with this command:

```
cd /Users/mike/Code/lowgravitas/low-gravitas.github.io && node scripts/bump-upstream.mjs --zen=v$VERSION
```

Then commit and push the updated `artifacts.json` and `artifacts.lock.json` in that repo.
