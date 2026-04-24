"""Full round — news + science + fun aggregators → optimize images → upload to
Storage → write redesign_runs + redesign_stories → emit v1-shape payload files
for the new v2 UI.

Run:  python -m pipeline.full_round
View: http://localhost:18100/  (UI loads from website/payloads/ + article_payloads/ + article_images/)
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .news_rss_core import detail_enrich, tri_variant_rewrite
from .fun_sources import todays_enabled_sources as fun_sources
from .fun_sources import todays_topic as fun_topic
from .science_sources import todays_enabled_sources as science_sources
from .science_sources import todays_topic as science_topic
from .image_optimize import fetch_and_optimize
from .supabase_io import insert_run, insert_story, update_run, upload_image
from .news_sources import enabled_sources as news_sources
from .news_aggregate import run_source_with_backups as run_news
from .science_aggregate import run_source_with_backups as run_sci
from .fun_aggregate import run_source_with_backups as run_fun
from .news_sources import backup_sources as news_backups
from .science_sources import todays_backup_sources as sci_backups
from .fun_sources import todays_backup_sources as fun_backups
from .news_rss_core import check_duplicates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("full-round")


# -------------------------------------------------------------------
# 1) Aggregate 3 categories
# -------------------------------------------------------------------

def aggregate_category(label: str, enabled: list, backups: list, runner) -> list[dict]:
    """Run Phase A for each source; return winners list (without dedup/rewrite)."""
    log.info("[%s] aggregating from %d sources", label, len(enabled))
    used_backups: set[str] = set()
    winners: list[dict] = []
    for source in enabled:
        avail = [b for b in backups if b.name not in used_backups]
        res = runner(source, avail)
        if res:
            if res.get("used_backup"):
                used_backups.add(res["source"].name)
            winners.append(res)
    return winners


def dedup_winners(winners: list[dict]) -> list[dict]:
    """One-pass cross-source dup check. If dup, drop weaker."""
    if len(winners) < 2:
        return winners
    briefs = [
        {"id": i, "title": w["winner"].get("title"),
         "source_name": w["source"].name,
         "source_priority": w["source"].priority,
         "excerpt": (w["winner"].get("body") or "")[:400]}
        for i, w in enumerate(winners)
    ]
    dup = check_duplicates(briefs)
    if dup.get("verdict") != "DUP_FOUND":
        return winners
    drop_id = dup.get("drop_suggestion")
    if drop_id is None and dup.get("duplicate_pairs"):
        pair = dup["duplicate_pairs"][0]["ids"]
        drop_id = max(pair, key=lambda i: winners[i]["source"].priority)
    if drop_id is not None and drop_id < len(winners):
        log.info("  dropping cross-source dup [%d] %s", drop_id,
                 winners[drop_id]["winner"].get("title", "")[:60])
        winners = [w for i, w in enumerate(winners) if i != drop_id]
    return winners


# -------------------------------------------------------------------
# 2) Optimize + upload images
# -------------------------------------------------------------------

def _short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def process_images(stories: list[dict], today: str, website_dir: Path) -> None:
    """For each story winner, download + optimize og:image → local cache + Supabase Storage.
    Annotates each story dict with _image_local, _image_storage_url.
    """
    images_dir = website_dir / "article_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for s in stories:
        art = s["winner"]
        og = art.get("og_image")
        if not og:
            log.warning("[%s] no og:image", art.get("title", "")[:60])
            continue
        img_id = _short_hash(art.get("link") or og)
        filename = f"article_{img_id}.webp"
        local_path = images_dir / filename
        info = fetch_and_optimize(og, local_path)
        if not info:
            log.warning("  skip image for %s", art.get("title", "")[:60])
            continue
        s["_image_id"] = img_id
        s["_image_local"] = f"article_images/{filename}"
        s["_image_info"] = info
        # Upload to Supabase Storage (public)
        storage_name = f"{today}/{filename}"
        storage_url = upload_image(local_path, storage_name)
        if storage_url:
            s["_image_storage_url"] = storage_url
        log.info("  ✓ image %s (%.1f KB, q=%d)  %s",
                 filename, info["final_bytes"] / 1024, info["final_quality"],
                 "+ uploaded" if storage_url else "local-only")


# -------------------------------------------------------------------
# 3) Rewrite (tri-variant) — batched per category
# -------------------------------------------------------------------

def rewrite_for_category(stories: list[dict]) -> tuple[dict[int, dict], dict]:
    """Tri-variant rewrite, then detail enrichment. Returns
    (variants_by_src_id, details_by_slot). Raises if either step ultimately
    fails — callers decide whether that's fatal for the whole run."""
    if not stories:
        return {}, {}
    articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
    rewrite_res = tri_variant_rewrite(articles_for_rewrite)
    variants = {a.get("source_id"): a for a in rewrite_res.get("articles") or []}
    if len(variants) < len(stories):
        raise RuntimeError(
            f"rewrite returned {len(variants)} variants for {len(stories)} stories"
        )

    # Phase D — detail enrichment (1 extra call per category)
    enrich = detail_enrich(rewrite_res)
    details_by_slot = enrich.get("details") or {}
    expected_slots = len(stories) * 2  # easy + middle per story
    if len(details_by_slot) < expected_slots:
        raise RuntimeError(
            f"detail_enrich returned {len(details_by_slot)} slots, "
            f"expected {expected_slots}"
        )
    return variants, details_by_slot


