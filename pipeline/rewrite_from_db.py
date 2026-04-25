"""Resume pipeline from DB state — optionally single-category for testing.

Given today's redesign_stories already picked + images already in Storage,
this regenerates body + detail payload without re-doing Phase A/B.

Steps (per category):
  1. Query redesign_stories for today → source URLs, image paths, story metadata
  2. Re-fetch each source URL + extract body via cleaner
  3. Tri-variant rewrite (1 call per category)
  4. Detail enrich (1 call per category)
  5. Emit v1-shape payload files

Run all 3 categories:
  python -m pipeline.rewrite_from_db

Run one category only (for testing):
  python -m pipeline.rewrite_from_db News
  python -m pipeline.rewrite_from_db Science
  python -m pipeline.rewrite_from_db Fun
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from supabase import create_client

from .cleaner import extract_article_from_html
from .full_round import card_summary
from .news_rss_core import detail_enrich, tri_variant_rewrite
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("resume")

_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

WEBSITE_DIR = (_REPO_ROOT / "website")


def fetch_body(url: str) -> tuple[str, list[str]]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code >= 400:
            return "", []
        ex = extract_article_from_html(url, r.text)
        return ex.get("cleaned_body") or "", ex.get("paragraphs") or []
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return "", []


def main() -> None:
    import sys
    only_cat = sys.argv[1] if len(sys.argv) > 1 else None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    q = sb.table("redesign_stories").select("*").eq("published_date", today)
    if only_cat:
        q = q.eq("category", only_cat)
    res = q.order("category").order("story_slot").execute()
    stories = res.data
    log.info("Fetched %d stories from DB for %s%s", len(stories), today,
             f" (category={only_cat})" if only_cat else "")

    if not stories:
        log.error("No stories in DB for today — aborting")
        return

    # Group by category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for s in stories:
        by_cat[s["category"]].append(s)

    # Re-fetch bodies for each story
    log.info("=== REFETCH BODIES ===")
    for cat, group in by_cat.items():
        for s in group:
            body, paras = fetch_body(s["source_url"])
            s["_body"] = body
            s["_paragraphs"] = paras
            log.info("  [%s #%d] %dw · %s", cat, s["story_slot"], len(body.split()),
                     s["source_title"][:50] if s.get("source_title") else "")

    # Ensure referenced images exist on local disk (CI may have produced them
    # without syncing to this workstation). Pull any missing ones from the
    # redesign-article-images bucket — dated subfolder first, then flat root.
    log.info("=== SYNC IMAGES FROM SUPABASE (missing-only) ===")
    images_dir = WEBSITE_DIR / "article_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    sb_base = os.environ["SUPABASE_URL"].rstrip("/")
    for cat, group in by_cat.items():
        for s in group:
            local = (s.get("primary_image_local") or "").strip()
            if not local:
                continue
            fname = Path(local).name
            dest = images_dir / fname
            if dest.is_file():
                continue
            for subpath in (f"2026-04-24/{fname}", today + "/" + fname, fname):
                url = f"{sb_base}/storage/v1/object/public/redesign-article-images/{subpath}"
                try:
                    r = requests.get(url, timeout=15)
                    if r.status_code == 200 and len(r.content) > 1000:
                        dest.write_bytes(r.content)
                        log.info("  pulled %s (%d bytes)", fname, len(r.content))
                        break
                except Exception as e:
                    log.warning("  image fetch %s: %s", url, e)
            else:
                log.warning("  MISSING image %s — live site will 404 until re-run", fname)

    # Build rewrite input shape
    log.info("=== REWRITE + ENRICH (2 calls per category) ===")
    details_dir = WEBSITE_DIR / "article_payloads"
    payloads_dir = WEBSITE_DIR / "payloads"
    details_dir.mkdir(parents=True, exist_ok=True)
    payloads_dir.mkdir(parents=True, exist_ok=True)

    per_cat_listings: dict[str, dict[str, list]] = {}

    for cat, group in by_cat.items():
        # Build articles_with_ids for tri_variant_rewrite: [(slot, art_dict)]
        arts = []
        for i, s in enumerate(group):
            art = {
                "title": s.get("source_title") or "",
                "link": s.get("source_url") or "",
                "published": "",
                "body": s.get("_body") or "",
            }
            arts.append((i, art))
        if not arts:
            continue
        log.info("  [%s] %d stories", cat, len(arts))

        rewrite_res = tri_variant_rewrite(arts)
        enrich_res = detail_enrich(rewrite_res)
        variants = {a["source_id"]: a for a in rewrite_res.get("articles") or []}
        details = enrich_res.get("details") or {}
        log.info("    rewrite=%d variants · detail=%d slots", len(variants), len(details))

        # Emit listings + details
        per_level: dict[str, list] = {"easy": [], "middle": [], "cn": []}
        for i, s in enumerate(group):
            var = variants.get(i) or {}
            easy = var.get("easy_en") or {}
            middle = var.get("middle_en") or {}
            zh = var.get("zh") or {}
            story_id = s.get("payload_story_id") or f"{today}-{cat.lower()}-{s['story_slot']}"
            img_local = s.get("primary_image_local") or ""
            img_url = f"/{img_local}" if img_local else ""

            # Preserve the original mining timestamp — DB has it as created_at.
            mined_at = s.get("created_at") or datetime.now(timezone.utc).isoformat()
            source_pub = s.get("source_published_at") or ""
            common_listing = {
                "id": story_id,
                "source": s.get("source_name", ""),
                "time_ago": "",
                "mined_at": mined_at,
                "source_published_at": source_pub,
                "image_url": img_url,
                "category": cat,
            }
            per_level["easy"].append({**common_listing,
                "title": easy.get("headline") or s.get("source_title") or "",
                "summary": card_summary(easy),
            })
            per_level["middle"].append({**common_listing,
                "title": middle.get("headline") or s.get("source_title") or "",
                "summary": card_summary(middle),
            })
            per_level["cn"].append({**common_listing,
                "title": zh.get("headline") or "",
                "summary": zh.get("summary") or "",
            })

            # Per-story detail files (easy + middle; no cn detail)
            story_dir = details_dir / f"payload_{story_id}"
            story_dir.mkdir(parents=True, exist_ok=True)
            for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
                slot_key = f"{i}_{lvl_key}"
                det = details.get(slot_key) or {}
                bg = det.get("background_read") or []
                if isinstance(bg, str):
                    bg = [bg]
                detail = {
                    "title": var_obj.get("headline") or s.get("source_title") or "",
                    "summary": var_obj.get("body") or "",
                    "why_it_matters": det.get("why_it_matters", ""),
                    "image_url": img_url,
                    "keywords": det.get("keywords") or [],
                    "questions": det.get("questions") or [],
                    "background_read": bg,
                    "Article_Structure": det.get("Article_Structure") or [],
                    "perspectives": det.get("perspectives") or [],
                    "mined_at": mined_at,
                    "source_published_at": source_pub,
                    "source_name": s.get("source_name", ""),
                    "source_url": s.get("source_url", ""),
                }
                (story_dir / f"{lvl_key}.json").write_text(
                    json.dumps(detail, ensure_ascii=False, indent=2)
                )

        per_cat_listings[cat] = per_level

    # Write listing files
    log.info("=== EMIT LISTINGS ===")
    for cat, per_level in per_cat_listings.items():
        cat_slug = cat.lower()
        for lvl_key, items in per_level.items():
            out = payloads_dir / f"articles_{cat_slug}_{lvl_key}.json"
            out.write_text(json.dumps({"articles": items}, ensure_ascii=False, indent=2))
            log.info("  %s (%d items)", out.name, len(items))

    log.info("DONE. View: http://localhost:18100/")


if __name__ == "__main__":
    main()
