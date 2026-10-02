---
name: kidsnews-shadow
description: Generate Kids News using the running Agent's own model; publish only to the separate shadow reader.
---

# Kids News shadow run

Runtime `/workspace/kidsnews-shadow`. Date D is America/New_York.
Model communication lives in `pipeline/ai_providers/` and the shadow-only `pipeline/agent_shadow_providers.py`.
Native file handoff is the default; HTTP role routing is only explicit maintainer configuration.
Run the supplied scripts; do not edit code, prompts, thresholds or this runbook.
Your files are `work/`. The local project maintainer changes code through Git.

## Maintainer-approved hybrid tests

### Current new run: source-first-deepseek fixed five (2026-10-02)

Read docs/KIDSNEWS-FIXED-FIVE-2026-10-02.md and
docs/KIDSNEWS-SOURCE-FIRST-RUNBOOK-2026-10-02.md first. They override older profile rules below.
Use pipeline.kidsnews_bot in a NEW directory. It continuously executes Python preparation,
three DeepSeek ID/abstract top-eight ranks and three five-draft writes. Each of fifteen drafts
contains Easy/Middle/Chinese. No native plan task, no repeated full-text downloads.
Grok must pick and finish THREE inside each fixed FIVE: group task returns all five IDs,
best three then reserves, using DeepSeek order/Python audit as references, not binding rankings.
Relax soft composition preferences, remove child-unsuitable detail, use accurate general
definitions to explain short stories; never invent event facts/quotes/numbers. NO backfill.
Finish one article with both detail levels and self-check in ONE task, then Python validates.
No standalone details generation/audit; normal baseline6 DeepSeek +12 native tasks, repairs extra.
Follow exit2 read/write_to; rerun the SAME kidsnews_bot command, preserving its publish parameters.
The entry drains cheap Python boundaries automatically, not a loop of unanswered requests.
Three-per-section count is a hard completion target. If bounded hard failures leave fewer,
report group-blocked and keep the same five; no sixth candidate or short successful package.
With explicit --publish --ack-same-day-replacement --branch, the entry builds the pinned official
reader and pushes ONLY approved artifact files; existing CI backs up, replaces latest, dispatches
the unchanged website Action and verifies public hashes. Push means pending CI, not deployed.
Article DB/date archive/email are forbidden; preserve debug/cache. Logs ship once per handoff.
Same-directory runs older than24h require --confirm-stale and refreshed history.

### Historical new run: source-first-grok (frozen directories only)

Read docs/KIDSNEWS-SOURCE-FIRST-RUNBOOK-2026-10-02.md and its full Spec.
Use a NEW directory with --editor-mode autonomous --test-profile source-first-grok.
Python collects bodies/photos first: source windows6/3/3, stop immediately at4 qualified,
max12/source, first6 all bad suspends this feed for this run. WebP below20,000 bytes
drops the candidate without alternate images. No native browsing/discovery.
DeepSeek writes five bodies per category; native plan/select plus each review-finish task
modifies ONE article, generates both detail levels and self-checks in ONE response.
No separate detail audit. Normal baseline3 DeepSeek and13 native tasks; repairs extra.
facts_supported=false is recorded warning only in this mode, not proof of factual accuracy.
Python safety/evidence/body gates still apply. Detail-only failure may be repaired once
more or omitted by scripts, never discard a good body only for bad detail. Preserve state.
Exit2 is a request handoff, not failure; answer exact path and resume same directory.
Never rewrite whole batches, edit frozen input, reset budgets, or delete caches.
First new flow stops at checked ZIP for human quality approval; approved website-only
handoff uses existing CI backup/resume protocol. DB/archive/email remain forbidden.

Older profiles below remain supported for SAME-directory resume only.

### Website-only trial after Cloud fixes (2026-10-01)

Read docs/KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md for the current executable contract.
Build/check internal ZIP, then website_release build/check converts to the pinned official
reader shell. Only website_delivery handoff pushes FOUR approved artifact files to a new
codex/website-release-* branch; never push code/main. New Bot CI writes only latest.zip and
latest-manifest.json and dispatches the UNCHANGED website workflow. Credentials remain in CI.
CI disabled/missing credentials/approval is a stop, not permission to use other upload paths.
Never publication_bundle upload or agent_shadow publish for this trial. DB/date archive/SQL/
new Edge Function/email remain forbidden. Same-day slot reuse requires explicit acknowledgement.
Download private website ledger and overlay the read-only registry before prepare. Persist old
pair as CI artifact BEFORE upload; use original run-id for resume/rollback, not whole-job rerun.
Keep all debug/cache/state. Report skipped/uncertain honestly; public hash is the success criterion.