# -------------------------------------------------------------------
# 4) Emit v1-shape payload files (what the existing v2 UI reads)
# -------------------------------------------------------------------

def make_story_id(date: str, category: str, slot: int) -> str:
    return f"{date}-{category.lower()}-{slot}"


def card_summary(variant: dict, max_words: int = 120) -> str:
    """Short blurb for the home-page card. Prefer `card_summary` from the
    rewriter; fall back to the first few sentences of `body` capped at
    `max_words`. Strip to whole sentence so it never ends mid-word."""
    cs = (variant.get("card_summary") or "").strip()
    if cs:
        words = cs.split()
        if len(words) <= max_words:
            return cs
        return " ".join(words[:max_words]).rstrip(",;:") + "…"
    body = (variant.get("body") or "").strip()
    if not body:
        return ""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', body)
    out, count = [], 0
    for s in sentences:
        n = len(s.split())
        if count + n > max_words and out:
            break
        out.append(s)
        count += n
        if count >= max_words * 0.6:  # stop once we have a reasonable blurb
            break
    return " ".join(out).strip()


def emit_v1_shape(stories_by_cat: dict[str, list[dict]],
                  variants_by_cat: dict[str, dict[int, dict]],
                  details_by_cat: dict[str, dict[str, dict]],
                  today: str,
                  website_dir: Path) -> None:
    """Write v1-compatible payload files the prototype UI already reads:
      payloads/articles_<cat>_<level>.json  (listings)
      article_payloads/payload_<id>/<level>.json  (detail)
    """
    payloads_dir = website_dir / "payloads"
    details_dir = website_dir / "article_payloads"
    payloads_dir.mkdir(parents=True, exist_ok=True)
    details_dir.mkdir(parents=True, exist_ok=True)

    for category in ("News", "Science", "Fun"):
        stories = stories_by_cat.get(category, [])
        variants = variants_by_cat.get(category, {})
        details = details_by_cat.get(category, {})
        # Build one listing file per level (easy / middle / cn) per category
        per_level_articles = {"easy": [], "middle": [], "cn": []}
        for slot, s in enumerate(stories, start=1):
            art = s["winner"]
            var = variants.get(slot - 1) or {}
            story_id = s.get("_story_id") or make_story_id(today, category, slot)
            s["_story_id"] = story_id
            img_local = s.get("_image_local") or ""
            src_name = s["source"].name
            src_url = art.get("link") or ""
            time_ago = art.get("published") or ""

            easy = var.get("easy_en") or {}
            middle = var.get("middle_en") or {}
            zh = var.get("zh") or {}

            # Listings (flat, v1-shape) — summary is short card blurb (≤120 words)
            per_level_articles["easy"].append({
                "id": story_id,
                "title": easy.get("headline") or art.get("title") or "",
                "summary": card_summary(easy),
                "source": src_name,
                "time_ago": time_ago,
                "image_url": f"/{img_local}" if img_local else "",
                "category": category,
            })
            per_level_articles["middle"].append({
                "id": story_id,
                "title": middle.get("headline") or art.get("title") or "",
                "summary": card_summary(middle),
                "source": src_name,
                "time_ago": time_ago,
                "image_url": f"/{img_local}" if img_local else "",
                "category": category,
            })
            per_level_articles["cn"].append({
                "id": story_id,
                "title": zh.get("headline") or "",
                "summary": zh.get("summary") or "",
                "source": src_name,
                "time_ago": time_ago,
                "image_url": f"/{img_local}" if img_local else "",
                "category": category,
            })

            # Detail payloads (per-story, per-level). Chinese is summary-only → no detail.
            story_detail_dir = details_dir / f"payload_{story_id}"
            story_detail_dir.mkdir(parents=True, exist_ok=True)
            # slot-based lookup into details_by_slot: "<article_index>_<level>"
            for lvl_key, var_obj in (("easy", easy), ("middle", middle)):
                slot_key = f"{slot - 1}_{lvl_key}"
                det = details.get(slot_key) or {}
                bg = det.get("background_read") or []
                if isinstance(bg, str):
                    bg = [bg]
                detail = {
                    "title": var_obj.get("headline") or art.get("title") or "",
                    "summary": var_obj.get("body") or "",      # full body (v1 pattern)
                    "why_it_matters": det.get("why_it_matters", ""),
                    "image_url": f"/{img_local}" if img_local else "",
                    "keywords": det.get("keywords") or [],
                    "questions": det.get("questions") or [],
                    "background_read": bg,
                    "Article_Structure": det.get("Article_Structure") or [],
                    "perspectives": det.get("perspectives") or [],
                }
                (story_detail_dir / f"{lvl_key}.json").write_text(
                    json.dumps(detail, ensure_ascii=False, indent=2)
                )

        # Write 3 listing files per category (easy / middle / cn)
        cat_slug = category.lower()
        for lvl_key, items in per_level_articles.items():
            out = payloads_dir / f"articles_{cat_slug}_{lvl_key}.json"
            out.write_text(json.dumps({"articles": items},
                                       ensure_ascii=False, indent=2))


