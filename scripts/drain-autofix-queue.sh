#!/usr/bin/env bash
# Drain the autofix queue: process every queued item until empty.
# Invoked by the macOS Shortcut "Drain Kidsnews Queue" (set up once
# per Mac), which is itself triggered by the "Drain now" button in
# the daily quality-digest email.
#
# Each item spawns `claude -p` for ~2 min. Multiple items run
# sequentially. Run this when you're NOT actively using Claude IDE
# — token contention will throttle your IDE for the duration.
# (See docs/bugs/2026-04-29-autofix-token-starvation.md.)
#
# Manual usage from Terminal also works:
#   ~/myprojects/news-v2/scripts/drain-autofix-queue.sh
set -euo pipefail

REPO="${REPO:-$HOME/myprojects/news-v2}"
LOG_DIR="$HOME/Library/Logs/kidsnews-autofix"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date -u +%Y-%m-%d).log"

cd "$REPO"

# shellcheck disable=SC1091
set -a
source "$REPO/.env"
set +a
export SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_KEY:-}" ]; then
    echo "$(date -u +%FT%TZ) FATAL: missing SUPABASE_URL or SUPABASE_SERVICE_KEY" >> "$LOG"
    osascript -e 'display notification "Missing credentials in ~/myprojects/news-v2/.env" with title "Kidsnews autofix"' || true
    exit 1
fi

echo "$(date -u +%FT%TZ) ── manual drain start ──" >> "$LOG"

# Drain everything queued. NO --once flag. autofix_consumer's loop
# pulls items until the queue is empty. Each item invokes claude -p
# under the hood (~1-3 min each).
python3 -m pipeline.autofix_consumer 2>&1 \
    | tee -a "$LOG"

echo "$(date -u +%FT%TZ) ── manual drain done ──" >> "$LOG"

# Native macOS notification when done so the user knows the IDE is
# safe to use again.
osascript -e 'display notification "Autofix drain complete" with title "Kidsnews autofix" sound name "Pop"' || true