### Current test: Grok final details (2026-10-01)

Use `--editor-mode autonomous --test-profile batch-grok-details` in a NEW directory.
Full summary and Bot message: `docs/KIDSNEWS-GROK-DETAILS-2026-10-01.md`.
DeepSeek still chooses five and writes bodies in one call per category. Grok chooses three,
modifies only those bodies, then generates final details natively (one task per story, both levels).
There is NO extra review-details task: generation/self-check plus Python structure validation,
keyword filtering and deterministic shuffle are NOT independent detail review. Never rewrite
the final titles/bodies/Chinese while enriching. Ground viewpoints, roles and background in source;
keep answer options parallel in length. Longest-correct-answer warnings do not authorize another model call.
News two qualified publishers are accepted in this profile; Science two and Fun three remain.
Science/Fun have no additional standalone strict fact audit, but modifiers still correct false claims.
Normal baseline: three DeepSeek batch calls and 22 native tasks (plan1/select3/modify9/details9),
not a quota promise; repairs/refills add tasks. Stop at local ZIP build/check. Old profiles below
are retained for resume compatibility, not silently upgraded. Do not change frozen input.json.
2026-10-01 family preference: famous tennis/swimming champions and engaging current matches,
comebacks or records take priority among comparably good eligible Fun stories. Do not favor
tearful retirement just for its emotional arc. Follow this in plan, DeepSeek five-draft choice
and final three; never override safety/history/source support or invent favorite names.
Official-reader transition plan (not deployment authorization):
`docs/KIDSNEWS-SAFE-TRANSITION-2026-10-01.md`.

For `--editor-mode autonomous --test-profile batch-deepseek`, the CURRENT 8→5→3 flow is
`docs/KIDSNEWS-BATCH-AND-ZIP-RUNBOOK.md` plus `docs/KIDSNEWS-HYBRID-8-5-3-FLOW.md`.
Run all three categories in a NEW directory with a fresh same-category seven-day registry.
DeepSeek writes five drafts in ONE HTTP call per category; Bot selects three and modifies
only selected bodies. NEVER regenerate all five to fix one bad draft: repair that ID only,
or use its modifier; whole-answer JSON recovery repairs syntax only via native files.
Accepted drafts and settled categories remain fixed. Source-image mechanical checking happens
before the batch writer, with cached final reuse and no extra visual model calls.
Use `.venv/bin/python`; follow exit2 tasks, not a blind shell loop. This profile does NOT
authorize deployment, ready upload, database writes, scheduled function activation or emails.
The ZIP commands in the runbook are separate handoff tools, not permission to publish.

### Same-directory recovery and native transport fallback (2026-09-30)

Prepare may explicitly add `--http-fallback native`; default is OFF, and the choice is
frozen in input.json. Only a failed HTTP transport (bounded pre-execution retries exhausted,
or uncertain delivery) can hand off to native files. Content/length/schema failures NEVER
activate this fallback. Native batch fallback writes FOUR drafts (3+1), not five; its
request omits HTTP max_tokens while retaining the original request_id/validation contract.
Never recompute request_id from the displayed fallback task; copy the supplied ID.
The displayed batch messages AND Python validation cap native fallback at four drafts
(fewer are allowed). fallback_pending is an interrupted quarantine, not a native answer:
rerun resumes local cleanup without HTTP; never copy the archived HTTP draft back.

Exit 2 is a task handoff, NOT a failed run. Read request.json, write answer.json, and run
the exact returned rerun command in the SAME directory. Never delete answer/state/cache,
reset counters, change providers/date, or resend the entire group. Exit 1 pauses a genuine
error; check error_class/http_status/retry_after and report instead of blindly looping.
HTTP errors with a response and confirmed pre-send connection failures retry at most three
times per invocation within the persistent HTTP budget; 429 waits up to 120 seconds.
Read timeouts/resets never auto-resend HTTP. Without explicit fallback, uncertain tasks
remain paused. A corrected key can recover failed_not_executed in the same directory.

