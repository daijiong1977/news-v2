# Autofix — local Claude Code scheduled task

The news-v2 autofix system is now a **Claude Code Desktop scheduled task** (since 2026-05-04). It replaced a launchd → `claude -p` daemon that had token-starvation issues with the user's interactive Claude Code session.

## What runs where

| | Where | When | Notes |
|---|---|---|---|
| `pipeline.quality_autofix` | GitHub Actions | After daily-pipeline | Detects quality misses, enqueues into `redesign_autofix_queue` |
| `pipeline.autofix_apply` | GitHub Actions | After `quality_autofix` | DeepSeek + og:image regrab for routine fixes; escalates the rest |
| **News-v2-autofix scheduled task** | **User's Mac (Claude Code Desktop)** | **3:03 AM + 10:03 AM EDT daily** | Polls queue for `fix-requested`, dispatches kidsnews-bugfix sub-agent, opens PRs |
| `news.6ray.com/autofix` | Vercel static + JS | On click | Admin UI to review queue + flip rows to `fix-requested` |

## One-time setup (per Mac)

1. **Confirm `.claude/settings.local.json` is committed in the repo** — it pre-approves Bash/Read/Write/Edit/Glob/Grep/Agent so the first scheduled-task fire doesn't stall on a permission prompt.

2. **Register the two scheduled tasks** by running the MCP calls in your interactive Claude Code session — see `docs/autofix-scheduled-task-prompt.md` for the exact `mcp__scheduled-tasks__create_scheduled_task` invocations + the prompt body.

   Two tasks:
   - `news-v2-autofix-3am` — cron `3 3 * * *` (3:03 AM EDT)
   - `news-v2-autofix-10am` — cron `3 10 * * *` (10:03 AM EDT)

3. **Pre-flight test** — Claude Code Desktop sidebar → `news-v2-autofix-3am` → click "Run now". Watch the session in real-time. If anything stalls on permission, expand the allow-list in `.claude/settings.local.json`.

4. **Verify DB columns exist** (one-time SQL — idempotent):
   ```sql
   ALTER TABLE redesign_autofix_queue
     ADD COLUMN IF NOT EXISTS pr_number       INTEGER,
     ADD COLUMN IF NOT EXISTS resolved_at     TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS abandoned_at    TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS last_error      TEXT;
   ```

## Daily operating flow

```
Day N, evening
  daily-pipeline runs → pipeline.quality_autofix detects body_too_short (id 547) → enqueue
  pipeline.autofix_apply tries DeepSeek regen, fails wc check → status='escalated'
  Evening admin checks news.6ray.com/autofix → clicks 🛠️ Fix → status='fix-requested'

Day N+1, 03:03 AM EDT
  Mac (closed lid) doesn't fire — caught up at next launch.

Day N+1, 06:00 AM EDT (user opens Mac)
  Scheduled task catches up → fires immediately
  Picks row 547 → dispatches kidsnews-bugfix sub-agent
  Sub-agent reads issue body, scopes edits to `website/article.jsx`
  Cuts fix branch, makes edits, runs tests, opens PR
  Returns SUCCESS + PR URL → orchestration writes status='resolved'
  Notification: "news-v2 autofix: 1 resolved"

Day N+1, 10:03 AM EDT
  Queue empty → notification "nothing in queue", exits.
```

## Failure modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| Queue stuck at `fix-requested` for >24h | Mac wasn't open at 3 or 10 AM, or Claude Code wasn't logged in | Open Claude Code, click "Run now" on the task |
| First fire after install stalls forever | `.claude/settings.local.json` was missing, permission prompt blocked | Verify file exists; click Approve in Desktop UI |
| Sub-agent times out | Single-session budget exhausted | This shouldn't happen with sub-agent dispatch — check the orchestration session's prompt isn't doing the actual fix work itself |
| Same row fails twice → `abandoned` | Bug is too hard for autofix | Manual fix needed; admin reviews `news.6ray.com/autofix` for `abandoned` rows |
| Task fires but `lastRunAt` unchanged | Cron job got disabled (UI sidebar shows ⏸) | Re-enable in sidebar |

## Manual run (don't wait for cron)

Open Claude Code Desktop → sidebar → `news-v2-autofix-3am` → "Run now". Same prompt, fires immediately.

Or for a one-off test of the prompt without registering the task: paste the prompt body (between `---PROMPT-BEGIN---` and `---PROMPT-END---` in `docs/autofix-scheduled-task-prompt.md`) into a fresh Claude Code session.

## Files

- `.claude/settings.local.json` — permissions
- `docs/autofix-scheduled-task-prompt.md` — the prompt body + setup instructions
- `docs/AUTOFIX-SCHEDULED-TASK.md` — this file
- `docs/bugs/2026-05-04-autofix-scheduled-task-migration.md` — migration record (what we tore down + why)
- `pipeline/quality_autofix.py` — pipeline-side enqueuer
- `pipeline/autofix_apply.py` — pipeline-side routine fixer
- `~/.claude/skills/kidsnews-bugfix/SKILL.md` — the sub-agent's skill (in user-skills repo)

## Background reading

- `~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md` — canonical guide to Claude Code scheduled tasks (single-session budget trap, permissions setup, cron-jitter notes).
