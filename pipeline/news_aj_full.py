"""Al Jazeera RSS → 12yo kids news (thin wrapper around news_rss_core).

Run:  python -m pipeline.news_aj_full
View: http://localhost:18100/news-aj-full.html
"""
import logging
from .news_rss_core import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    run_pipeline(
        rss_url="https://www.aljazeera.com/xml/rss/all.xml",
        source_label="Al Jazeera",
        output_slug="news-aj-full",
        max_rss=20,
        max_kept=0,          # no cap for AJ — vet all that pass filter
        pick_count=2,
        min_words=500,
        target_words=400,
    )


if __name__ == "__main__":
    main()
