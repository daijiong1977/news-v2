# news-v2 — Lessons for Future Similar Projects

> **Purpose**: synthesize patterns from the ~20+ bugs we hit in news-v2
> so the **next** project doesn't relive them. Read this BEFORE
> designing any "daily content pipeline + frontend + email + autofix"
> stack. Each pattern below has been paid for in real debug time.

---

## 1. Platform sandboxes silently override your code

**What we hit:**
- Supabase Edge Functions **force `Content-Type: text/plain`** + `CSP: sandbox` + `nosniff` on every response that *might* be presentation HTML. We spent hours debugging "why is my HTML page rendering as plain text" before realizing the platform itself injects this. Headers we set on the Response object never reach the browser. Bug record: `2026-04-30-supabase-edge-fn-html-blocked.md`.
- **Gmail silently drops** emails with multi-link bodies + custom URL schemes (treated as phishing pattern). Not even spam'd — just gone. The sender gets `success:true` from SMTP, the recipient never gets the email. Symptom only visible from the recipient side.
- **macOS Shortcuts.app (Tahoe / 26.4+)** removed the "Allow Untrusted Shortcuts" toggle. .shortcut files can no longer be auto-installed by `open` even with `shortcuts sign --mode anyone`.
- **Vercel `cleanUrls: true`** runs AFTER rewrites, so destination `/index.html` becomes `/index` → 404. Bug record: `2026-04-28-archive-route-404.md`.

**Rule for next project:**
1. **Verify your assumption from the user's actual entry point**, not via curl alone. `curl` over the wire shows raw server bytes; browser/email-client may apply additional security policies invisible from your side.
2. **For HTML rendering, use a real static host** (Vercel, Cloudflare Pages, S3+CloudFront). Edge function platforms (Supabase, Deno Deploy, Cloudflare Workers) are JSON-API hosts, not webpage hosts.
3. **For emails, avoid custom URL schemes in href** — gateway filters strip them. Use https URLs that redirect server-side if you need to reach a local app.
4. **Read the vendor's "abuse mitigation" docs** before designing the architecture, not after.

## 2. Field names lie — schema docs are critical

**What we hit:**
- `payload.summary` (per-story JSON) is **the article body** (~340 words). The actual short summary is in the LISTING JSON's `summary`. We spent 3 round-trips with the user before realizing this — the digest was telling them "summary is too long" because it was checking the body field as if it were the summary. Bug context: shipped fix in `0682413`.
- Storage prefix dates ≠ story_id dates. A story id `2026-04-28-news-1` may live under `<2026-04-29>/article_payloads/payload_2026-04-28-news-1/...` because pipeline overwrote the listing for 4-29 but kept old article files. Bug record: `2026-04-29-search-click-wrong-article.md`.

**Rule for next project:**
1. **At schema-design time, write a brief field glossary** alongside the SQL — what each field actually contains, with size hint and example.
2. **If a field's name is misleading (e.g. legacy reasons), rename it** OR add a comment in EVERY file that touches it. Field names are the only docs many readers see.
3. **Test cross-source consistency**: when the same logical thing has two paths to access (storage prefix vs story id), write a verification script that runs daily.

## 3. Frontend state + async is hostile

**What we hit:**
- `setArchiveDay(d)` triggered re-render BEFORE the `useEffect`'s async `loadArchive(d)` finished. First render after click had stale `window.ARTICLES`. Click-then-click opened wrong article. Bug record: `2026-04-28-archive-click-race.md`.
- `ARTICLES.find(a => a.id === articleId) || ARTICLES[0]` silently fell back to first article when the searched-for id wasn't in the bundle (because pipeline overwrote the listing). Bug record: `2026-04-29-search-click-wrong-article.md`.

**Rule for next project:**
1. **Any handler that flips state which gates a downstream async fetch MUST `await` the fetch BEFORE flipping state.** The pattern:
   ```js
   onAction = async (newState) => {
     await loadDataFor(newState);   // populate the global before render
     setState(newState);             // then flip
   };
   ```
