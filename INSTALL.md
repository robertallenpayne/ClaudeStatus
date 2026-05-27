# Claude Status — Installation & Build Guide

## Install the pre-built app

```sh
cp -R "dist/Claude Status.app" /Applications/
```

Then launch it from Spotlight, Finder, or double-click in `/Applications`.

## Launch at login (optional)

Open **System Settings → General → Login Items** and click **+** to add `Claude Status.app`.

## Troubleshooting: "App can't be opened" (Gatekeeper)

macOS will block the app if it isn't signed with an Apple Developer certificate. The build script handles this automatically via ad-hoc signing, but if you copied the app manually or see the error after an update, run:

```sh
codesign --sign - --deep --force "/Applications/Claude Status.app"
xattr -cr "/Applications/Claude Status.app"
killall Dock
```

The `killall Dock` clears the icon cache at the same time — useful if the app icon shows as a blank page.

When you eventually have an Apple Developer account, replace `--sign -` with `--sign "Developer ID Application: Your Name (TEAMID)"` and update the same line in `build.sh`.

## Troubleshooting: Icon shows as blank page

macOS caches app icons aggressively. If the icon looks wrong after install, run:

```sh
killall Dock
```

## Rebuild after code changes

```sh
./build.sh
```

This script:
1. Creates/updates the `.venv` with required packages
2. Regenerates `icon.icns` from `generate_icon.py`
3. Cleans `build/` and `dist/`
4. Runs `py2app` to produce `dist/Claude Status.app`
5. Patches the bundled `darkdetect` module (workaround for macOS 26 returning an empty version string inside py2app bundles)

## How it works

| File | Purpose |
|------|---------|
| `widget.py` | The app — customtkinter GUI, reads `~/.claude/statusline-data.json` |
| `generate_icon.py` | Draws the icon with Pillow and builds `icon.icns` via `iconutil` |
| `setup.py` | py2app configuration (bundle ID, icon, included packages) |
| `build.sh` | One-shot build script |
| `launch.sh` | Legacy launcher — runs the widget directly from the venv without bundling |

## Data source

The widget reads `~/.claude/statusline-data.json`, written by the Claude Code statusline hook. If that file doesn't exist yet, the widget shows "waiting for Claude Code…" and polls every 30 seconds until it appears.

## Notes

- The app has `LSUIElement = True` in its plist, so it doesn't appear in the Dock while running. In **full-card** mode it behaves like a normal window; in **strip** mode it's a borderless, always-on-top HUD that reveals when you push the cursor into the top-right corner of the screen. Quit it from the `⋮` menu.
- The full card's window position (and your chosen mode) is saved to `~/.claude/status-widget.json` and restored on next launch. The strip auto-positions at the top-right corner.
- The API key (if set via the widget's "Set API Key" button) is also stored in `~/.claude/status-widget.json`.
