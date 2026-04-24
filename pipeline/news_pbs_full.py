"""PBS NewsHour RSS → 12yo kids news.

Spec: fetch RSS → filter (≥500w + image) → cap at 6 for vetter → pick 2 → rewrite 2.

Run:  python -m pipeline.news_pbs_full
View: http://localhost:18100/news-pbs-full.html
"""
import logging
from .news_rss_core import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    run_pipeline(
        rss_url="https://www.pbs.org/newshour/feeds/rss/headlines",
        source_label="PBS NewsHour",
        output_slug="news-pbs-full",
        max_rss=25,
        max_kept=6,          # cap at 6 to send to vetter
        pick_count=2,
        min_words=500,
        target_words=400,
    )


if __name__ == "__main__":
    main()