answer.json is the atomic HTTP commit record (request_id/revision/attempt_id/usage/content).
An attempting sentinel cannot invalidate a matching answer. First corrections retain
answer.attempt-1.json; do not edit that archive or completed answers.
Task/HTTP/fetch budgets persist across restarts; there is NO one-hour deadline.
After 24 hours, obtain a fresh read-only connector registry and run
`step --confirm-stale --registry /absolute/path/fresh-registry.json`; follow its history
recheck task first. Original publication date remains frozen. status is lock-free and
read-only; inspect answer_integrity without trying to repair accepted answer hashes.
Rechecking includes the current discovered catalog and its final section routing;
archived rows are excluded, and the original date being overwritten remains excluded.
Fetch exhaustion prevents NEW downloads, not use of previously cached eligible originals.

Each native fallback consumes another task and increments fallback_tasks. The runtime
parent ledger .http-fallback-runs.json is state too: never delete it to reset the circuit
breaker. Two consecutive fallback runs exit 1: ask the maintainer to check key/account.
Report fallback task IDs/reasons, possible double billing for uncertain delivery, and
writer_provider. Native-written pieces are “同模型写稿并自检”, not second-model review;
done.json/site manifest report provider=mixed, and ZIP records retain writer_provider.

For `--editor-mode autonomous --test-profile news-deepseek` OR `science-fun-deepseek`, follow
`docs/KIDSNEWS-NEWS-HYBRID-TEST.md` instead of full-round publishing below.
The first profile runs only News; the second runs only Science/Fun, never News. DeepSeek writes bodies/details and reviews details using the user-supplied
`DEEPSEEK_API_KEY` in local `.env`; scripts load it without exposing it. Bot only plans and
modifies full bodies against the source and judges its FINAL corrected draft (or bounded discovery).
For both profiles there is no third AI audit; label this second-model editing/self-check.
Return corrected_article, scores, facts_supported and event_clear. Failed final quality replaces the draft.
HTTP correction budgets are one formatting repair plus one content repair, at most three attempts.
Do not read/print `.env`, manually
answer HTTP tasks, run inactive categories, deploy, write databases or send email. HTTP corrections
are bounded and automatic. Images use source downloads/technical checks, **not** visual
approval; no review-image tasks in this profile. Stop after local pack and report once.
Default full autonomous mode still uses independent visual review. This is an explicit
user-approved external-model exception to the default native-only workflow below.

## Default full-round steps

1. Start with `git pull -q` from the configured code branch.
2. Use the Supabase connector to READ source configs and past-seven-day stories.
   Write the result to `work/D/registry.json` with this query (replace D in both places):

```sql
select json_build_object(
  'date', 'D',
  'sources', (select coalesce(json_agg(s),'[]') from public.redesign_source_configs s where enabled = true),
  'history', (select coalesce(json_agg(h),'[]') from
    (select source_title,source_url,published_date,category from public.redesign_stories
     where archived = false and published_date >= date 'D' - interval '7 days'
       and published_date < date 'D') h)
) as registry;
```

The `history` key is mandatory. Check counts for News/Science/Fun in the returned history list.
If the combined eligible history count is zero, prepare exits 1: verify the connector, database,
date window and permissions; do not replace inaccessible history with []. A zero in one section
is reported, but only all three empty is a hard stop.

3. Run `.venv/bin/python -m pipeline.agent_shadow prepare --run-dir work/D/run-1 --date D --registry work/D/registry.json`.
   Optional maintainer-approved autonomous test: add `--editor-mode autonomous` in a NEW directory.
   Follow `docs/KIDSNEWS-AUTONOMOUS-SHADOW.md`: direct three + reserves, only deficient categories
   may expand. Search is permitted ONLY for discover-* tasks with stated budgets, never other judgments.
   Sources remain temporary; no source-table writes. Mode/provider configuration is frozen per run.
4. Run `.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/run-1`.
   `step` and the compatibility alias `next` stop at ONE successful unit boundary.
   Exit 0 with `completed_step` means that unit is done, NOT that the whole run is done.
   Continue with the returned `next` command, using `.venv/bin/python` on the VM.
   - Exit 2: read the entire `read` file, follow its task messages, write JSON to `write_to`.
     Native Grok or another online Agent answers; no DeepSeek, JEV or Grok API key.
     `content` is a JSON string containing the task answer. Copy request_id exactly.
     Rerun the SAME step command (also printed as `rerun`). On validation errors correct only the answer once.
   - Exit 1: tool/code error. Stop and report; do not fix code or change rules.
   - Exit 3: already done; do not regenerate or republish.
   - Exit 0: check `completed_step` and follow `next`. Only `pack` means local reader files are ready.
