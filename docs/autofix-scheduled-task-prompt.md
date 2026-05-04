# Autofix scheduled-task prompt (3am + 10am EDT)

Paste this entire body into the `prompt` field when you register the
scheduled task via `mcp__scheduled-tasks__create_scheduled_task`.

## Task creation calls (run these in your interactive Claude Code session)

```python
# 3 AM EDT daily
mcp__scheduled-tasks__create_scheduled_task(
    taskId="news-v2-autofix-3am",
    description="news-v2 autofix — drain redesign_autofix_queue at 3 AM EDT",
    cronExpression="3 3 * * *",   # 3:03 AM local (EDT). Off the :00 mark per cron-fleet jitter.
    prompt=open("docs/autofix-scheduled-task-prompt.md").read().split("---PROMPT-BEGIN---")[1],
    notifyOnCompletion=True,
)

# 10 AM EDT daily
mcp__scheduled-tasks__create_scheduled_task(
    taskId="news-v2-autofix-10am",
    description="news-v2 autofix — drain redesign_autofix_queue at 10 AM EDT",
    cronExpression="3 10 * * *",
    prompt=open("docs/autofix-scheduled-task-prompt.md").read().split("---PROMPT-BEGIN---")[1],
    notifyOnCompletion=True,
)
```

Or, paste the prompt body manually (everything between `---PROMPT-BEGIN---` and `---PROMPT-END---`).

---PROMPT-BEGIN---

You are running autonomously. There is no user available to answer questions. The scheduled task that invoked you is the news-v2 autofix drain at 3 AM or 10 AM EDT.

## Your job

Process up to 3 rows from `redesign_autofix_queue` whose `status='fix-requested'`. For each row:

1. Read the queue row's `problem_type`, `payload`, `github_issue_number` (if any), `previous_attempts` count.
2. Dispatch a sub-agent (kidsnews-bugfix skill) to do the actual fix.
3. After the sub-agent returns, write back to the queue: `status='resolved'` on success, or increment `previous_attempts` on failure (after 2 failed attempts, set `status='abandoned'`).
4. Print a one-line status to stdout.

You MUST dispatch sub-agents for the heavy work (per ~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md "single-session context exhaustion" trap). Do NOT do the fix in this orchestration session — its budget is for queue-management only.

## Setup

```bash
cd /Users/jiong/myprojects/news-v2
git checkout main
git pull --ff-only
```

## Step 1 — pull queued rows

Use the Supabase MCP `execute_sql` (project_id `lfknsvavhiqrsasdfyrs`):

```sql
SELECT id, problem_type, problem_detail, github_issue_number,
       payload, previous_attempts, escalated_at
FROM redesign_autofix_queue
WHERE status = 'fix-requested'
ORDER BY escalated_at ASC NULLS LAST, id ASC
LIMIT 3;
```

If the result is empty, write a notification "news-v2 autofix: nothing in queue" and exit 0. Done.

## Step 2 — dump context per row to /tmp

For each row in the result, write a context bundle to `/tmp/autofix-<id>-context.md`:

```markdown
# Autofix queue row <id>

problem_type: <problem_type>
problem_detail: <problem_detail>
github_issue_number: <if any>
previous_attempts: <count>

## Issue body (if github_issue_number set)
<output of `gh issue view <N> -R daijiong1977/news-v2`>

## Payload
<JSON pretty-printed>

## Bug-record discipline
You are operating under the kidsnews-bugfix skill rules. See:
- ~/.claude/skills/kidsnews-bugfix/SKILL.md
- ~/myprojects/news-v2/docs/bugs/INDEX.md
- ~/myprojects/news-v2/docs/bugs/_template.md

You MUST:
1. Create a fix branch (fix/issue-<N>-<slug> or fix/<short-slug>).
2. Make minimal page-scoped edits.
3. For layout/visual changes, deploy a temp preview + verify with Chrome MCP.
4. Write a bug record at docs/bugs/<date>-<slug>.md (5 sections: Symptom, Root cause, Fix, Invariant, Pinning test).
5. Add a row to docs/bugs/INDEX.md.
6. Commit with subject `fix(<area>): <description>` and trailers:
   `Bug-Record: docs/bugs/<date>-<slug>.md` (if existing issue: also `Closes #<N>`)
