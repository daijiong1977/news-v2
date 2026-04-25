"""Re-enrich existing category detail files using the upgraded detail_enrich()
(deepseek-reasoner + enhanced prompt). Merges new background_read,
Article_Structure, perspectives, keywords, questions into existing payload_*/*.json
— keeps title/summary/image_url/why_it_matters unchanged.

Run:
  python -m pipeline.enrich_existing News
  python -m pipeline.enrich_existing Science
  python -m pipeline.enrich_existing Fun
  python -m pipeline.enrich_existing          # all three
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .news_rss_core import detail_enrich
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrich")


def enrich_category(cat: str, date: str) -> None:
    details_dir = (_REPO_ROOT / "website/article_payloads")
    slug = cat.lower()

    # Build the rewrite_result shape expected by detail_enrich()
    articles_payload = []
    file_paths = {}    # (source_id, level) -> Path
    for slot in (1, 2, 3):
        story_dir = details_dir / f"payload_{date}-{slug}-{slot}"
        easy_f = story_dir / "easy.json"
        middle_f = story_dir / "middle.json"
        if not (easy_f.exists() and middle_f.exists()):
            log.warning("Missing files for %s #%d — skipping", cat, slot)
            continue
        easy = json.loads(easy_f.read_text())
        middle = json.loads(middle_f.read_text())
        sid = slot - 1
        articles_payload.append({
            "source_id": sid,
            "easy_en": {
                "headline": easy.get("title", ""),
                "body": easy.get("summary", ""),
                "why_it_matters": easy.get("why_it_matters", ""),
            },
            "middle_en": {
                "headline": middle.get("title", ""),
                "body": middle.get("summary", ""),
                "why_it_matters": middle.get("why_it_matters", ""),
            },
            "zh": {"headline": "", "summary": ""},
        })
        file_paths[(sid, "easy")] = easy_f
        file_paths[(sid, "middle")] = middle_f
        log.info("  Loaded %s #%d — easy %d words · middle %d words",
                 cat, slot,
                 len(articles_payload[-1]["easy_en"]["body"].split()),
                 len(articles_payload[-1]["middle_en"]["body"].split()))

    if not articles_payload:
        log.error("No articles for %s — aborting", cat)
        return

    rewrite_result = {"articles": articles_payload}
    log.info("[%s] calling deepseek-reasoner (~60-120s) ...", cat)
    enriched = detail_enrich(rewrite_result)
    details = enriched.get("details") or {}
    log.info("[%s] got %d detail slots", cat, len(details))

    # Merge into existing files
    for (sid, lvl), fpath in file_paths.items():
        key = f"{sid}_{lvl}"
        det = details.get(key)
        if not det:
            log.warning("  no detail for %s in %s", key, fpath.name)
            continue
        existing = json.loads(fpath.read_text())
        # Merge the 5 enriched fields; keep everything else
        for field in ("keywords", "questions", "background_read",
                      "Article_Structure", "perspectives"):
            if field in det:
                existing[field] = det[field]
        fpath.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
        log.info("  ✓ merged into %s/%s (%d kw, %d q, %d bg, %d struct, %d persp)",
                 fpath.parent.name, fpath.name,
                 len(existing.get("keywords") or []),
                 len(existing.get("questions") or []),
                 len(existing.get("background_read") or []),
                 len(existing.get("Article_Structure") or []),
                 len(existing.get("perspectives") or []))


def main() -> None:
    from datetime import datetime, timezone
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        cats = [sys.argv[1]]
    else:
        cats = ["News", "Science", "Fun"]
    for cat in cats:
        log.info("========== %s ==========", cat)
        enrich_category(cat, date)


if __name__ == "__main__":
    main()
