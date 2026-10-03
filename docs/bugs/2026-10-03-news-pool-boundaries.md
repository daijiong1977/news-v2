# News pool loses major stories and admits Fun-origin stale events

## Symptoms and root cause

News 1200-word upper bound silently omitted the 1474-word Supreme Court article.
Fun-origin items were allowed to refill News. Four mechanical passes stopped PBS
before later civic reporting, although early rows were already forbidden by ranking.

## Fix

News originals 350–2000, Fun-origin blocked at cache-only News entrance, and
new source journals screen explicit metadata hard exclusions before counting passes.
Routing global cap frozen at2000 in new journals; legacy journals retain1500.
No production full_round/news_rss_core paths changed. No site or database writes.

## Regression

pipeline/test_news_pool_boundaries.py: three tests failed before fix and passed
after; source-first/shortlist/freshness/provider tests total46 pass on Python3.10.
See docs/KIDSNEWS-NEWS-POOL-2026-10-03.md for rollout boundaries.
