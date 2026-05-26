#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

APP="dist/Claude Status.app"

echo "==> Setting up venv…"
if [ ! -d .venv ]; then
    /opt/homebrew/bin/python3.12 -m venv .venv
fi
.venv/bin/pip install -q customtkinter pillow py2app

echo "==> Regenerating icon…"
.venv/bin/python3 generate_icon.py

echo "==> Cleaning previous build…"
rm -rf build dist

echo "==> Building .app bundle…"
.venv/bin/python3 setup.py py2app 2>&1

echo "==> Patching darkdetect for macOS 26+ version-string bug…"
DARKDETECT="$APP/Contents/Resources/lib/python3.12/darkdetect/__init__.py"
if [ -f "$DARKDETECT" ]; then
    python3 - "$DARKDETECT" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path) as f:
    src = f.read()

patched = src.replace(
    "    major = int(sysver.split('.')[0])",
    "    major = int(sysver.split('.')[0]) if sysver and sysver.split('.')[0].isdigit() else 99"
)
with open(path, "w") as f:
    f.write(patched)
print("  darkdetect patched OK")
PYEOF
fi

echo "==> Repairing liblzma…"
# py2app/macholib rewrites this dylib's load commands to repoint its install
# name but leaves a dangling LC_CODE_SIGNATURE, corrupting the Mach-O so it
# can't be (re)signed ("internal error in Code Signing subsystem"). Replace it
# with the intact Homebrew copy (same version) and re-point it cleanly.
LZMA_SRC="/opt/homebrew/opt/xz/lib/liblzma.5.dylib"
LZMA_DST="$APP/Contents/Frameworks/liblzma.5.dylib"
if [ -f "$LZMA_SRC" ] && [ -f "$LZMA_DST" ]; then
    cp -f "$LZMA_SRC" "$LZMA_DST"
    chmod u+w "$LZMA_DST"
    install_name_tool -id @executable_path/../Frameworks/liblzma.5.dylib "$LZMA_DST"
    echo "  liblzma replaced from $LZMA_SRC"
else
    echo "  WARNING: $LZMA_SRC not found (brew install xz?) — skipping liblzma repair"
fi

echo "==> Removing bundled .DS_Store detritus…"
find "$APP" -name '.DS_Store' -delete || true

# Sign in /tmp, NOT in place: ~/Documents is iCloud-synced and its file provider
# keeps re-adding xattrs (com.apple.FinderInfo, com.apple.fileprovider.*) between
# the xattr clear and codesign, which makes codesign fail with "resource fork,
# Finder information, or similar detritus not allowed". /tmp has no such churn.
echo "==> Ad-hoc signing in a non-iCloud staging dir…"
STAGE="$(mktemp -d /tmp/claudestatus.XXXXXX)"
ditto "$APP" "$STAGE/Claude Status.app"
SAPP="$STAGE/Claude Status.app"

xattr -cr "$SAPP"; xattr -c "$SAPP"

# Sign bottom-up (more reliable than --deep for nested dylibs/frameworks).
find "$SAPP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 \
    | xargs -0 -n1 codesign --force --sign - >/dev/null 2>&1
codesign --force --sign - "$SAPP/Contents/Frameworks/Python.framework" >/dev/null 2>&1 || true
codesign --force --sign - "$SAPP/Contents/MacOS/python"        >/dev/null 2>&1 || true
codesign --force --sign - "$SAPP/Contents/MacOS/Claude Status" >/dev/null 2>&1
codesign --force --sign - "$SAPP"
codesign --verify --strict "$SAPP"   # aborts the build if signing didn't settle

echo "==> Placing verified bundle back in dist/…"
rm -rf "$APP"
ditto "$SAPP" "$APP"
rm -rf "$STAGE"

echo ""
echo "==> Done! App is at: $APP (ad-hoc signed, verified)"
echo "    Install it to /Applications (a non-iCloud location, so the signature stays valid):"
echo "      cp -R \"$APP\" /Applications/"
