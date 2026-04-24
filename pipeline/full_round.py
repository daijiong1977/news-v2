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

from .news_rss_core import (check_duplicates, detail_enrich,
                              run_source_phase_a, tri_variant_rewrite)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("full-round")


# -------------------------------------------------------------------
# 1) Aggregate 3 categories
# -------------------------------------------------------------------

def aggregate_category(label: str, enabled: list, backups: list, runner) -> dict[str, dict]:
    """Run Phase A for each source; return `{source_name: {source, candidates}}`.
    Each source contributes up to 4 ranked candidates (choice_1…). If the
    primary source yields 0 candidates, rotates to a backup source (handled
    inside `runner`)."""
    log.info("[%s] aggregating from %d sources", label, len(enabled))
    used_backups: set[str] = set()
    by_source: dict[str, dict] = {}
    for source in enabled:
        avail = [b for b in backups if b.name not in used_backups]
        res = runner(source, avail)
        if not res:
            continue
        # Supports both the new multi-candidate Phase A return shape and the
        # legacy single-winner shape (some aggregator paths still produce
        # the latter, e.g. after backup rotation).
        cands = res.get("candidates")
        if not cands and res.get("winner"):
            cands = [{"winner": res["winner"], "slot": res.get("winner_slot") or "choice_1"}]
        if not cands:
            continue
        src_obj = res["source"]
        by_source[src_obj.name] = {"source": src_obj, "candidates": cands}
        if res.get("used_backup"):
            used_backups.add(src_obj.name)
    return by_source


def _normalize_title(t: str) -> str:
    """lowercase + strip punctuation + collapse whitespace for similarity match."""
    import re as _re
    s = (t or "").lower()
    s = _re.sub(r"[^\w\s]", " ", s)
    s = _re.sub(r"\s+", " ", s).strip()
    return s


def _title_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


# Shape used by filter_past_duplicates + pick_winners_with_dedup:
#   by_source = {
#     <source_name>: {"source": <SourceObj>, "candidates": [{"winner": art, "slot": "choice_1"}, ...]},
#     ...
#   }


def filter_past_duplicates(category: str, by_source: dict[str, dict],
                           days: int = 3, threshold: float = 0.80) -> dict[str, dict]:
    """Drop candidates whose title ≥threshold-matches any story this category
    published in the last `days` days. Cheap — SequenceMatcher on a few
    dozen title pairs is microseconds."""
    from datetime import date, timedelta
    from .supabase_io import client
    try:
        sb = client()
    except Exception as e:
        log.warning("past-dedup skipped — Supabase unreachable: %s", e)
        return by_source
    start = (date.today() - timedelta(days=days)).isoformat()
    try:
        r = sb.table("redesign_stories").select(
            "source_title, category, published_date"
        ).eq("category", category).gte("published_date", start).execute()
        past_titles = [row.get("source_title") or "" for row in (r.data or [])]
    except Exception as e:
        log.warning("past-dedup query failed — skipping: %s", e)
        return by_source

    if not past_titles:
        log.info("  [%s] past-dedup: no prior stories in last %d days", category, days)
        return by_source

    result: dict[str, dict] = {}
    for name, bundle in by_source.items():
        kept: list[dict] = []
        for c in bundle["candidates"]:
            t = (c["winner"].get("title") or "")
            best = max((_title_similarity(t, pt) for pt in past_titles), default=0.0)
            if best >= threshold:
                log.info("  [%s/%s] past-dup drop %s (sim=%.2f) — %s",
                         category, name, c.get("slot"), best, t[:60])
            else:
                kept.append(c)
        result[name] = {"source": bundle["source"], "candidates": kept}
    return result


