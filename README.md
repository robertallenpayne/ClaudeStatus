# Claude Status

A tiny always-on-top macOS widget that shows live **Claude Code** and **Anthropic API** status at a glance — model, context-window usage, rate limits, and reset times — in a dark, compact floating window.

It reads the data the Claude Code statusline hook writes to `~/.claude/statusline-data.json` and refreshes every 30 seconds.

## Features

- **Context window** usage with a color-coded bar (green → yellow → red).
- **5-hour** and **7-day** rate-limit usage, plus the next reset time.
- Current **model** and working directory.
- **Anthropic API** key indicator with quick links to set a key and open the billing console.
- **Two layouts** — a full card and a one-line compact strip — toggled with a button (or the `⋮` menu in compact mode). Window position and chosen layout persist between launches.

## Install

### Pre-built app

```sh
cp -R "dist/Claude Status.app" /Applications/
```

Then launch from Spotlight or Finder. See [`INSTALL.md`](INSTALL.md) for login-item setup and Gatekeeper troubleshooting.

> **Note:** install to `/Applications`, not a folder synced by iCloud Drive (e.g. `~/Documents`). iCloud's file provider rewrites extended attributes on the bundle, which invalidates the code signature and can prevent the app from launching.

### Build from source

```sh
./build.sh
```

This creates/updates the `.venv`, regenerates the icon, builds `dist/Claude Status.app` with `py2app`, and ad-hoc signs it (no Apple Developer account required). Requires Python 3.12 and `xz` (`brew install xz`) for the bundled `liblzma`.

### Run without bundling

```sh
./launch.sh
```

Runs the widget directly from the project venv.

## How it works

| File | Purpose |
|------|---------|
| `widget.py` | The app — a `customtkinter` GUI that reads `~/.claude/statusline-data.json` |
| `generate_icon.py` | Draws the icon with Pillow and builds `icon.icns` |
| `setup.py` | `py2app` bundle configuration |
| `build.sh` | One-shot build, icon regeneration, and ad-hoc signing |
| `launch.sh` | Runs the widget from the venv without bundling |

The API key (if set via the widget) and window geometry are stored in `~/.claude/status-widget.json` — outside this repository.

## Requirements

- macOS (Apple Silicon)
- Python 3.12
- `customtkinter`, `pillow`, `py2app` (installed automatically by `build.sh`)
