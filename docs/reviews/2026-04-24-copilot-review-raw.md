● skill(using-superpowers)

● skill(dispatching-parallel-agents)

● Read 2026-04-24-review-brief.md
  │ docs/reviews/2026-04-24-review-brief.md
  └ 177 lines read

● Read daily-pipeline.yml
  │ .github/workflows/daily-pipeline.yml
  └ L1:250 (61 lines read)

● Read index.html
  │ website/index.html
  └ L1:250 (250 lines read)

● Search (glob)
  │ "pipeline/*.py"
  └ 42 files found

● Search (glob)
  │ "website/*.jsx"
  └ 5 files found

I'll review the pipeline code focusing on the specific edge cases mentioned in the brief. Let me start by reading the context document and then inspecting the critical files.Let me read the review brief and then examine the frontend files:Now let me read the review brief for context:Now let me read the review brief and the pipeline files:Now let me view the components.jsx and user-panel.jsx:Now let me read the key pipeline files, starting with full_round.py and the files it depends on:Now let me look at pack_and_upload.py and related pipeline files for security and operational concerns:Now let me search for specific security and correctness issues in the large files:Now let me check for env-loading patterns and look for logging of secrets:Let me check the news_rss_core.py for logging of sensitive data and API calls:Now let me continue reading full_round.py to check the critical edge cases:Now let me examine key sections of home.jsx and article.jsx:Let me check for logging of URLs that might contain secrets or API keys in more detail:Let me continue reviewing article.jsx and check for potential issues with URL construction and archive loading:Let me check for the article structure rendering and potential template-injection risks:Now let me examine error handling in full_round.py and whether partial uploads can happen:Now let me check the other source/aggregate files and look for specific issues:Let me check the archive date validation and URL construction more carefully:Let me search for the DatePopover component and archive date validation:Now let me check the rewrite_from_db file and look at specific edge cases mentioned in the brief:Let me check env loading security more thoroughly:Now let me check how the archive index is fetched and if there's any server-side validation:Now let me examine the artifact upload and see if there could be any secret exposure:Now let me check the news_rss_core.py around line 700 to see the detail_enrich edge case more clearly:Let me check the requirements.txt to understand dependencies and any potential security issues:Let me check for potential localStorage issues and also verify what happens when archive-index.json is compromised:Let me check for any logging of environment variables or secrets in the pipeline code:Now let me look more carefully at the deepseek retry logic to check for 429 handling:Let me check for the CI-only guard mentioned in the brief:Let me check for any other issues with the workflow and partial failure scenarios:Now let me check the full_round.py context around rewrite_for_category to see the error handling:Let me check for potential issues with logging configuration and whether secretsLet coul me check if imagesd leak can through be travers standared ord output: if there's other string injection risks:Let me examine the actual secret masking issue more carefully and check if there are any bypass scenarios:Let me check the exact flow around detail_enrich fallback and check the validation more carefully:Let me also check if there are issues with the article structure rendering:Based on my thorough review of the pipeline code against the brief's key concerns, here areLet me check if there's any risk my findings:

## Code of the Review . Findings —env file being checke Pipeline Domaind in or

---

### **Critical Findings**

**1. CRITICAL: detail exported:_enrich fallback returns partial data without validation**
- **File:line:** `pipeline/news_rss_core.py:681-715`
- **What:** `detail_enrich()` can return incomplete details dict if split-batch calls fail. Falls back gracefully but returns whatever succeeded, violating the contract.
- **Why it matters:** The brief flagged this edge case: "if BOTH easy and middle sub-calls fail? Currently continues with partial details." Then `full_round.py:256` checks `len(details_by_slot) < expected_slots` and raises. However, if one level (easy) succeeds and middle fails, you get 3 out of 6 slots. This passes validation if a category has only 1.5 stories (edge case but possible after dedup), creating partial detail payloads that emit_v1_shape writes to disk. Later `pack_and_upload.py:135-140` checks `Article_Structure` count but doesn't validate it's populated for ALL slots—only that ≥3 exist, which could be satisfied by just easy_0, easy_1, easy_2 if middle all failed.
- **Suggested fix:** Change line 256 to require EXACT count (not `<`), and add retry-on-partial fallback: if first batch returns partial, catch it and trigger split-batch immediately rather than only on RuntimeError.

