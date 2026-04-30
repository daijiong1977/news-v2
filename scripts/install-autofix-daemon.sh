#!/usr/bin/env bash
# One-time installer: copies the launchd plist into
# ~/Library/LaunchAgents, expands {{HOME}}, and bootstraps it.
#
# Usage:
#   ~/myprojects/news-v2/scripts/install-autofix-daemon.sh
#
# Uninstall:
#   launchctl bootout gui/$UID/com.daedal.kidsnews-autofix
#   rm ~/Library/LaunchAgents/com.daedal.kidsnews-autofix.plist
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/com.daedal.kidsnews-autofix.plist"
DST="$HOME/Library/LaunchAgents/com.daedal.kidsnews-autofix.plist"
LABEL="com.daedal.kidsnews-autofix"

if [ ! -f "$SCRIPT_DIR/autofix-daemon.sh" ]; then
    echo "✗ $SCRIPT_DIR/autofix-daemon.sh missing — wrong directory?" >&2
    exit 1
fi

# Make daemon script executable.
chmod +x "$SCRIPT_DIR/autofix-daemon.sh"

# Pre-flight: confirm Claude Code is on PATH.
if ! command -v claude >/dev/null 2>&1; then
    echo "✗ \`claude\` CLI not on PATH. Install via: npm i -g @anthropic-ai/claude-code" >&2
    exit 1
fi

# Pre-flight: confirm .env exists with the keys we need.
if [ ! -f "$SCRIPT_DIR/../.env" ]; then
    echo "✗ $SCRIPT_DIR/../.env missing — daemon won't have credentials." >&2
    exit 1
fi
for k in SUPABASE_URL SUPABASE_SERVICE_KEY DEEPSEEK_API_KEY; do
    if ! grep -q "^${k}=" "$SCRIPT_DIR/../.env" 2>/dev/null \
        && ! grep -q "^${k}_ROLE_KEY=" "$SCRIPT_DIR/../.env" 2>/dev/null; then
        echo "⚠️  $k missing from .env — daemon may fail." >&2
    fi
done

# If already loaded, unload first (idempotent reinstall).
if launchctl list | grep -q "$LABEL"; then
    echo "→ Unloading existing $LABEL…"
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
fi

# Materialize {{HOME}} into the plist.
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|{{HOME}}|$HOME|g" "$SRC" > "$DST"
chmod 644 "$DST"

# Bootstrap (modern way; replaces deprecated `load`).
echo "→ Bootstrapping $LABEL…"
launchctl bootstrap "gui/$UID" "$DST"
launchctl enable "gui/$UID/$LABEL"
launchctl kickstart -k "gui/$UID/$LABEL"

echo ""
echo "✓ Installed and started."
echo "  plist:  $DST"
echo "  log:    ~/Library/Logs/kidsnews-autofix/$(date -u +%Y-%m-%d).log"
echo ""
echo "Verify with:"
echo "  launchctl list | grep kidsnews-autofix"
echo "  tail -f ~/Library/Logs/kidsnews-autofix/\$(date -u +%Y-%m-%d).log"