7. Push branch + open PR with `gh pr create`.
```

## Step 3 — dispatch ONE sub-agent per row (sequentially)

For each context file, dispatch a sub-agent:

```
Agent(
  subagent_type="general-purpose",
  description="Autofix queue row <id>",
  prompt=f"""
You are fixing a bug from the news-v2 autofix queue. Context is in
/tmp/autofix-<id>-context.md — read it first.

Activate the kidsnews-bugfix skill (~/.claude/skills/kidsnews-bugfix/SKILL.md)
and follow it strictly. The autofix queue is the entry point named in
that skill description.

Working directory: /Users/jiong/myprojects/news-v2
Current branch: main (you'll cut a fix branch).

Report back:
- Status: SUCCESS (PR opened) | FAILED (reason) | NEEDS_HUMAN
- PR URL if SUCCESS
- Branch name
- One-line summary of the fix
- Any concerns

Do NOT ask the user questions. The user is asleep. If genuinely
blocked, set NEEDS_HUMAN and report the blocker; the next fire
or the user will pick it up.
"""
)
```

Process rows sequentially (one at a time). Wait for each sub-agent to return before starting the next.

## Step 4 — write back to the queue

For each row, based on the sub-agent's status:

```sql
-- SUCCESS:
UPDATE redesign_autofix_queue
SET status = 'resolved',
    resolved_at = NOW(),
    pr_number = <N>,
    notes = 'Resolved by scheduled-task fire at <ISO>'
WHERE id = <id>;

-- FAILED (and previous_attempts < 2):
UPDATE redesign_autofix_queue
SET previous_attempts = COALESCE(previous_attempts, 0) + 1,
    last_attempt_at = NOW(),
    last_error = '<sub-agent reason>'
WHERE id = <id>;

-- FAILED (and previous_attempts >= 2):
UPDATE redesign_autofix_queue
SET status = 'abandoned',
    abandoned_at = NOW(),
    last_error = '<sub-agent reason>'
WHERE id = <id>;

-- NEEDS_HUMAN:
UPDATE redesign_autofix_queue
SET status = 'needs-human',
    last_attempt_at = NOW(),
    last_error = '<sub-agent reason>'
WHERE id = <id>;
```

## Step 5 — fire a notification

```bash
osascript -e 'display notification "Drained N rows: K resolved, F failed, A abandoned" with title "news-v2 autofix"'
```

(N = total processed, K = SUCCESS, F = FAILED-still-retryable, A = ABANDONED+NEEDS_HUMAN.)

## Constraints / safety

- **Cap: 3 rows per fire.** If queue has > 3, the rest wait until the next fire (10 AM if you're 3 AM, or tomorrow 3 AM if you're 10 AM).
- **No force-push, no main-branch direct commits.** All work goes through `fix/...` branches + PRs.
- **No git config changes.** Don't touch `.gitconfig`.
- **If `cd /Users/jiong/myprojects/news-v2` fails**, the user moved the repo. Fire a notification "news-v2 autofix: repo not found" and exit 1.

## Report at the end

Print a single line summary to stdout:

```
[autofix-scheduled-task <ISO>] processed=N resolved=K retryable=F abandoned=A needs_human=H
```

That's the full task. Begin.

---PROMPT-END---

## Setup checklist (one-time)

After registering the two scheduled tasks (above):

1. **Verify `.claude/settings.local.json` exists in the repo:**
   ```bash
   cat /Users/jiong/myprojects/news-v2/.claude/settings.local.json
   # should show defaultMode: acceptEdits + allow list
   ```

2. **Pre-flight test:** Open Claude Code Desktop sidebar → `news-v2-autofix-3am` → click "Run now". Watch the session execute. Confirm no permission prompts stall it.

3. **Check fire history:** `cat ~/Library/Application\ Support/Claude/claude-code-sessions/*/scheduled-tasks.json` — should show both tasks with their fireAt computed.

4. **Pre-fill DB schema columns** if missing:
   ```sql
   ALTER TABLE redesign_autofix_queue
     ADD COLUMN IF NOT EXISTS pr_number INTEGER,
     ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS abandoned_at TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ,
     ADD COLUMN IF NOT EXISTS last_error TEXT;
   ```

   And ensure status enum allows `needs-human` + `abandoned`:
   ```sql
   SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = 'redesign_autofix_queue'::regclass AND contype = 'c';
   ```

## Operational notes

- Cron is in **local time** (EDT here, not UTC). 3am = 03:00 EDT = 07:00 UTC.
- 5-minute jitter applies to cron fires (per `~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md`); we use `:03` instead of `:00` to land off the global cron fleet's :00-rush.
- If your Mac is closed at 3am, the task **catches up at next launch**. Worst case: 03:00 → next morning 09:00 → 6h late, processing the night's queue.
- Each fire counts against your Pro/Max plan minutes. Expected ~50-100K tokens per fire (orchestration only; sub-agents have their own budget).

## See also

- `~/myprojects/sourcefinder/docs/scheduled-tasks-howto.md` — the canonical guide.
- `~/.claude/skills/kidsnews-bugfix/SKILL.md` — the skill the sub-agent activates.
- `docs/bugs/2026-05-04-autofix-scheduled-task-migration.md` — bug record for this migration.
- `docs/bugs/2026-04-29-autofix-token-starvation.md` — the token-starvation issue this migration also resolves (sub-agent dispatch eliminates concurrent `claude -p` spawning).
