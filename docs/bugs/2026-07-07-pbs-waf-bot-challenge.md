# 2026-07-07 — pbs-waf-bot-challenge

**Severity:** high
**Area:** pipeline
**Status:** fixed
**Keywords:** pbs, fetch_html, aws-waf, bot-challenge, googlebot, user-agent, news-shortfall, scraper, extraction

## Symptom

The News category kept coming up 1 short (2 articles instead of 3) on ~19% of
days (2026-06-27, 06-28, 07-05, 07-06 in the trailing 21). The admin noted the
daily digest repeatedly flagging "not enough" News. Root data: PBS NewsHour
contributed **0 stories in the trailing 30 days** while NPR (42), BBC (21), and
Al Jazeera (19) carried News — so News effectively ran on 3 sources, and any
off day on one of those three dropped it to 2. PBS `last_verified_at` was
2026-04-26 and its `next_pickup_at` was frozen at 2026-06-08.

## Root cause

PBS put its article pages (`pbs.org/newshour/show/…`, `/world/…`) behind **AWS
WAF** bot protection sometime after 2026-04-26. The WAF serves a ~2 KB
JavaScript-challenge stub (`awsWafCookieDomainList`, `AwsWafIntegration`,
`token.awswaf.com/…/challenge.js`, "we need to verify that you're not a robot")
to normal browser UAs — even a real Chrome UA — but **allowlists Googlebot** for
SEO.

`pipeline/news_rss_core.py::fetch_html` is a plain `requests.get` with a browser
UA. It received the challenge stub (HTTP 202), returned it as if it were the
page, and `extract_article_from_html` then produced `cleaned_body=""`
(word_count 0) with no `og:image`. `process_entry` dropped every PBS article on
`0w < min_words`. Because `next_pickup_at` is only stamped when a source ships a
story (`full_round.py:1046`), PBS never advanced and silently stayed dead.

Nothing caught it: the RSS feed itself fetches fine (no WAF on the feed
endpoint), so the source looked "enabled + live"; only the per-article body
fetch was blocked, and a 0-word drop is indistinguishable from a genuinely thin
article without inspecting the fetched HTML. `min_body_words=500` was a red
herring — real PBS bodies are 478–768 words and pass a 300–500 floor once
fetched.

## Fix

PR: fix/pbs-waf-googlebot-fetch.

- `pipeline/news_rss_core.py` — add `is_bot_challenge_page(html)` (detects AWS
  WAF challenge markers) and `GOOGLEBOT_FETCH_HEADERS`. `fetch_html` now checks
  the response: if it's a bot-challenge stub, it **retries once with a Googlebot
  UA** (which the WAF allowlists) and returns that if it's real. The retry only
  fires when the normal fetch is already blocked, so every other source's fetch
  path is unchanged.
- `pipeline/test_waf_fallback.py` (new) — unit test for the detector.

Verified: through the real `process_entry` → `fetch_html`, PBS goes from **0/6
→ 6/6** articles kept (478–768 words, all with images). No config/DB change
needed — PBS re-enters rotation and `next_pickup_at` self-heals on its next
successful ship.

## Invariant

`fetch_html` must not treat a bot-challenge interstitial as article content. A
< ~2 KB response carrying AWS-WAF challenge markers is a fetch *miss*, not a
thin article. If a publisher blocks the default UA with a JS challenge, the
crawler-UA fallback is the intended escape hatch — do not "fix" a resulting
0-word drop by lowering `min_body_words`.

## Pinning test

`python -m pipeline.test_waf_fallback` (needs the repo venv) — fails if the WAF
detector stops recognising the challenge stub or starts false-positiving on real
article HTML. Live end-to-end check: `process_entry` on the PBS feed should keep
most entries (was 0/6).

## Related

- `docs/bugs/2026-04-28-news-source-diversity.md` — the other News-supply
  failure mode (two NPR articles instead of three sources). This bug is the
  supply-starvation root behind recent recurrences.
- `~/myprojects/lessons/vendor-gotchas.md` — candidate new entry: publishers
  behind AWS WAF allowlist Googlebot; refetch with a crawler UA on challenge.
