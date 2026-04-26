# Gotchas — Small Places Where Bugs Hide

Append entries chronologically. Each entry: **Date · Symptom · Root cause · Fix · Where it lives**.

Aim is to capture subtle traps that silently produce wrong-looking output (not crashes — those find themselves). Keep entries ≤ 10 lines.

---

## 2026-04-25 · og:image returned with face cropped off

**Symptom.** Hero photo on the published article had the top of the subject's head cut off (e.g. "ENIAC Replica" article on news.6ray.com — teacher's eyes/forehead missing).

**Root cause.** The article's `<meta property="og:image">` URL embeds publisher-CMS pre-crop directives in its query string. IEEE Spectrum / Squarespace / Imgix-style URLs use `coordinates=`, `rect=`, or `crop=` to force a 2:1 social-share banner. For portrait photos that crop chops heads/feet. Our pipeline downloaded the cropped variant verbatim — `image_optimize.py` only scales, never re-crops — so the bad framing survived all the way to the live site.

**Fix.** `cleaner.py · _strip_banner_crop_params()` strips `coordinates`, `rect`, `crop` from any og:image URL before it gets stored or downloaded. Verified IEEE Spectrum returns the natural 1200×938 (4:3) once `coordinates=` is removed.

**Where to look if it regresses.** `pipeline/cleaner.py · _extract_og_image()` — every call routes through the strip helper. If a new publisher uses a different param name, add it to `_BANNER_CROP_PARAMS`.

---

## 2026-04-25 · Keyword count is not a bundle-validity signal

**Symptom.** Mega run 24921336686 produced 9 finished stories, persisted them to Supabase, then `pack_and_upload` rejected the bundle: 4 News slots had 0 keywords (need ≥3). The article content was fine — the keyword arrays just got drained by the post-LLM literal-appearance filter.

**Why 0 is acceptable.** Keywords aren't editorial signal — they're vocabulary scaffolding for kids. A plain-language body can legitimately yield 0 qualifying terms. Blocking the bundle on keyword count just means a complete article gets withheld over a missing teaching aid.

**Future direction.** Replace the LLM's subjective "above grade-2/3" judgment with a deterministic Google-10k-frequency-rank filter applied server-side: rank >2000 for easy, rank >3000 for middle, plus a small allowlist of named-entity / topical terms the article makes salient. The LLM should emit ALL nouns/verbs from the body; the rank filter does the curation.

**Fix shipped today.** `pipeline/pack_and_upload.py · DETAIL_MIN` no longer lists keywords. The other detail fields (`questions`, `background_read`, `Article_Structure`) still gate the bundle — those ARE editorial signal.

---

## 2026-04-26 · Two send-email functions deployed; assumed Resend, was Gmail SMTP

**Symptom.** Kicking off the parent-digest scaffold I added a Resend-based path with a `RESEND_API_KEY` env var — but the user already had Gmail SMTP working via a different edge function and didn't want a second mail provider.

**Root cause.** Two edge functions on the same project: `send-email` (v17, Nov 2025, AWS SES) and `send-email-v2` (v4, Apr 2026, Gmail SMTP via denomailer). Both had credentials configured in `public.secrets`. From the outside they looked equally "deployed". The newer `send-email-v2` was the actual production path — Gmail address is `daedal1977@gmail.com`, app password lives in `secrets.GMAIL_APP_PASSWORD`.

**Fix.** Switched `send-digest` to POST `send-email-v2` instead of Resend (no extra API key, no extra domain to verify). Workflow secrets needed: only `SUPABASE_PROJECT_REF` + `SUPABASE_FUNCTION_TOKEN` (anon key).

**Lesson learned.** Before scaffolding new infra, list deployed edge functions (`mcp__claude_ai_Supabase__list_edge_functions`) AND check which credentials in `public.secrets` were updated most recently. The `updated_at` column tells you which provider is "current".

---

## 2026-04-26 · Browser-fetch on send-digest got "Failed to fetch" (CORS)

**Symptom.** Parent dashboard's "Send me a copy now" button posted to `https://...supabase.co/functions/v1/send-digest` and got "✗ Failed to fetch" in the inline status. curl from a server worked fine.

**Root cause.** `send-digest` had no `Access-Control-Allow-*` headers and no OPTIONS preflight handler. Browser fetch from `kidsnews.21mins.com` failed at the preflight before the request body ran. `send-email-v2` (Gmail) had CORS, which is why my server-side test worked but the live button didn't.

**Fix.** Added `corsHeaders` constant + an `OPTIONS` early-return + `...corsHeaders` on every Response — same pattern as `send-email-v2` already uses.

**Where to look if it regresses.** `supabase/functions/send-digest/index.ts` — any edge function you call from a browser needs the CORS dance. Don't trust curl-from-localhost as a CORS test.

---

## 2026-04-26 · Republish workflow clobbered today's freshly-mined articles

**Symptom.** Right after a pipeline mined fresh 2026-04-25 stories (Gaza, Strait of Hormuz, etc.), I dispatched `republish-bundle` to ship a parent-dashboard JSX change. Result: kidsnews.21mins.com reverted to 2026-04-24 stories (Betting on Yourself, etc.) — the freshly-mined content was wiped.