def pick_winners_with_dedup(by_source: dict[str, dict]) -> list[dict]:
    """Pick the highest-ranked surviving candidate per source, then
    cross-source dedup. When a pair of today's picks duplicates, drop the
    weaker source's current pick and promote its NEXT candidate (no extra
    DeepSeek-and-RSS round-trip — we already mined up to 4 per source)."""
    ptrs: dict[str, int] = {name: 0 for name in by_source}
    exhausted: set[str] = set()

    def current_for(name: str) -> dict | None:
        idx = ptrs.get(name, 0)
        cands = by_source[name].get("candidates") or []
        return cands[idx] if idx < len(cands) else None

    for _round in range(8):
        picks: list[tuple[str, dict]] = []
        for name in by_source:
            if name in exhausted:
                continue
            c = current_for(name)
            if c:
                picks.append((name, c))
        if len(picks) < 2:
            break
        briefs = [
            {"id": i, "title": c["winner"].get("title"),
             "source_name": name,
             "source_priority": getattr(by_source[name]["source"], "priority", 9),
             "excerpt": (c["winner"].get("body") or "")[:400]}
            for i, (name, c) in enumerate(picks)
        ]
        dup = check_duplicates(briefs)
        if dup.get("verdict") != "DUP_FOUND":
            break
        drop_id = dup.get("drop_suggestion")
        if drop_id is None and dup.get("duplicate_pairs"):
            pair = dup["duplicate_pairs"][0]["ids"]
            drop_id = max(pair, key=lambda i: briefs[i]["source_priority"])
        if drop_id is None or drop_id >= len(picks):
            break
        drop_name, drop_cand = picks[drop_id]
        log.info("  cross-source dup — promoting next candidate for [%s] "
                 "(was %s: %s)",
                 drop_name, drop_cand["slot"],
                 (drop_cand["winner"].get("title") or "")[:50])
        ptrs[drop_name] += 1
        if ptrs[drop_name] >= len(by_source[drop_name].get("candidates") or []):
            log.warning("  [%s] exhausted all candidates — skipping", drop_name)
            exhausted.add(drop_name)

    final: list[dict] = []
    for name, bundle in by_source.items():
        if name in exhausted:
            continue
        c = current_for(name)
        if c:
            final.append({
                "source": bundle["source"],
                "winner": c["winner"],
                "winner_slot": c["slot"],
            })
    return final


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

    mined_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
            common_listing = {
                "id": story_id,
                "source": src_name,
                "time_ago": time_ago,
                "mined_at": mined_at,                  # when this pipeline run captured the story
                "source_published_at": art.get("published") or "",
                "image_url": f"/{img_local}" if img_local else "",
                "category": category,
            }
            per_level_articles["easy"].append({**common_listing,
                "title": easy.get("headline") or art.get("title") or "",
                "summary": card_summary(easy),
            })
            per_level_articles["middle"].append({**common_listing,
                "title": middle.get("headline") or art.get("title") or "",
                "summary": card_summary(middle),
            })
            per_level_articles["cn"].append({**common_listing,
                "title": zh.get("headline") or "",
                "summary": zh.get("summary") or "",
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
                    "mined_at": mined_at,
                    "source_published_at": art.get("published") or "",
                    "source_name": src_name,
                    "source_url": src_url,
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

    log.info("=== AGGREGATE (up to 4 candidates per source) ===")
    news_bs = aggregate_category("News", news_sources(), news_backups(), run_news)
    science_bs = aggregate_category("Science", science_sources(), sci_backups(), run_sci)
    fun_bs = aggregate_category("Fun", fun_sources(), fun_backups(), run_fun)

    log.info("=== PAST-DEDUP (3-day lookback · title ≥80%% similar = dup) ===")
    news_bs = filter_past_duplicates("News", news_bs, days=3)
    science_bs = filter_past_duplicates("Science", science_bs, days=3)
    fun_bs = filter_past_duplicates("Fun", fun_bs, days=3)

    log.info("=== PICK + CROSS-SOURCE DEDUP (promote next candidate on dup) ===")
    news = pick_winners_with_dedup(news_bs)
    science = pick_winners_with_dedup(science_bs)
    fun = pick_winners_with_dedup(fun_bs)
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