# -------------------------------------------------------------------
# 5) Persist to Supabase (runs + stories rows)
# -------------------------------------------------------------------

def persist_to_supabase(stories_by_cat, variants_by_cat, today: str, run_id: str) -> int:
    """Insert stories rows; return count inserted."""
    count = 0
    for category, stories in stories_by_cat.items():
        variants = variants_by_cat.get(category, {})
        for slot, s in enumerate(stories, start=1):
            art = s["winner"]
            story_id = s.get("_story_id") or make_story_id(today, category, slot)
            vet = art.get("_vet_info") or {}
            safety = vet.get("safety") or {}
            interest = vet.get("interest") or {}
            src_host = urlparse(art.get("link") or "").netloc.replace("www.", "")
            row = {
                "run_id": run_id,
                "category": category,
                "story_slot": slot,
                "published_date": today,
                "source_name": s["source"].name,
                "source_url": art.get("link") or "",
                "source_title": art.get("title") or "",
                "source_published_at": None,   # skip for now
                "winner_slot": s.get("winner_slot"),
                "used_backup": bool(s.get("used_backup")),
                "backup_for_source": s.get("primary_source_name"),
                "safety_violence":   safety.get("violence"),
                "safety_sexual":     safety.get("sexual"),
                "safety_substance":  safety.get("substance"),
                "safety_language":   safety.get("language"),
                "safety_fear":       safety.get("fear"),
                "safety_adult_themes": safety.get("adult_themes"),
                "safety_distress":   safety.get("distress"),
                "safety_bias":       safety.get("bias"),
                "safety_total":      safety.get("total"),
                "safety_verdict":    safety.get("verdict"),
                "interest_importance": interest.get("importance"),
                "interest_fun_factor": interest.get("fun_factor"),
                "interest_kid_appeal": interest.get("kid_appeal"),
                "interest_peak":       interest.get("peak"),
                "interest_verdict":    interest.get("verdict"),
                "vet_flags": safety.get("flags") or vet.get("flags") or [],
                "primary_image_url": s.get("_image_storage_url") or art.get("og_image"),
                "primary_image_local": s.get("_image_local"),
                "primary_image_credit": src_host,
                "payload_path": f"payloads/articles_{category.lower()}_easy.json",
                "payload_story_id": story_id,
            }
            sid = insert_story(row)
            if sid:
                count += 1
                log.info("  → redesign_stories id=%s · %s #%d %s",
                         sid[:8], category, slot, art.get("title", "")[:50])
            else:
                log.warning("  insert failed: %s", art.get("title", "")[:60])
    return count