**Root cause.** `pack_and_upload` in republish mode collected files from the GitHub Actions runner's checkout of news-v2. The runner has whatever `website/payloads/` and `website/article_payloads/` were last committed to git — which is yesterday-or-older content (the daily pipeline's CI runner generates fresh files but never commits them back). So republish packed STALE committed payloads → uploaded as latest.zip → kidsnews-v2 sync downloaded → site rolled back.

**Fix.** Split `INCLUDE_FILES` / `INCLUDE_DIRS` into SHELL (`website/*.html`, `*.jsx`, `assets/`, `components/`) and CONTENT (`payloads/`, `article_payloads/`, `article_images/`, `article_pdfs/`). In republish mode, `pack_and_upload` downloads the existing `latest.zip` from Supabase Storage, extracts CONTENT_DIRS to a temp dir, and packs SHELL from the local checkout + CONTENT from the temp dir. Now JSX/CSS changes ship without touching content.

**Bonus restore mode.** Set `PACK_RESTORE_FROM_DATE=YYYY-MM-DD` to copy a dated zip → `latest.zip` (no build, no validation) — a one-command recovery from a botched republish.

**Where it lives.** `pipeline/pack_and_upload.py · main()` — the `republish` branch, plus `restore_latest_from()`. Workflow input: `restore_from_date` on `republish-bundle.yml`.

---

## 2026-04-26 · "Pipeline succeeded; site was actually stale" — sync ran silently broken

**Symptom.** `daily-pipeline.yml` reported `success` and `redesign_runs.notes` said "stories persisted: 9; deployed". But kidsnews.21mins.com kept serving yesterday's articles. The persist checkpoint just means `pack_and_upload` finished — it doesn't verify the kidsnews-v2 sync committed the new zip.

**Root cause.** The "Trigger kidsnews-v2 sync" step fired a `curl repository_dispatch` with the `KIDSNEWS_DISPATCH_TOKEN` PAT. The PAT was scoped to the wrong permission ("Actions: Read-only" instead of "Read and write"), so the curl returned 403. The `if: env.KIDSNEWS_DISPATCH_TOKEN != ''` gate let the step run even with a useless token. Step failure surfaced the curl 403, but earlier in the day the workflow shape masked the failure as "expected when no token set" pattern.

**Fix.** Added a "Verify kidsnews-v2 sync completed with fresh content" step to BOTH `daily-pipeline.yml` and `republish-bundle.yml`. Stamps `dispatch_at`; polls `kidsnews-v2/commits` for one authored AFTER `dispatch_at` by the sync bot; fails the workflow with a clear error pointing at the three common causes (PAT scope drift, "no content changes" guard, sync-workflow error).

**Lesson.** Any step that "fires and forgets" against a downstream system needs a positive confirmation step. A green workflow without a downstream check is worse than no workflow.

---

## 2026-04-26 · Fine-grained PAT default permission is "No access", not Read

**Symptom.** Created a fine-grained Personal Access Token, scoped it to one repo, set the secret in news-v2 — `repository_dispatch` curl still returned 403.

**Root cause.** GitHub fine-grained PATs default every repository permission to "No access" except `Metadata` (which is required and read-only). You have to explicitly scroll the long permissions list and set "Actions: Read and write" — there's no helpful "common defaults" preset.

**Fix.** Edit token at `https://github.com/settings/personal-access-tokens` → set **Actions: Read and write** on the target repo → click **Update**. The existing secret value stays valid; no need to regenerate or re-paste.

**Lesson.** When a fine-grained PAT returns 403, the answer is almost always "add Actions: Read and write" — not "regenerate token".

---

## 2026-04-26 · kidsync silently no-op'd because ohye_client_id never got minted

**Symptom.** Kid used the app on a device, but parent's auto-claim found nothing. `redesign_kid_profiles` had no row for that device.

**Root cause.** `ohye_client_id` was generated lazily by `data.jsx::getClientId()` — but `getClientId()` is only called when the kid asks for AI feedback in DiscussTab (one specific button). Most kid sessions never trigger AI feedback. So no client_id, kidsync's `clientId()` returned null, every event RPC was a silent no-op, no kid profile in cloud, parent's `claim_kid_for_caller(NULL)` had nothing to bind to.

**Fix.** `kidsync.js · clientId()` now mints the ID itself on first kidsync.* call (using `window.getClientId` if data.jsx already loaded, else a UUID-shaped fallback). Subsequent calls reuse the persisted value.

**Lesson.** If feature B depends on a unique ID owned by feature A, B should mint the ID eagerly when first used — not assume A will run first.

---

## 2026-04-26 · LLM emitted keywords for slot N+1 in slot N (off-by-one)

**Symptom.** "Rocky Statue" article showed keywords about TICKS. Root: news-2 (Ticks) had NASCAR's keywords; news-3 (Rocky) had Ticks' keywords; news-1 (NASCAR) had empty.