**2. CRITICAL: pick_winners_with_dedup can exhaust all sources and return empty list**
- **File:line:** `pipeline/full_round.py:131-191`
- **What:** The loop can mark all sources as exhausted (line 178) if every dedup round promotes candidates from the same sources until all exhaust. Then line 180-191 filters by `if name in exhausted` and returns 0 picks.
- **Why it matters:** If 3 sources each have 4 candidates and all 9 candidates are pairwise dupes, the loop tries to promote but exhausts all sources, resulting in `[]` return. Then `emit_v1_shape` writes 0 articles and `pack_and_upload.validate_bundle()` sees empty listings (line 96 checks `len(arts) < 2`), which exits with error. But this is silent in logs—no clear "all candidates exhausted" message.
- **Suggested fix:** Add explicit check after pick loop (line 180-191): if final list is empty, log.error and raise or return sentinel. Also, the loop logic at line 163 breaks if `verdict != DUP_FOUND` but never exhausts aLet me verify the exact line numbers and check one more thing about error handling: source; only promotion at line 176 does. A source can exit the loop with unconsumed candidates if dedup suddenly returns "OK"—those alternates are lost. Document this or force an exit on first OK to maximize candidates used.

**3. CRITICAL: Hardcoded local paths in pipeline modules bypass CI guards**
- **File:line:** `pipeline/rewrite_from_db.py:52`, `pipeline/news_rss_core.py:1209`, `pipeline/news_guardian_full.py:419`, etc.
- **What:** `WEBSITE_DIR = Path("/Users/jiong/myprojects/news-v2/website")` is hardcoded. These are used by one-shot debug scripts, but if CI ever calls these (e.g., via rewrite_from_db), it writes to `/Users/jiong/...` on CI runners, fails, and silently doesn't update the live site.
- **Why it matters:** The brief flagged "Hardcoded `/Users/jiong/...` paths were a CI bug source today." The guard `check_not_overwriting_newer()` doesn't catch this—it only checks manifest timestamps, not whether files were actually written to the correct location.
- **Suggested fix:** Replace with `Path(__file__).resolve().parent.parent / "website"` in all non-test files. Add a fixture that logs `WEBSITE_DIR` at startup so CI logs show the path for debugging.

---

### **Important Findings**

**4. IMPORTANT: deepseek_call doesn't distinguish 429 (rate limit) from other errors**
- **File:line:** `pipeline/news_rss_core.py:241-270`, `630-661`
- **What:** Both `deepseek_call` and `deepseek_reasoner_call` catch `requests.HTTPError` broadly (line 263, 654). A 429 (rate limit) is wrapped as HTTPError but treated the same as any 4xx/5xx. Retry logic uses fixed `time.sleep(2 * attempt)` backoff, not exponential or rate-limit-aware.
- **Why it matters:** Rate limits should trigger longer backoff or fast-fail to preserve quota for later steps. Current logic sleeps 2s, 4s, then fails—if quota is truly exhausted, 4s won't help. The brief asked "Let me check the validate_bundle edge cases more carefully:does it handle rate-limit (429) differently from JSON parse errors?"
- **Suggested fix:** Extract status code from HTTPError, check `r.status_code == 429`, and apply exponential backoff (e.g., 10s, 30s, 90s)Let or me view fail the components lou.dly withjsx more carefully to check for a different exception type. any For non additional issues:-429 errors, retry faster.

**5. IMPORTANT: filter_past_duplicates threshold of 0.80 may drop unrelated stories**
- **File:line:** `pipeline/full_round.py:90-128`
- **What:** Title similarity ≥0.80 → drop. The brief notes: "titles can differ significantly while being the same story; or be identical but different stories." At 0.80, "North Korea Missiles Test" ≈ "North Korea Test Missiles" (high sim, same story ✓) but also "Apple Event Announced" ≈ "Apple Pie Recipe Announced" (high sim, different ✗).
- **Why it matters:** False positives (dropping a real new story) are worse than false negatives (running a duplicate, which cross-source dedup may catch). No data on false-positive rate with 0.80 threshold.
- **Suggested fix:** Benchmark threshold against historical runs. Consider lowering to 0.75 and/or adding a secondary check (e.g., same source URL domain, or DeepSeek semantic similarity, not just string similarity).

