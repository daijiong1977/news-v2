# Daily quality-digest email

**Source:** [feedback #10](../../../docs/bugs/HOW-TO-USE.md) → [issue #5](https://github.com/daijiong1977/news-v2/issues/5)
**Classification:** suggestion
**Status:** implemented 2026-04-29

## Why

Owner wants a daily check on pipeline output quality without logging
into the admin or manually inspecting Supabase storage. A drop in
quality (e.g. body too short, missing keywords, source-diversity
violation) should be loud enough to spot in a one-screen email.

## Scope

After every successful (or failed) daily-pipeline run, send an HTML
email to `self@daijiong.com` summarizing the **last 3 days** of
published content.

For each day × category × story × level, compute and display:

- **Word count** vs target (target by level: middle 320-400 / easy
  220-280 / cn 150-300 chars)
- **Summary length** ≤ 80 words
- **Why-it-matters length** ≤ 75 words
- **Keyword coverage** — every keyword findable in body via the
  existing `keyword_in_body` matcher (with stem rules)
- **Image present** — non-empty `image_url`
- **Source present** — non-empty `source_name`
- **All 3 levels generated** — easy + middle + cn payloads exist

Per category per day:
- **Source diversity** — 3 distinct source names

## Architecture

```
daily-pipeline.yml
  ├── ... (existing steps) ...
  ├── Verify kidsnews-v2 sync
  └── Send quality digest         ← new, if: always()
       └── python -m pipeline.quality_digest
            ├── Reads Supabase storage for 3 day prefixes
            ├── Computes metrics per article
            ├── Renders HTML
            └── POSTs to send-email-v2 edge function (Gmail SMTP)
```

No new infra: `send-email-v2` already exists and works.

## Files

- **Create:** `pipeline/quality_digest.py` — reader + scorer + HTML
  renderer + sender
- **Modify:** `.github/workflows/daily-pipeline.yml` — add a final
  `Send quality digest` step with `if: always()` so we get an email
  even when upstream fails (with errors highlighted)

## Configuration

- `QUALITY_DIGEST_TO`  — recipient (default `self@daijiong.com`)
- `QUALITY_DIGEST_DAYS` — lookback window (default 3)
- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` — already in workflow env

## Failure modes (graceful)

- Storage day-prefix missing → render "no data published this day"
  row, don't crash
- Story payload 404 → log warning, skip, count as "incomplete"
- Email send failure → log error, exit non-zero so the workflow run
  shows red (visible signal that the email didn't arrive)

## Pinning test

Manual: trigger `daily-pipeline` workflow with workflow_dispatch
after deploy; confirm email arrives in inbox within ~2 min of run
completion. Eyeball: any cell with a missed metric should be red,
healthy days entirely green/neutral.
