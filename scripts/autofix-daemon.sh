#!/usr/bin/env bash
# Autofix daemon — invoked by launchd every 30 min on the project
# owner's Mac. Drains redesign_autofix_queue by calling
# pipeline.autofix_consumer, which spawns Claude Code per item.
#
# All real work happens in Python; this shell is just a thin loader
# (paths, env, logging) so launchd has something simple to invoke.
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
# Service-key env name in .env vs what our Python expects.
export SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_KEY:-}" ]; then
    echo "$(date -u +%FT%TZ) FATAL: missing SUPABASE_URL or SUPABASE_SERVICE_KEY" >> "$LOG"
    exit 1
fi

echo "$(date -u +%FT%TZ) ── tick start ──" >> "$LOG"

# Drain the queue. autofix_consumer prints JSON; tee it into the log.
python3 -m pipeline.autofix_consumer 2>&1 \
    | tee -a "$LOG" \
    || echo "$(date -u +%FT%TZ) consumer exited non-zero" >> "$LOG"

echo "$(date -u +%FT%TZ) ── tick done ──" >> "$LOG"