2. **`array.find(...) || array[0]` is a regret pattern.** When the find should always succeed, throw or log an error. Silent fallback to array[0] means rare misses produce wrong results, not visible failures.
3. **For race conditions, the question is "what does the user see in the FIRST 200ms after click?"** Inspect that frame in the debugger or via UI smoke tests.

## 4. Cleanup migrations destroy infrastructure silently

**What we hit:**
- `public.get_secret` RPC dropped during a "delete old tables" cleanup. Edge functions calling it (send-email-v2, send-digest, etc.) returned `Gmail not configured`. Symptom: user thought emails were just slow; actually they had been broken for days. Bug record: drive-by fix in `c56441a`.
- Pipeline running TWICE on the same date overwrites listing JSONs but accumulates article_payload files. Search index points at orphan story_ids whose listings no longer reference them. Bug record: `2026-04-29-search-click-wrong-article.md`.

**Rule for next project:**
1. **Before dropping any DB function/table, grep ALL code (incl. edge functions, scripts, workflows) for its name.** If found, evaluate before dropping.
2. **For overwriting workflows, write idempotency checks**: "if today already has content, refuse / merge / clearly tag stale parts."
3. **Add invariant assertions in CI**: a smoke test that does end-to-end "click X, expect Y" — if a cleanup breaks Y, CI catches it.

## 5. Concurrent token sharing kills interactive use

**What we hit:**
- Autofix daemon spawned 3 `claude -p` headless calls back-to-back (~6 min). Each shared the user's Anthropic account token with their interactive Claude Code IDE. **IDE locked out for 2 minutes** until the rate-limit window cleared. Bug record: `2026-04-29-autofix-token-starvation.md`.

**Rule for next project:**
1. **Any background agent process must run AT MOST one invocation per scheduled tick** when it shares the user's account token.
2. **If you need higher throughput, use a SEPARATE API key** (different billing pool) so background work doesn't starve interactive sessions.
3. **Document this as an Invariant** in a bug record so future Claude sessions don't reintroduce it.

## 6. Encoding chains break at every layer