# -------------------------------------------------------------------
# Orchestrator
# -------------------------------------------------------------------

def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    website_dir = Path(__file__).resolve().parent.parent / "website"

    # Start run record
    run_id = insert_run({"run_date": today, "status": "running"})
    if not run_id:
        log.warning("insert_run failed — continuing without DB persistence")

    log.info("=== AGGREGATE ===")
    news = aggregate_category("News", news_sources(), news_backups(), run_news)
    science = aggregate_category("Science", science_sources(), sci_backups(), run_sci)
    fun = aggregate_category("Fun", fun_sources(), fun_backups(), run_fun)

    log.info("=== DEDUP (per category) ===")
    news = dedup_winners(news)
    science = dedup_winners(science)
    fun = dedup_winners(fun)
    stories_by_cat = {"News": news, "Science": science, "Fun": fun}
    for cat, ws in stories_by_cat.items():
        log.info("  %s: %d winners", cat, len(ws))

    log.info("=== IMAGES (optimize + upload) ===")
    for cat, ws in stories_by_cat.items():
        log.info("[%s] processing %d images", cat, len(ws))
        process_images(ws, today, website_dir)

    log.info("=== REWRITE (tri-variant + detail enrich, 2 calls per category) ===")
    variants_by_cat: dict[str, dict] = {}
    details_by_cat: dict[str, dict] = {}
    failures: list[str] = []
    for cat, ws in stories_by_cat.items():
        try:
            v, d = rewrite_for_category(ws)
            variants_by_cat[cat] = v
            details_by_cat[cat] = d
            log.info("  [%s] rewrite: %d variants · detail slots: %d",
                     cat, len(v), len(d))
        except Exception as e:  # noqa: BLE001
            log.error("  [%s] rewrite/enrich FAILED: %s", cat, e)
            failures.append(f"{cat}: {e}")

    if failures:
        # Mark run as failed (if DB tracking on), don't upload a partial zip.
        msg = f"{len(failures)} category failures: " + " | ".join(failures)
        if run_id:
            update_run(run_id, {"status": "failed",
                                "finished_at": datetime.now(timezone.utc).isoformat(),
                                "notes": msg})
        log.error("Aborting — %s", msg)
        raise SystemExit(1)

    log.info("=== EMIT v1-shape payload files ===")
    emit_v1_shape(stories_by_cat, variants_by_cat, details_by_cat, today, website_dir)

    log.info("=== PERSIST TO SUPABASE ===")
    count = 0
    if run_id:
        count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
        update_run(run_id, {"status": "completed",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "notes": f"stories persisted: {count}"})

    log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
    try:
        from .pack_and_upload import main as _pack_upload
        _pack_upload()
    except Exception as e:  # noqa: BLE001
        log.warning("pack_and_upload failed — site will lag until next run: %s", e)

    log.info("=== DONE ===")
    total_stories = sum(len(ws) for ws in stories_by_cat.values())
    log.info("Run: %s · Stories: %d · DB persisted: %d", run_id or "(no DB)",
             total_stories, count)
    log.info("View: http://localhost:18100/")


if __name__ == "__main__":
    main()