**6. IMPORTANT: card_summary prompt enforceability unclear**
- **File:line:** `pipeline/news_rss_core.py:416-420`, `full_round.py:272-296`
- **What:** Rewriter prompt says "card_summary: 6-9 sentences, MAX 120 words" (line 419). But the model may ignoreNow let me create this. a comprehensive final review Fall byback logic checking at ` onefull_round.py:278 more detail about-281` strips the URL construction to 120: words post-hoc. However, if the rewriter returns 200-word card_summary anLet me verifyd the fall theback trunc exceptionates to 120, we handling behavior lose: semantic coherence.
- **Why it matters:** The brief flagged "is the prompt actually enforceable? (We also post-trim with a word cap.)" The post-trim is reactive—if the model emits 3 huge paragraphs, word-capping mid-sentence is lossy.
- **Suggested fix:** Add a harder constraint: "Return the card_summary field as a single paragraph, MAX 120 words. No newlines. Cut off mid-word if needed." Or, post-processing should trim to last complete sentence before word limit, not arbitrary truncation.

---

### **Important (Continued)**

**7. IMPORTANT: partial upload state if upload fails mid-flight**
- **File:line:** `pipeline/pack_and_upload.py:221-252`, `390-415`
- **What:** `upload_dated_flat_files()` uploads files one by one (line 234, 245). If the loop fails on file 47/100, the bucket has 47 files under the dated prefix. Then `upload_archive_index()` at line 255 adds the date to the index anyway. UI sees the date in archive-index but files are incomplete.
- **Why it matters:** The brief asked "is there a state where a partial bundle gets uploaded?" The validation (line 74-172) checks for completeness on-disk BEFORE packing, but during upload to Supabase, a transient network error leaves the bucket in an inconsistent state.
- **Suggested fix:** Wrap the loop in a try-catch. On exception, fetch the list of files actually uploaded, removeNow them let me create ( a comprehensive summary. Letsb me verify one more detail about the workflow.storage.remove()), then re-raise permissions:. Only update archive-index after successful completion.

