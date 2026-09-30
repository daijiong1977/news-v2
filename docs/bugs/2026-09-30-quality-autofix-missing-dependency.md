# 2026-09-30 quality digest: autofix missing dependency

## Observed

- The natural quality-digest run [36703162747](https://github.com/daijiong1977/news-v2/actions/runs/36703162747) reported workflow success and sent its email, but the email showed six escalated rows.
- The scan queued one new row: `2026-09-29-news-3/easy`, `keyword_miss`. The apply step escalated it without fixing it.
- The other five escalated rows were already in the persistent queue. The email panel queries all `status=escalated` rows, not just the three-day digest window. Their individual causes are not established by this run.

## Root cause

The quality-digest workflow installed only pip itself. `pipeline.autofix_apply` imports `pipeline.news_rss_core` when it reaches independent rewrite safety review; `news_rss_core` imports `feedparser`. The runner did not have `feedparser`, so the apply step raised `ModuleNotFoundError` before safety review or storage update. The exception was caught and represented as an escalated row. The step is `continue-on-error`, so the email still went out and the workflow conclusion was success. That conclusion does **not** mean the auto-fix succeeded.

## Fix and verification boundary

Install the repository's root `requirements.txt` in the quality-digest job, matching the daily pipeline's dependency source. A workflow regression test checks that the apply step and dependency install remain paired and that `feedparser` stays in the requirements.

This change does not rewrite a published article, resolve/dismiss historical escalations, or prove that the next DeepSeek repair will succeed. Confirm on the next natural digest that the apply step reaches independent safety review, reports a real resolved/escalated outcome, and does not show `ModuleNotFoundError`. If the 2026-09-29 keyword issue remains escalated, handle that row separately; do not mark it resolved merely because the dependency was installed.
