#!/usr/bin/env bash
# Build & register ~/Applications/KidsnewsAutofix.app — a tiny
# AppleScript app that runs scripts/drain-autofix-queue.sh when the
# user clicks a `kidsnews-autofix://` URL (the button in the daily
# quality-digest email).
#
# Why this exists: macOS 26 (Tahoe) tightened Shortcuts.app's trust
# gate so unsigned .shortcut files can't be auto-installed. An
# AppleScript app with a registered URL scheme bypasses Shortcuts
# entirely.
#
# Run once on any Mac that wants the email-button workflow:
#
#   ~/myprojects/news-v2/scripts/build-autofix-app.sh
#
# After it finishes, clicking 🛠️ Drain queue now in any digest email
# launches this app, which spawns the drain script.
set -euo pipefail

APP_DIR="$HOME/Applications/KidsnewsAutofix.app"
DRAIN_SCRIPT="$HOME/myprojects/news-v2/scripts/drain-autofix-queue.sh"

if [ ! -f "$DRAIN_SCRIPT" ]; then
    echo "✗ $DRAIN_SCRIPT missing — wrong checkout?" >&2
    exit 1
fi

mkdir -p "$HOME/Applications"
rm -rf "$APP_DIR"

echo "→ Compiling AppleScript app…"
osacompile -o "$APP_DIR" -e '
on open location URL_str
  do shell script "bash $HOME/myprojects/news-v2/scripts/drain-autofix-queue.sh > /dev/null 2>&1 &"
end open location

on run
  do shell script "bash $HOME/myprojects/news-v2/scripts/drain-autofix-queue.sh > /dev/null 2>&1 &"
end run
'

echo "→ Registering URL scheme kidsnews-autofix://…"
PLIST="$APP_DIR/Contents/Info.plist"
plutil -insert CFBundleIdentifier -string "com.daedal.kidsnews-autofix" "$PLIST"
plutil -insert CFBundleURLTypes -json '[
  {
    "CFBundleURLName": "Kidsnews Autofix",
    "CFBundleURLSchemes": ["kidsnews-autofix"]
  }
]' "$PLIST"

echo "→ Re-signing (Info.plist edit invalidated osacompile sig)…"
codesign --force --deep --sign - "$APP_DIR" 2>&1 | grep -v "replacing existing signature" || true

echo "→ Registering with LaunchServices…"
LSREG="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
"$LSREG" -f "$APP_DIR"

echo ""
echo "✓ Built and registered."
echo "  app:        $APP_DIR"
echo "  URL scheme: kidsnews-autofix://"
echo ""
echo "Test with:"
echo "  open kidsnews-autofix://drain"
echo "(should run drain-autofix-queue.sh; macOS notification on completion)"
