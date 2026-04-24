"""NPR World RSS — LIGHT flow (same shape as news_guardian_full).

Run:  python -m pipeline.news_npr_full
View: http://localhost:18100/news-npr-full.html
"""
from __future__ import annotations

import logging

# Swap constants and re-use the Guardian light-flow main via module substitution
from . import news_guardian_full as _g

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Override the module-level constants before calling main()
_g.GUARDIAN_RSS = "https://feeds.npr.org/1003/rss.xml"
_g.SOURCE_LABEL = "NPR — World"
_g.OUTPUT_SLUG = "news-npr-full"
_g.PICK_COUNT = 2
_g.TARGET_WORDS = 400
_g.MAX_RSS = 25


def main() -> None:
    _g.main()


if __name__ == "__main__":
    main()
