# 2026-09-14 — ChunkedEncodingError escapes LLM retry loops; V4-Flash silently became V4.1

## Symptom

Scheduled daily runs failed on 2026-09-11 and 2026-09-12 and needed a
second dispatch (watchdog) to publish:

- 09-12 (run 34708127711): `requests.exceptions.ChunkedEncodingError:
  Response ended prematurely` — DeepSeek's response stream cut off
  mid-transfer; the run crashed at mega_curate with zero retries.
- 09-11 (run 34627628125): `articles_news_cn.json: article
  2026-09-11-news-3 missing title/summary/id` — the rewrite's zh
  variant came back empty, flowed through as "" (full_round.py:1248),
  and only exploded at pack-time bundle validation.

Context: DeepSeek released V4.1-Flash on 2026-09-10 and retired
V4 Flash; the legacy `deepseek-v4-flash` model id "temporarily" routes
to V4.1-Flash. Runs got ~3x faster from 09-10 (8-11 min vs 21-25 min),
and quality drifted: word-count flags rose (2 on 09-08 → 5 on 09-14,
one middle body at 724w vs the 300-410 spec) and the 09-11 zh dropout
is likely the new model's output quirk.

## Root Cause

The transport-retry `except` tuples in `deepseek_call` (line ~627) and
`_reasoner_call_with_model` (line ~1515) caught only
`(HTTPError, ConnectionError, Timeout)`. A mid-stream disconnect
surfaces as `ChunkedEncodingError` (a `RequestException` subclass not
in the tuple), so one transient network blip killed the whole run
instead of consuming a retry.

## Fix

- Both tuples widened to `except requests.RequestException` — the base
  class covers HTTPError/ConnectionError/Timeout/ChunkedEncodingError
  and any other transport failure. `_retry_sleep_for` already has a
  safe default branch (2s × attempt) for unknown exception types.
- DB `redesign_ai_providers.model_id` updated `deepseek-v4-flash` →
  `deepseek-flash` (official V4.1 id) so we're not riding a deprecated
  alias that DeepSeek says routes only "temporarily".

## Verification

- 09-12 traceback shows the exact escape path (ProtocolError →
  ChunkedEncodingError → uncaught → main_mega crash).
- grep confirms no other `except (requests.HTTPError, ...)` narrow
  tuples remain in pipeline/.
- Post-change scheduled runs to be watched for first-try success.

## Lessons

- Catch `requests.RequestException` in transport retry loops, never a
  hand-picked subset — streaming responses add failure types
  (ChunkedEncodingError, ContentDecodingError) that aren't
  ConnectionError/Timeout.
- A vendor model release can change behavior UNDER the same model id
  (legacy-name routing). When run duration or quality shifts with no
  commit, check the vendor's release notes first.
- Open follow-ups: (1) zh-variant fields should be validated at
  generation time (retry once) instead of failing 15 min later at
  pack; (2) V4.1-Flash length discipline is worse — watch word-count
  flags; if drift continues, re-enable V4 Pro (still served, off-peak
  half-price at our 17:2x UTC cron = 1:2x AM Beijing) or tighten the
  rewrite prompt.
