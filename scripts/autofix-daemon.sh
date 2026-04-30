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

# Process exactly ONE item per tick. Reason: each `claude -p` spawn
# competes with the user's interactive Claude IDE session for token
# quota / concurrent slots — running 3 back-to-back at 21:00 once
# locked the user's IDE for ~2 min until cooldown. With 8h ticks +
# --once, the daemon spends ~3 min on Claude per 8h window (≈0.6%
# duty cycle) which won't interfere with interactive sessions.
#
# Tradeoff: a queue of N items takes 8*N hours to fully drain. For
# our workload (a few quality issues per day max) that's still fine.
python3 -m pipeline.autofix_consumer --once 2>&1 \
    | tee -a "$LOG" \
    || echo "$(date -u +%FT%TZ) consumer exited non-zero" >> "$LOG"

echo "$(date -u +%FT%TZ) ── tick done ──" >> "$LOG"