**8. IMPORTANT: check_not_overwriting_newer is not a sufficient CI-only guard**
- **File:line:** `pipeline/pack_and_upload.py:355-377`
- **What:** The guard compares `local_freshest_mined_at()` vs `remote_freshest_mined_at()`. If someone runs `pack_and_upload` locally AFTER the CI run finishes (with same day's date), local stories have same or newer mined_at, so the check passes. The env var `ALLOW_STALE_UPLOAD=1` is a backdoor.
- **Why it matters:** The brief asked "any evasion paths?" Yes—local run on same day, or set the env var. The intent is "never overwrite CI from local," but the implementation only checks timestamps, not origin.
- **Suggested fix:** Check `GITHUB_ACTIONS` env var or `GITHUB_RUN_ID`. Only allow pack_and_upload from CI, or require a token signed with a secret. Alternatively, add a "locked" flag in the manifest: if remote is locked (CI-produced), local run should fail unless `FORCE_UNLOCK=1` with a hard-coded safe code.

---

### **Minor Findings**

**9. MINOR: Exception handling swPerfect. Now I have all the information I need. Let me compileallows critical context the final findings in pack:

##_and_upload** SUBSTANT
- **File:line:** `IVE FINDINGS — News-v2 pipeline/pack_and_upload.py:412-415Workflow Security &`
- **What:** `uploa Operationsd_dated_flat_files` fails ( Reviewnetwork

### ** timeout1., CRITICAL quota: exceeded, etc.) → Unsafe logge Secretd as Handling in GitHub " Actionsnon-fatal Workflow**
- **" warningSeverity**: Critical. The run
- **File compl**: `.github/workflows/daily-etes,pipeline.yml: zip41 is- uploaded, but users48 can't fetch past`
- **What**: `. datesenv` file written because the flat via files never here landedoc withd. secrets
- **Why it matters:** If expanded in Supabase quota shell, is hit during creating flat unnecessary surface- forfile upload, the site secret works for exposure.
- **Why today it but breaks matters for**: While archive GitHub access. No Actions masks secrets in logs, heredocs can expose secrets alerting.
- **Suggested fix in process:** Add post listings-uploa,d validation shell: query history, or if the bucket mas toking is bypassed. The `.env` file is unnecessary confirm since at Python least N modules files lande read underd ` the date prefix. If countos < expecte.environ` directly.
- **d, failSuggeste thed fix**: Remove lines whole 41-48. run and don Secrets't mark are as complete.

**10. MINOR: already .env injected into the job environment via `env:` block module-level import in multiple files (lines 17 risks-20). exposed secrets**
- **File:line:** `pipeline/news_rss Modules_core.py:35 should continue-40`, using ` `pipeline/suos.environ.pabase_ioget()` without.py:13 the-18 intermediate`, `pipeline/pack_and_upload.py:31-35 `.env` file.

---

### **2. IMPORTANT:`, SUPABASE_ `pipeline/rewrite_from_URLdb.py:40 Incorre-44`
- **What:**ctly Marked as Secret**
- **Severity Each**: Important module loads .  
- **File**: `.githubenv on/workflows/daily-pipeline.yml import.:19 If a` secrets + logger ` orwebsite tra/datacer captures. modulejsx` init har, thedcoded public URL
- **What**: ` DEEPSUPABASE_URL` isSEEK_KEY stored in GitHub and SUPABASE_SERVICE_KEY Secrets but are is visible publicly. visible GitHub in fronten Actions secrets are injd sourceected into code, creating operational confusion about env at job security boundaries start, so the.
- **Why it matters**: .env file is a fallback. Developers may assume But the the pattern is repeate URL is sensitived  when4+ times, it's not, and if a leading to over-protection downstream library of non logs-sensitive data module an __d missedictd protection__, secrets of actual secrets leak.
- **Why it matters:**. The Only brief asked "any `Based on my review of the frontend code, here are the substantive findings:

## Frontend Code Review — News Oh,Ye! v2 pathDEEP

### CRITICAL

**Undefined variable reference (home.jsx:34)**
- **File:lineSEEK_API_KEY` an**: `website/home.jsx:34`
- **What**: Reference to undefined variable `todayArticles`d `SU in `displayPool` memo.
- **Why it matters**: Will throw `ReferenceError: todayArticles is not defined` on everyPABASE_SERVICE_KEY` are render, crashing the app. The app becomes non-functional when trying to load home page content.
- **Suggested fix**: Replace `todayArticles` with `ARTICLES` (or intended variable based on design). The displayPool logic attempts to group articles by category but references a non-existent variable.

---

### IMPORTANT

**Unprotected localStorage writes without error handling (index.html:98, 99, 100, 102 truly sensitive.
- **Suggeste where the, 113, 114)** keyd fix**: Remove ` coul
- **File:line**: `websited enSUPABASE_URL` fromd up in a/index.html:98,  GitHub log99, 100, 102, Secrets. 113, 114`
-?" Standar Defined logging **What**: ` it as a public repository configlocalStorage. variable or in a nonsetItem()` called without try-catch blocks in doesn't filter env var multiple-secret config le use file.aks Keep. The .env fallEffect hooks only.
- **Why it matters**: If localStorage is full (Quotaback is sensible forExceededError) or disabled ( the twoprivate local API browsing, dev keys as restricte, secretsd environments but the module.

---

### **3.), the write-level pattern IMPORTANT will throw: Partial an is risky.
- **Suggested fix Upload crash the app.:** Load Risk Stated secrets once with Non mutations in-Fatal will fail Exception silently from Handling**
- **Severity a single user module (**: Important
- **File**: ` perspective bute.g., `pipeline theconfig.py`), then import/full_round.py:528 app breaks.
- **Suggested fix**:-532 from`
- **What**: ` there. Use Wrap all `packlocalStorage.setItem()` calls in logging_an filters try-catch blocks.d_upload() to re Example` isdact known wrapped in bare secret: `try { localStorage.setItem(' ` keys fromexcept logs. Exception` Ad handler thatd a logsoh guard: ifye_route only running', a JSON in CI an.stringify(route)); } catch( warningd .e) { console.warn(',localStorage allowing unav theailable'); pipelineenv exists, error (fail } to report the`.

** success run) even if so theUnvalidated archiveDate used in URL construction (data.jsx: Supabase uploads partially git-79-80, fail.
- **Why it matters article.jsx:31)**
-push trap**: If catches **File:line**: `website/ ` mistakesdata.jsx:79-80`,validate.

--- `website_bundle`/article.jsx:31` passes

##
- **What**: `archiveDate but then `uploa` is interpol Summaryd_date

The pipeline has solid_flat_d fail-safes (files()validate` (_lineated directly into Supabase Storage URLs without validation when loading archived paybundle 413loads.
- **Why it, check_not_overwriting_) fails, the zip matters**: Whilenewer, detail is index_en already.html doesrich validate arch iniveDate on fallback) but three localStorage Supabase but structural gaps load (regex `/ the supporting flat stan files are missing. The kid out:

1. **detail^\d{4}-\d{dsn_enrich partial2}-\d{2}$/ fallews-back** accepts`), datesv2 sync incomplete workflow may from details pull without ` incompletearchive downstream data-index.json` fet visibility.che. Pipeline
2. **pickd from Supabase ( reportsdata_winners success when deployment.jsx:110) are use_withd un_dedup** can is partiallyvalidated. sil faile If Supabase storageently exhad.
- **Suggested fix**: is compromised or misconfigured, Distinguishust all malicious path candidates between fatal an sequences failures (`d return (validation../../../admin`,) `....//.... and non-fatal (retention). zero stories// For.
3. **`) could traverseHar into un Supabase uploadcoded localintd failures ( pathsended storagenot** in debug pref retention scriptsixes.
- **Suggested fix), raise can**: an compromise Validate archiveDate with exception to CI runs the fail if same regex * the step accidentallybefore* using it in calle URL construction at. linesd in 79-80 an Only productiond 31. Ad catch workflowsd: Supabase connectivity during.

Additionally, ** cleanuprate `if (archiveDate &&  operations!/^\d{4}-\-limitd{2}-\d{2} handling is$/.test(archiveDate)) throw.

---

### **4. IMPORTANT: Archive Index conflated with Failure new Error('Invalid archive date');` trans Creates

**ient errors Operational**,Unvalidated storyId used in Blin an URLd Spot**
- **Severity construction (article.jsx:33)****: Important
- **File**: `
- **File:line**: `pipeline/packwebsite/article.jsx:33`d **upload-time_and_upload.py:431 failures
- **What**: `base-432 canArticle.storyId` (` leavederive + `420d from listing the bucket in an inconsistent state**.-425

** payload) is interpolTopated into fetch`
- **What**: If 3 to URL fix:**
1. **detail_ `update without validation.
- **Why it_archive_index()` fails (enrich:** matters**: If the backend payloaline 430d contains a Require), today mal's date exacticious ` is not recorde match of expecteid, butd slotsd` value the, not ` with zip was already path traversal sequences (<`. Trigger uploaded.e Next split-batch.g., ` run fall../../../sensitive,`), the ` fetchbackback immediately on URL partialf results woulill_missing,d become not just_archive_dirs Runtime()` will re `...payload_../Error.
2. **pick_winners_with_dedup:** Ad../../sensitive/-extract and explicit...d re-upload files exhaustjson unnecession check +`,arily.
- **Why it matters log**: Silent + potentially exposing unintended files raise if at the backend storage end. Force doesn failures in non-fatal operations accum at't enforce strict boundsulate inefficiency least 1 OK an roun.
- **Suggested fix**:d to Validate storyId isd make it har break alpd to diagn anhanumeric/d finose whysafealize picks archive before.
3. **Hardc state useoded paths:** Replace is inconsistent. Logs. Add: `if (!/^ `/ showUsers success when/ji archive[a-zA-Z0-9_-]+$/.test(baseArticle.storyId))ong- throw new Error('Invalid story ID');/...index` is st or use URL` with dynamic `ale. normPath
- **Suggested fix**: Logalization.

**(__ archiveUnvalidated image URLs in CSSfile__).parent.parent- backgroun /index failures withd (home.jsx:200,  "website `224, 691)**
- **"` in alllogFile:line**: `website/home non.error()` not `log.warning()`. Consider.jsx:200, 224, 691`
- **What**: Article image-test modules. making Log URLs are resolve archive-index update embedded directlyd path fatal in CSS ` on or atbackground: startup minimumurl()` without esc. add a check onaping or validation.
- **Why next it matters**: If run to payloa validated image archive-● Explore Review pipeline code
  │ Check brief mentions of partial failures (shell)
  │   │ grep -n "partial\|incomplete\|fallback"
  │   │ /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-review-brief.md
  │   └ 6 lines...
  └ Check detail_enrich fallback continue logic (shell)
      │ grep -n "raise\|return\|continue"
      │ /Users/jiong/myprojects/news-v2/pipeline/news_rss_core.py | grep -A 2 -B 2
      │ "710\|711"
      └ 1 line...

index fresh_url contains CSS-ness.

---

### **5. IMPORTANT: Datebreakingd- characters (`;Flat Uploa`, `"`, `)d Failure Not`, or new Surflines),aced**
- **Severity**: it Important
- **File**: `pipeline could break/pack the CSS rule or allow_and_upload.py:412-415`
- **What**: `uploa CSS injection.d_dated_flat_files()` failure (line 413) is caught Example: `article.image = 'test and logged as non.jpg"); background: url(-fatal, butdata this:... breaksevil the UI''s` ability to fetch woul pastd inject- aday secon contentd CSS directly property from Storage.
- **Why it matters**:.
- **Suggested fix**: Either ( Frontend uses `a) validate<date>/ image URLs are well-formed (payloads/*.startjson with `/` directly`, protocol from, Supabase ( orwebsite safe/data.jsx fetch prefixArch), or (b) useive flow `backgroun).dImage` property If with upload fails, archive properly dates escaped URL will: `style={{ be listed in archive-index but filesbackgroundImage: `url(${JSON won't exist.stringify(article.image).slice, causing (1404s,- in1)})`, the backgroundSize: 'cover'... UI}}.
- **Suggested fix**:` Make or enc `upload_dated_flat_files()` forode todayU's date fatalRI.

---

### MINOR (

**Missingnon dependency-negoti orable for st today's deploymentale closure in). Only progress mark state back (indexfill of.html:113)**
- **File:line**: `website/index.html:113 old dates as non-fatal.

---

### **6. MINOR`
- **What**: `localStorage.setItem(': Unnecessaryohye_progress', JSON.stringify(progress))` SUPABASE_URL Logge dependsd**
- **Severity**: Minor only
- **File**: `pipeline/ on `[packprogress]_and_upload.py:440`,-441`
- **What**: but `progress` object includes SUPABASE_URL is logged as neste partd fields of the public that URL may not trigger string re-renders if, creating noise mut inated.
- **Why it matters logs and potentially**: If `progress. exposing bucketarticle structureProgress.
- **Why it matters**:` is mutated directly rather than replace Bucket named, the useEffect may (` not fireredes, anign-dailyd saves-content coul`) and URLd be lost ( are loggelowd unnecess priority givenarily. While not a secret, this information should only be logged if needed for debugging.
- **Suggeste the bumpProgress logic replaces the object).
- **Suggested fix**: Lowd fix**: Remove line priority, 441 or but consider only verifying `bumpProgress` always log the filename (`latest.zip creates new`) without object references the full: URL.

---

### **7 `const. INFO next: No Remote Fresh = { ...p, articleProgress: { ...ap, [ness Check on Partialarticle.id]: p Datact**
- **Severity**: Info } };`
- **File**: `pipeline/ (pack_and_upload.py:already355 doing this correctly-377,` so ( not a realcheck_not_overwriting_newer) issue).

---
- **What**: Fresh

## Summaryness check compares `m

The codebase has **oneine critical runtimed_at` timestamps, crash but only** ( for storiesundefined variable), **two in `latest blocking- errormanifest modes.json`. If archive** (localStorage quota/-index updatedisable, faile path traversal ind, manifest archive may be st URLsale while), and **two zip data is fresh-.
- **Why it matters**: Edge caseintegrity/injection risks where local** (storyId, image URLs). The localStorage pipeline is prevented from uplo issue is the most userading because manifest-visible from failure yesterday's successful mode on zip restricte is newerd environments,. but The path today traversal risks are lower's data-probability ( is ready. This isrequire acceptable behavior ( Supabase compromiseconservative) but high)-severity if but worth explo noting.
- **Suggested fixited.

****:Top Acceptable  as3 fixes-is; the check prevents (priority order):**
1. Fix ` acctodayArticles` undefineidental overwd →rites. replace If this with correct becomes variable ( a blocker, add explicit loggingblocks app) of the decision
2. Ad.

---

##d try Summary-catch around all

** localStorage writes → preventsOverall crashes on Assessment**: Pipeline quota/disabled storage has
3. Validate archiveDate soli and validationd storyId before URL (` construction → prevents path traversal attacksvalidate_bundle`), but error handling in `pack_and_upload()` conflates fatal (● Explore Review frontend code
  │ Read components.jsx
  │   │ website/components.jsx
  │   └ L100:200 (97 lines read)
  └ Read article.jsx
      │ website/article.jsx
      └ L28:62 (34 lines read)

validation, freshness check) and non-fatal (cleanup) failures. The three-repo architecture works because kidsnews-v2 pulls immutable `latest.zip`, but silent failures in archive-index and dated-flat uploads can cause the frontend's archive browsing feature to break without visibility.

**Top 3 fixes (priority order)**:
1. **Remove `.env` file creation** in workflow (line 41-48) — unnecessary and risky
2. **Differentiate fatal vs non-fatal failures** in `pack_and_upload.py` — make dated-flat for today fatal, archive-index failure log.error()
3. **Move SUPABASE_URL out of Secrets** — it's public; reduces confusion and operational overhead● Explore Review workflow security
  │ Check SystemExit handling (shell)
  │   │ python3 -c "
  │   │ try:
  │   │ raise SystemExit(1)
  │   │ except Exception as e:
  │   │ print('Caught by Exception')…
  │   └ 5 lines...
  └ Check workflow permissions (shell)
      │ grep -A20 "permissions:"
      │ /Users/jiong/myprojects/news-v2/.github/workflows/daily-pipeline.yml
      └ 22 lines...

● Read data.jsx
  │ website/data.jsx
  └ L1:260 (137 lines read)

● Read article.jsx
  │ website/article.jsx
  └ L1:260 (260 lines read)

● Read full_round.py
  │ pipeline/full_round.py
  └ L1:360 (360 lines read)

● Read news_rss_core.py
  │ pipeline/news_rss_core.py
  └ L1:900 (491 lines read)

● Read pack_and_upload.py
  │ pipeline/pack_and_upload.py
  └ L1:520 (445 lines read)

● Read home.jsx
  │ website/home.jsx
  └ L1:220 (220 lines read)

● Read rewrite_from_db.py
  │ pipeline/rewrite_from_db.py
  └ L1:220 (220 lines read)

● Read config.py
  │ pipeline/config.py
  └ L1:220 (216 lines read)

● Search (grep)
  │ "todayArticles|localStorage\.setItem|loadArchive|archiveDate|storyId|backgro
  │ und:url|dangerouslySetInnerHTML|postMessage|unpkg.com|babel|fetch\(" in
  │ website/*.{jsx,html}
  └ 56 lines found

● Search (grep)
  │ "def pick_winners_with_dedup|def filter_past_duplicates|def
  │ detail_enrich|def deepseek_call|def
  │ deepseek_reasoner_call|check_not_overwriting_newer|upload_dated_flat_files|u
  │ pdate_archive_index|ALLOW_STALE_UPLOAD|/Users/jiong" in pipeline/*.py
  └ 40 lines found

● Read news_rss_core.py
  │ pipeline/news_rss_core.py
  └ L560:780 (221 lines read)

● Read index.html
  │ website/index.html
  └ L90:310 (186 lines read)

● Read home.jsx
  │ website/home.jsx
  └ L220:460 (241 lines read)

● Read full_round.py
  │ pipeline/full_round.py
  └ L360:620 (183 lines read)

● Read supabase_io.py
  │ pipeline/supabase_io.py
  └ L1:220 (83 lines read)

● Read news_rss_core.py
  │ pipeline/news_rss_core.py
  └ L462:520 (59 lines read)

● Search (grep)
  │ "def client|SUPABASE_SERVICE_KEY|create_client|logging" in supabase_io.py
  │ (pipeline)
  └ 8 lines found

● Search (grep)
  │ "DEEPSEEK|SUPABASE_SERVICE_KEY|SUPABASE_URL" in website/*.{jsx,html}
  └ 2 lines found

- **Severity**: `Critical`  
  **File:line**: `website/home.jsx:31-37`  
  **What**: `HomePage` references `todayArticles`, but that identifier is never defined anywhere in the file.  
  **Why**: That `useMemo` runs during render, so the first trip through the home page throws a `ReferenceError` and the UI never mounts the listing view. This is a hard correctness bug, not just a stale-code smell.  
  **Fix**: Build `displayPool` from an actually defined source (`ARTICLES`, `filteredRaw`, or another explicit per-category pool) and keep the dependency list aligned with that source.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`website/index.html:61-76,98-114`; `website/home.jsx:41-55`)  
  **What**: The app reads and writes `localStorage` in several places without a safe wrapper.  
  **Why**: Browsers can throw on `localStorage` access when storage is disabled/restricted, and writes can throw `QuotaExceededError` when storage is full. In this app those exceptions happen inside state initializers/effects, so one bad storage environment can take down routing, archive mode, progress saving, or daily-picks persistence.  
  **Fix**: Centralize `getItem` / `setItem` / `removeItem` behind a small `safeStorage` helper with `try/catch`, and fall back to in-memory defaults when storage is unavailable.

- **Severity**: `Important`  
  **File:line**: `pipeline/full_round.py:521-532`  
  **What**: The run is marked `completed` in Supabase before `pack_and_upload()` runs, and upload-phase exceptions are downgraded to a warning.  
  **Why**: A run can be recorded as completed even when the bundle never ships, archive uploads fail, or deployment lags. That creates false-green operational state exactly when you most need the DB status to tell you the truth.  
  **Fix**: Move `update_run(... status="completed" ...)` until after a successful pack/upload phase, and record a failed/degraded terminal state when upload or archive publication fails.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`pipeline/pack_and_upload.py:276-296,411-432`; `website/data.jsx:78-80,106-123`; `website/home.jsx:351-383`)  
  **What**: Flat-file upload and archive-index update are treated as non-fatal even though the frontend depends on them for archive browsing.  
  **Why**: The UI reads old editions from `<date>/payloads/*.json` and discovers dates from `archive-index.json`; if flat upload fails and the date still lands in the index, the site advertises an archive day whose payloads 404. Worse, once that date is in the index, future backfill logic stops considering it “missing,” so the bad state can stick.  
  **Fix**: Only add `today` to `archive-index.json` after flat files are confirmed present, and fail the run (or at least leave the date out of the index) if both direct upload and backfill fail.

- **Severity**: `Important`  
  **File:line**: `pipeline/news_rss_core.py:241-270,630-661`  
  **What**: DeepSeek retry logic treats malformed JSON, 429/rate limiting, and generic network failures as the same class of error with the same short linear backoff.  
  **Why**: Those failures need different behavior: malformed JSON often merits a quick retry, while 429 usually needs a longer wait or explicit surfacing. The current 2s/4s backoff is too short for quota/rate-limit recovery and makes the logs less actionable.  
  **Fix**: Split retry policy by failure type: inspect HTTP status, honor `Retry-After` when present, use longer exponential backoff for 429s, and keep JSON-repair retries separate.

- **Severity**: `Important`  
  **File:line**: cross-cutting (`pipeline/news_rss_core.py:462-477,495-500,570-585,668-678`; `pipeline/full_round.py:242-260`)  
  **What**: The rewrite/enrich prompts are hard-coded for exactly 3 articles / 6 slots, but the pipeline explicitly supports thinner categories after dedup.  
  **Why**: On a legitimate 2-story day, the model is still told “3 articles” and asked for slot keys through `2_middle`, which increases the chance of hallucinated extra output, malformed structure, or attention wasted on nonexistent items. This is prompt-contract drift between orchestration and prompt design.  
  **Fix**: Parameterize prompt text and expected slot keys from the actual article count instead of embedding `3 articles`, `6 slots`, and `0..2` literals.

- **Severity**: `Minor`  
  **File:line**: `pipeline/full_round.py:69-80,90-128`  
  **What**: Past-duplicate filtering is driven entirely by `SequenceMatcher` title similarity at a fixed `0.80` threshold.  
  **Why**: Title-only matching will inevitably miss same-story rewrites with different wording and occasionally drop distinct stories with templated/similar headlines. Because this filter runs before cross-source promotion, false positives directly shrink the candidate pool on already-thin days.  
  **Fix**: Keep the cheap title check, but add a second signal before dropping (for example source URL hostname + named-entity overlap, or a small semantic duplicate pass on borderline cases).

- **Severity**: `Minor`  
  **File:line**: cross-cutting (`pipeline/rewrite_from_db.py:52`; `pipeline/news_rss_core.py:1209,1226`; `pipeline/news_aggregate.py:348,372`)  
  **What**: Hard-coded `/Users/jiong/...` paths still exist in the resume/debug path and related helper scripts.  
  **Why**: The brief called this out as a real CI footgun today, and those machine-specific paths are still present in non-primary flows. That means recovery/debug tooling remains host-bound and easy to break on CI or another workstation.  
  **Fix**: Route every website/output path through one repo-root-derived constant (`Path(__file__).resolve().parent.parent / "website"` or `config.PROJECT_ROOT`) instead of embedding absolute user paths.

Overall, the architecture still looks directionally sound: zip-for-deploy plus flat-files-for-archive is justified, and I did not see any frontend leak of the DeepSeek key or Supabase service key. The bigger problems are reliability mismatches between “pipeline succeeded” and “site/archive is actually usable,” plus one outright frontend crash. Prompt contracts have also drifted from the new 2-or-3-story reality, which will show up exactly on the hardest days.

**Top 3 things to fix first**
1. Fix the `todayArticles` crash in `website/home.jsx`.
2. Make upload/archive publication failures truthfully fail or degrade the run state instead of recording `completed`.
3. Parameterize rewrite/enrich prompts by actual story count so 2-story days are first-class, not an accidental edge case.


Changes   +0 -0
Requests  1 Premium (6m 36s)
Tokens    ↑ 3.4m • ↓ 44.9k • 3.1m (cached) • 12.0k (reasoning)
Session exported to: /Users/jiong/myprojects/news-v2/docs/reviews/2026-04-24-copilot-review.md