**Root cause.** The detail-enrich LLM call sends N article bodies labeled `=== Article [id: 0] ===`, `[id: 1]`, etc. and asks for output keys `0_easy, 1_easy, 2_easy`. The reasoner shifted: assigned each article's content to the NEXT slot key. The existing `filter_keywords` post-pass DID exist but didn't catch it because... well, we never investigated why. It was either skipped on this code path or had a slot-key parse bug.

**Fix.**
1. **Prompt tightening** — the user message now wraps each body with `=== SLOT KEY: 0_easy === ... Body for slot 0_easy ↓↓↓ ... ↑↑↑ end of body for slot 0_easy`. The system prompt got an explicit ALIGNMENT RULE warning + a FINAL CHECKLIST asking the LLM to verify each keyword before returning. Added "an empty list is acceptable; a misaligned list is NOT."
2. **Pack-time scrub safety net** — `pack_and_upload.build_zip()` now parses every `article_payloads/*/easy.json` and `middle.json`, drops keywords whose term doesn't match the body (suffix-aware regex matching the UI's highlight pass), and re-serializes. Even if upstream still drifts, the deploy zip can never carry hallucinated keywords.

**Where it lives.** `pipeline/news_rss_core.py · DETAIL_ENRICH_PROMPT` + `_detail_enrich_input_single_level()`; `pipeline/pack_and_upload.py · build_zip()` (`_scrub_detail_payload_bytes`).

---

## 2026-04-26 · Article stuck at 75% (3/4 steps) — discuss never credited

**Symptom.** Kid completed all four article steps (read / analyze / quiz / discuss), saved their final answer, picked a reaction. Home page card still showed 75%.

**Root cause.** `bumpStep('discuss')` only fired when the kid clicked the explicit "✓ All done →" button at the bottom of the Discuss tab. Most kids saved final + reacted + closed the tab without ever reaching that button. So `articleProgress[id].steps` topped out at 3 → `_articlePct = 3 × 25 = 75`.

**Fix.** `DiscussTab` now bumps 'discuss' on either of two natural completion signals: `savedFinal` flips to true (effect with ref guard so we fire once), OR the kid picks a reaction. The "✓ All done →" button still works (idempotent — `bumpStep` no-ops on dup steps).

**Lesson.** Tie progress credit to the natural completion moment, not to a separate confirmation button. Buttons that exist only to signal "yes I'm really done" get skipped.

---

## 2026-04-26 · "Same Vercel project name, different project" booby trap

**Symptom.** Pushed to `github.com/daijiong1977/news-v2`, ran tests against `https://news-v2.vercel.app/parent.html` — got HTTP 200 + a SPA fallback page titled "News V2" (a Create-React-App). Spent 10 minutes wondering why the new code wasn't deployed.

**Root cause.** A different Vercel team owns a project ALSO named "news-v2" at `news-v2.vercel.app`. SPA mode rewrites any unknown path to `index.html` and returns 200, so my "is parent.html deployed?" curl gave a false positive.

**Fix.** Verify deploys by **content-grepping** for a string that ONLY exists in the latest version, not by HTTP status code. e.g. `curl https://kidsnews.21mins.com/parent.jsx | grep -c "Email me the full report"`.

**Lesson.** A 200 from `<project>.vercel.app` only means SOMETHING served the request. Always content-check after a deploy if there's any chance of name collision.

## 2026-04-26 · picks-lock + progress wipe at midnight

**Symptom:** users come to kidsnews.21mins.com and (a) every visit
forces a re-pick of today's 3, (b) the streak/recents popover is
empty even after reading articles yesterday/earlier today.

**Root causes (two stacked bugs):**

1. The dayKey rollover guard in `index.html` (initial load + visibility
   change) wiped the entire `progress` object — including `articleProgress`
   (per-article reading state) and the readToday list. The wipe is
   correct for "today's counters" but kills the read history that the
   streak popover sources from.
2. The picks-lock invalidation in `home.jsx` compared a saved
   `bundleStamp` (freshest mined_at across picks) against the current
   pool's mined_at. Every pipeline rerun nudges mined_at, so any
   republish silently invalidated the kid's lock and forced a re-pick
   on the next reload.

**Fix:**

- Day rollover preserves `articleProgress` and a new lifetime
  `readHistory: [{id, at}]` array. Only `readToday` + `minutesToday`
  reset on midnight.
- Streak/recents popover sources from `readHistory` (lifetime), falls
  back to readToday for users on pre-fix saves.
- `article.jsx` appends to `readHistory` whenever an article is
  fully completed (idempotent: skip if last entry was the same id).
- Removed the `bundleStamp` field from the picks-lock entirely.
  The dayKey + "all ids still in pool" checks are sufficient.

**How to spot the next variant:** if you see the symptom "kid lands on
pickup screen on a same-day reload despite picking earlier", check the
saved `ohye_picks_lock_v1` in browser devtools and confirm `dayKey`
matches today's local toDateString. If picksLock is gone entirely,
look for a `setPicksLock(...empty...)` path that fires unintentionally.
