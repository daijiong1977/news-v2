# 2026-05-04 — autofix-scheduled-task-migration

**Severity:** medium (architecture migration; no user-facing breakage during transition)
**Area:** infra (autofix daemon)
**Status:** fixed
**Keywords:** autofix, claude_p, scheduled_tasks, launchd, daemon, kidsnews-autofix, URL-scheme, KidsnewsAutofix.app, redesign_autofix_queue

## Symptom

The pre-2026-05-04 autofix path used a launchd daemon that spawned `claude -p` headless processes to drain the autofix queue. Two known issues:

1. **Token starvation** (documented at `docs/bugs/2026-04-29-autofix-token-starvation.md`) — concurrent `claude -p` spawns from the daemon contended with the user's interactive Claude Code session for the same Anthropic plan token bucket. IDE locked out for ~2min during drain.

2. **Operational fragility** — required a daemon (`scripts/autofix-daemon.sh`), an installer (`scripts/install-autofix-daemon.sh`), a launchd plist (`scripts/com.daedal.kidsnews-autofix.plist`), an AppleScript app (`scripts/build-autofix-app.sh` building `~/Applications/KidsnewsAutofix.app`), and a custom URL scheme (`kidsnews-autofix://drain`) that macOS Tahoe's tightening of LaunchServices threatened to break. Three layers of click-through to fix one bug.

User experimented (per `~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md`) with Claude Code Desktop's local **scheduled tasks** feature for a similar workload (sourcefinder daily scoring) and confirmed it works. Cleaner architecture: cron + Claude session, no daemon, no URL scheme, no app, no token contention.

User ask (chat 2026-05-04, late evening):

> 我试验成功了，我觉得 cloud claude -p 是没有必要的。我可以把它弄成 schedule task 来做 bug fix。
> ...
> 4 是今天晚上直接拆掉

## Root cause

The launchd + `claude -p` architecture predates Claude Code Desktop having a stable scheduled-tasks feature. The daemon was the only way to wire "auto-process queue rows on a schedule" without the user clicking buttons. The token-starvation issue (2026-04-29) was a direct consequence of running a separate `claude -p` subprocess while the user might have an IDE session open — both share Anthropic plan quota.

When Claude Code 2.1.121 shipped reliable scheduled tasks (per the sourcefinder how-to validated 2026-04-30), the architecture became obsolete. Sub-agent dispatch within a scheduled-task session also addresses the single-session token budget cap that would otherwise cap how much work fits in one fire.

## Fix

PR https://github.com/daijiong1977/news-v2/pull/<TBD>.

### What was torn down

```
launchctl unload ~/Library/LaunchAgents/com.daedal.kidsnews-autofix.plist
rm ~/Library/LaunchAgents/com.daedal.kidsnews-autofix.plist
rm -rf ~/Applications/KidsnewsAutofix.app
```

Files deleted from the repo:

- `pipeline/autofix_consumer.py` (268 lines — daemon-side consumer that spawned `claude -p`)
- `scripts/autofix-daemon.sh` (45 lines — launchd entrypoint)
- `scripts/install-autofix-daemon.sh` (68 lines — installer)
- `scripts/com.daedal.kidsnews-autofix.plist` (64 lines — launchd job spec)
- `scripts/drain-autofix-queue.sh` (47 lines — manual drain via Shortcut)
- `scripts/build-autofix-app.sh` (66 lines — AppleScript app builder)

Total: 558 LOC removed.

### What was added

- `.claude/settings.local.json` — pre-approves Bash/Read/Write/Edit/Glob/Grep/Agent for the scheduled task. Required because `bypassPermissions` mode is broken for scheduled tasks per the sourcefinder how-to, and `acceptEdits` + allow list works.
- `docs/AUTOFIX-SCHEDULED-TASK.md` — operations guide (setup, daily flow, failure modes, manual run).
- `docs/autofix-scheduled-task-prompt.md` — the SKILL prompt body to paste into `mcp__scheduled-tasks__create_scheduled_task`. Two tasks: 3:03 AM EDT and 10:03 AM EDT, both running the same prompt.

### What stayed

- `pipeline/quality_autofix.py` — pipeline-side enqueuing (unchanged).
- `pipeline/autofix_apply.py` — pipeline-side routine fixer (DeepSeek + image regrab) — docstring updated to remove "claude -p" reference. The "escalate" path now hands off to the scheduled task instead of the daemon.
- `pipeline/feedback_triage.py` — quality-digest email — copy updated.
- `website/autofix.html` — admin UI — `🛠️ Fix` button no longer triggers `kidsnews-autofix://` redirect; it just flips queue status.
- `redesign_autofix_queue` table — schema unchanged (the `fix-requested` → `resolved`/`abandoned`/`needs-human` flow is now driven by the scheduled task instead of the daemon).
- `docs/bugs/2026-04-29-autofix-token-starvation.md` — KEPT AS HISTORICAL RECORD. The issue it documents is now structurally resolved (no concurrent `claude -p` spawns).

## Invariant

**The autofix queue's `fix-requested` rows MUST be drained by the local Claude Code scheduled task at next 3:03 AM or 10:03 AM EDT fire.** No other process should run the kidsnews-bugfix skill on queue rows.

If a future change re-introduces a daemon path (e.g., reverts to `claude -p` for some edge case), it MUST coordinate with the scheduled task to avoid concurrent processing of the same row.

`.claude/settings.local.json` MUST keep `defaultMode: acceptEdits` + the allow list. Removing it stalls the first fire on a permission prompt.

The orchestration session in the scheduled task MUST dispatch sub-agents for the actual fix work (per the sourcefinder how-to's "single-session context exhaustion" trap). The orchestration session does only queue management; sub-agents do the code edits and PR opens.

## Pinning test

Manual (no automation infra for orchestration-session simulation):

1. Insert a test row in `redesign_autofix_queue` with `status='fix-requested'` and a synthetic `problem_type` + `problem_detail`.
2. Open Claude Code Desktop → sidebar → `news-v2-autofix-3am` → "Run now".
3. Watch the session execute — confirm:
   - It loads the row from the queue.
   - It dispatches a sub-agent (look for `Task` tool calls in the session log).
   - The sub-agent runs without permission prompts (settings.local.json working).
   - The orchestration session writes back to the queue with the right status.
4. Verify queue row is now `resolved` / `abandoned` / `needs-human` (depending on what the sub-agent did).

If any step stalls or the row stays `fix-requested` after the session ends, the regression is back. The most likely culprits:
- Permissions broken: check `.claude/settings.local.json` and re-pre-flight via "Run now".
- Orchestration session ran the fix itself instead of dispatching: check the session log for inline file edits — there shouldn't be any in the orchestration session.

## Related

- `2026-04-29-autofix-token-starvation.md` — the issue that motivated this migration.
- `~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md` — canonical guide to scheduled tasks; validated empirically.
- `~/myprojects/sourcefinder` — the project where the user first validated this pattern.
- Universal-patterns lesson: **"replace process-spawning subprocess with in-session dispatch"** — when you have a long-lived agent runtime (Claude Code Desktop), prefer dispatching work to it via cron/scheduled-tasks over spawning new shell-out processes that contend for the same resources (token quota, fs locks, etc.).