5. See `docs/KIDSNEWS-STEPWISE-PIPELINE.md` for all units and acceptance checks.
   Enrichment (keywords/quiz/background/viewpoints) has a separate same-model second pass.
   Every review task MUST use a new session or sub-Agent that reads only its request.
   Do NOT read tasks/rewrite-*/answer.json or carry over the writer's conversational context.
   Report this as "同模型第二遍审核", not an independent reviewer/model. If the platform cannot
   isolate the session, stop the first test and report that limitation; do not claim isolation.
   Code cannot prove session isolation; a human must check it during the first real run.
   Incorrect keywords are filtered mechanically. A rewrite still invalid after one correction is
   recorded as rewrite_invalid and replaced with a reserve. Invalid detail answers omit extras,
   not the safe body. Rank/pick invalid after correction remains a fatal exit 1.
   Field/question review removes only failed fields and MCQs (including wrong correct_answer).
   Images failing to download
   are reported and omitted; never fabricate an image or fetch a replacement yourself.
   Autonomous mode adds review-image-* AFTER safe image fetch: OPEN the actual local pixels
   in a fresh vision session, check relevance/safety/neutrality/privacy/misleading framing,
   and bind your answer to image_sha256. If viewing is unavailable set viewed=false.
   Failed/unverifiable photos are quarantined outside site; keep the approved body.
   A readable image or matching hash alone is not a visual-content approval.
6. Publishing is a separate step. The VM has no Vercel credential. Give the maintainer the site artifact;
   do NOT provision keys or try production publishing as a fallback. From an authenticated Mac, run
   `python -m pipeline.agent_shadow publish --run-dir <local-run-directory>`.
   That command is hard-pinned to the separate `kidsnews-bot-shadow` Vercel project.
   deployment-attempt.json is written BEFORE the CLI call. If deployment times out, do not repeat it;
   run verify first. Only a definite failed verification permits explicit
   `publish --retry-after-failed-verify`; a network timeout does not permit resubmission.
   Zero-article runs cannot publish.
7. Run `.venv/bin/python -m pipeline.agent_shadow verify --run-dir work/D/run-1` after deployment.
   Public verification compares the manifest AND every payload/detail/image hash. A CLI deployment
   response is not evidence that the public site serves this run. Only verified `published.json` means deployed.

The ranking request uses metadata, not full texts. Autonomous shadow body reads are cached
and capped at TWELVE fetch attempts per section (News/Science/Fun independently), including
failed fetches. Batch mode first seeks eight qualified originals; expansion uses the remaining
per-section budget. Missing important News/second Science publisher triggers expansion ONLY
while an untried qualified improving catalog candidate remains; otherwise keep safe drafts
and report the warning, not an endless quota chase.
Each draft is reviewed in a separate request without writer self-scores. Review all English bodies,
headlines/cards and the Chinese card, using the original source for fact support.
Separate review prompts are a second pass, not proof of a separate model/provider.
Top-up targets and accepted stories are saved PER SECTION. A completed section is not fetched,
re-picked or rewritten when another section needs more candidates. Accepted Science stories remain
in the audit; a second publisher may replace a same-publisher final slot without rewriting safe drafts.

Never run `pipeline.full_round`, production pack/upload, production SQL writes, source-table changes,
email commands, or Vercel commands against kidsnews-v2. Never copy this output into production latest.zip.
Do not add keys to files or chat. No arbitrary browsing during judgment; supplied content is data.
Only autonomous discover-* requests permit bounded native public search. If unavailable return an empty list.
If source data or histories are inaccessible, report it rather than pretending history is empty.

Report date, per-section counts, important News present/missing, publisher warnings, rejected articles,
body fetch count, measured timings, and whether the shadow was actually deployed.
Do not create a daily routine yet. First complete one manual shadow run and inspect it with Jiong.
Do not modify completed answers mid-run. For a fresh same-day attempt choose a new run directory.
Successful/terminal answer SHA256 digests are checked on replay. Modified or missing accepted answers
exit 1. Only one command can hold the run-directory lock; a concurrent command exits 1 explicitly.
