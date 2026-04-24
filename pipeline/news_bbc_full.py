"""BBC News RSS — LIGHT flow (same shape as Guardian / NPR).

Feed: http://feeds.bbci.co.uk/news/rss.xml (top stories).

Run:  python -m pipeline.news_bbc_full
View: http://localhost:18100/news-bbc-full.html
"""
from __future__ import annotations

import logging

from . import news_guardian_full as _g

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_g.GUARDIAN_RSS = "http://feeds.bbci.co.uk/news/rss.xml"
_g.SOURCE_LABEL = "BBC News — Top Stories"
_g.OUTPUT_SLUG = "news-bbc-full"
_g.PICK_COUNT = 2
_g.TARGET_WORDS = 400
_g.MAX_RSS = 25


def main() -> None:
    _g.main()


if __name__ == "__main__":
    main()