**What we hit:**
- Emoji + em-dash + middle-dot in email subject → RFC 2047 encoded-word with line continuations → some email clients fail to decode → entire email renders as raw MIME source.
- Deno `Response(string)` default UTF-8 encoding worked over curl but rendered as latin-1 in browsers (CSP `nosniff` + Supabase's text/plain override at play).
- HTML email with only HTML alternative (no text/plain) → Gmail confused → showed source.

**Rule for next project:**
1. **For email subjects, default to ASCII-only.** Emojis are aesthetics; functionality first. If you must, test in 3+ clients (Gmail web, Apple Mail, iOS Mail) before shipping.
2. **For HTML responses, use `Headers` instance** AND `new TextEncoder().encode(body)` AND `<meta charset="utf-8">`. Belt + suspenders.
3. **For multipart emails, ALWAYS include text/plain alternative**, even if it's just `htmlToText(html)` stripping. Multipart/alternative with one part is malformed per RFC.

## 7. Stem/match algorithms need symmetric treatment

**What we hit:**
- Asymmetric suffix-stripping: `negotiation` → `negotia`, `negotiating` → `negotiat`. Different stems → no match. Cross-check by Copilot CLI caught this bug before merge. Bug record: `2026-04-28-keyword-stem-mismatch.md`.

**Rule for next project:**
1. **Stemming/normalization MUST be symmetric**: apply identical rules to BOTH the keyword AND the body word. Or use suffix-rewrite + set intersection.
2. **Cross-check with multi-model AI review** at every algorithm-level change. Different models notice different bugs.

## 8. LLM output isn't deterministic — post-process every field

**What we hit:**
- LLM emitted `"A final"` as a "keyword" — bogus, not a real keyword. Body checks failed because the literal phrase wasn't in the body.
- LLM hallucinated facts not in the source (when given the reasoner instead of chat).
- Source diversity validator only ran ONCE at the curator stage. After Stage 3 safety rejected a pick, the spare promotion blindly took the next-rank item without re-validating diversity. Bug record: `2026-04-28-news-source-diversity.md`.

**Rule for next project:**
1. **Every LLM-produced field needs a post-validator.** Word count, factual consistency, set membership, etc.
2. **Validators must re-run after every mutation.** "Validated once" is a lie if downstream stages can change the data.
3. **For source-faithful tasks (rewriting, summarization), use chat models with strict prompts. For analytical tasks, use reasoner.** The reasoner WILL invent things from training when given freedom.

## 9. Rate limits stay hidden until they bite

**What we hit:**
- Gmail-to-self rate limit kicked in after ~5 emails in 30min from the same FROM address.
- Claude Pro: concurrent session limits — daemon vs IDE collision.
- DeepSeek tier limits — split-batch fallback when rewrite hits max_tokens.

**Rule for next project:**
1. **Read the rate limit docs FIRST.** Plan retry / batching / dedup BEFORE you ship.
2. **Log every API call with timing.** When you hit a limit, you need attribution to find the chatty caller.
3. **Cron schedule must be coarser than your worst-case retry budget.** If retries can blow 30 min, don't run cron every 30 min.

## 10. Email is hostile, design defensively

**What we hit:**
- Multi-link emails dropped silently by Gmail spam filter.
- Custom URL schemes in `<a href>` flagged as phishing → email dropped.
- Subject lines with emoji + special chars triggered RFC 2047 encoded-word splits → some clients showed encoded form.
- Plain-text alternative missing → Gmail showed raw multipart source.

**Rule for next project:**
1. **Email is a notification, not the UX.** Keep the body minimal: 1 link to a real web page. Put the actual UX (per-item buttons, forms, etc.) on the web page.
2. **Subject = ASCII-only.** No emoji, no em-dashes, no middle-dots.
3. **Always set BOTH text and html alternatives** in multipart/alternative.
4. **Test from the recipient's inbox, not just SMTP success.** "Sender returned 250 OK" ≠ "user got the email."

## 11. Defaults should be conservative

**What we hit:**
- Daemon default was "drain whole queue" → token starvation. Corrected to `--once` per tick.
- Subject lines defaulted to "make it look nice" → Gmail filter trips. Corrected to ASCII.
- Custom URL scheme as primary button URL → Gmail strips it. Corrected to https → page redirect.

**Rule for next project:**
1. **Default to the safest behavior.** Aesthetics, optimization, fanciness all come AFTER reliability.
2. **Make the safe default the EASIEST path**, so future contributors don't fight it.
3. **Surface the trade-off in the code comment.** "Why --once: see bug record X."

## 12. Test at every layer, especially the user's entry point

**What we hit:**
- `curl` returned correct UTF-8 emoji bytes; browser rendered as latin-1. Same bytes on wire, different rendering.
- `send-email-v2` returned `success:true`; user got nothing in inbox.
- Edge function deployed v2 with my fix; user's browser still served v1 from cache.
- Local dev server worked perfectly; CI broke due to `Path('/Users/jiong/...')` hardcodes.

**Rule for next project:**
1. **End-to-end smoke test at the user's actual entry point.** Not just curl, not just the dev server. Use chrome-devtools-mcp / Playwright / similar to drive a real browser.
2. **Cache-bust during testing.** Always test with cache disabled OR via Incognito. Real users don't, but bugs hide there.
3. **Test on the deployed system, not just locally.** Local Python 3.14, local file paths, local rendering — all different from CI Linux + Chrome on user's Mac.

## 13. Bug record discipline pays compound interest

**What we built:**
- `docs/bugs/_template.md` — 5-section format (Symptom / Root cause / Fix / Invariant / Pinning test)
- `docs/bugs/INDEX.md` — grep-first index of all bug records
- `.githooks/commit-msg` — enforces `Bug-Record:` trailer on `fix(` commits

**Why it matters:**
The hook caught my own attempts to commit fix() without records THREE times in this session. Future Claude sessions (which won't have my conversation context) can grep for invariants before touching code. Without this system, every silent fix becomes potentially-rediscoverable knowledge that someone has to relearn.

**Rule for next project:**
1. **Set up the bug-record system from day 1**, not retroactively. Even if it's just `docs/bugs/_template.md` + a casual rule "we write records." Mature it later.
2. **The Invariant section is the most valuable part.** Symptom and Fix are answered by git log. Invariant is the institutional knowledge that prevents regression.
3. **The commit-msg hook is annoying. Keep it anyway.** The 30 seconds of friction is the price of preserving the discipline through tired evenings.

---

## 14. Project shape — what's worth keeping vs. throwing away next time

### Keep

- **Three-repo split** (authoring / deploy / packaging via Supabase Storage zip). The deploy repo stays minimal, the authoring repo can flip private, no ratio between the two.
- **`pack_and_upload` SHELL_FILES vs CONTENT_DIRS distinction.** Lets you republish frontend without re-running expensive LLM pipelines.
- **Bug-record + commit-msg hook combo.** Compounds value.
- **Vercel for HTML, Supabase for data + JSON edge fns + Storage.** Each tool's strengths.
- **Static HTML page that talks to Supabase REST via anon key + RLS.** Very few moving pieces.
- **Single-CTA email design.** Survives spam filters AND keeps the email small.
- **Workflow_run trigger pattern for dependent workflows.** Pipeline → digest auto-fires.

### Throw away (or redesign)

- **Custom URL schemes in email href**. Use https + redirect.
- **Headless agent default of "drain whole queue"**. Use `--once` always.
- **Multipart/alternative with HTML-only**. Always include text/plain alternative.
- **Edge functions returning HTML**. Always return JSON; serve HTML from a real static host.
- **Hardcoded user paths in modules.** Use `Path(__file__).resolve().parent.parent`.
- **Trust that "Test passed" means "feature works."** Test at user's entry point.

---

## 15. The synthesis — one page

If you remember nothing else, internalize these:

1. **Field names lie.** Write a glossary at schema-design time.
2. **Platform sandboxes override you.** Read vendor abuse-mitigation docs first.
3. **`array.find(...) || [0]` is a regret pattern.** Fail loudly.
4. **State + async needs `await` BEFORE state flip.**
5. **Headless agents must `--once` per tick** if they share user's account.
6. **Email subjects are ASCII-only.** Aesthetics later.
7. **Email body has 1 link.** Put the UX on the web.
8. **Bug records compound.** Set up day 1, enforce via commit hook.
9. **Test at the user's entry point.** curl is necessary but not sufficient.
10. **LLMs hallucinate; post-validate everything.**

---

## 16. Promote agent fixes to scripts once the recipe is known

When `claude -p` (or any agent) fixes a class of bug ≥ 2 times, the
recipe should be ported to `pipeline/autofix_apply.py` (deterministic
Python + DeepSeek). Agent reasoning is for novel multi-step work;
text-shape transforms (rewrite to N words, weave/drop keyword,
re-grab og:image) are scripted. See universal pattern #14 in
`~/myprojects/lessons/universal-patterns.md`.

**Project-specific operationalisation:**
- `pipeline/autofix_apply.py` runs in CI between `quality_autofix`
  (scan/enqueue) and `quality_digest` (report).
- The local Mac listener (`autofix_consumer.py` + a 4×/day launchd
  plist) only fires when there's a `status='fix-requested'` row — i.e.
  an admin clicked **🤖 Fix with Claude** on a digest-email
  escalation. Most days it does nothing.
- Each agent run writes its `agent_log` with a `PROMOTABLE:` tag if
  the fix was mechanical. Audit monthly: any pattern ≥ 2 → port a
  handler into `autofix_apply.py`, delete that branch from the
  agent's prompt.

---

## 17. References

- `docs/PROJECT-OVERVIEW.md` — full architecture + ops manual
- `docs/bugs/INDEX.md` — every bug record (8 entries as of 2026-04-29)
- `docs/bugs/HOW-TO-USE.md` — bug record system manual (中文)
- `docs/gotchas.md` — silent edge cases without specific bugs
- `docs/superpowers/specs/` — design docs per feature
