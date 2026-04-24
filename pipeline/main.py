"""KidsNews v2 pipeline — Steps 1-3 orchestrator."""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import config as cfg
from .discover import discover_category, image_head_check
from .vet import vet_candidates, vet_candidate, _combined_rank_key
from .read import read_candidates, read_candidate, _read_news_candidate
from .curator import curate_news
from .output import (
    download_image,
    sanitize_candidate_for_output,
    write_category_json,
    write_run_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("pipeline")


def _load_env() -> dict:
    load_dotenv(cfg.PROJECT_ROOT / ".env")
    missing = []
    for k in ("TAVILY_API_KEY", "DEEPSEEK_API_KEY"):
        if not os.getenv(k):
            missing.append(k)
    if missing:
        raise SystemExit(f"Missing required env vars: {missing}")
    return {
        "tavily": os.getenv("TAVILY_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "jina": os.getenv("JINA_API_KEY") or None,
    }


def _finalize_images_and_counts(
    category: str,
    candidates: list[dict],
    discover_meta: dict,
    out_dir: Path,
    boring_dropped: int,
    dropped_count: int,
) -> dict:
    """Shared post-processing: HEAD-check + download images, build counts/payload dict."""
    # Post-Step-3: image HEAD + download
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for c in candidates:
        img = c.get("image_url")
        if not img:
            continue
        lane = c.get("discovery_lane") or ""
        if lane.startswith("new_pipeline") or lane.startswith("tavily_"):
            if not c.get("image_filter_passed"):
                if image_head_check(img):
                    c["image_filter_passed"] = True

        if c.get("image_filter_passed"):
            local = download_image(img, images_dir, c["id"])
            if local:
                c["image_url"] = local

    post_verdicts = {"SAFE": 0, "CAUTION": 0, "REJECT": 0, "ERROR": 0}
    post_interest = {"ENGAGING": 0, "MEH": 0, "BORING": 0}
    for c in candidates:
        v = c.get("vetter_verdict") or "ERROR"
        post_verdicts[v] = post_verdicts.get(v, 0) + 1
        iv = c.get("interest_verdict") or "BORING"
        post_interest[iv] = post_interest.get(iv, 0) + 1
    selected_count = sum(1 for c in candidates if c.get("selected_for_publish"))
    tav_cands_ = [c for c in candidates
                  if (c.get("discovery_lane") or "").startswith(("new_pipeline", "tavily_"))]
    tav_with_image = [c for c in tav_cands_ if c.get("image_url")]
    tav_desc_matched = [c for c in tav_with_image if c.get("image_match_source") == "description_match"]
    image_match_pct = (
        round(100.0 * len(tav_desc_matched) / len(tav_with_image), 1)
        if tav_with_image else 0.0
    )
    counts = {
        "discovered_count": len(candidates),
        "safe_count": post_verdicts.get("SAFE", 0),
        "caution_count": post_verdicts.get("CAUTION", 0),
        "reject_count": post_verdicts.get("REJECT", 0) + post_verdicts.get("ERROR", 0),
        "engaging_count": post_interest.get("ENGAGING", 0),
        "meh_count": post_interest.get("MEH", 0),
        "boring_count": post_interest.get("BORING", 0),
        "boring_dropped_at_interest_filter": boring_dropped,
        "dropped_insufficient_content": dropped_count,
        "selected_count": selected_count,
        "image_match_pct_description": image_match_pct,
        "tavily_images_total": len(tav_with_image),
        "tavily_images_desc_matched": len(tav_desc_matched),
    }
    return counts


def run_news_category(
    keys: dict,
    out_dir: Path,
) -> tuple[dict, dict]:
    """News lane — redesigned 3-lane discovery + curator + aggressive clean + Stage 1 vet."""
    category = "News"
    log.info("===== %s (3-lane curator flow) =====", category)

    # Step 1 — 3-lane discover
    candidates, discover_meta = discover_category(category, keys["tavily"])
    group_counts = discover_meta.get("group_counts") or {}
    log.info(
        "Step 1 discovered %d candidates: A=%d B=%d C=%d",
        len(candidates),
        group_counts.get("A", 0),
        group_counts.get("B", 0),
        group_counts.get("C", 0),
    )

    # Step 2 — Curator (single DeepSeek call)
    curator_result, curator_api_calls, curator_warnings = curate_news(
        candidates, keys["deepseek"]
    )
    for w in curator_warnings:
        log.warning("Curator: %s", w)
    duplicates = curator_result.get("duplicates") or []
    picks = curator_result.get("picks") or []
    alternates = curator_result.get("alternates") or []
    log.info(
        "Step 2 curator: picks=%d duplicates=%d alternates=%d",
        len(picks), len(duplicates), len(alternates),
    )

    by_id = {c["id"]: c for c in candidates}

    # Annotate picks/alternates onto candidates
    pick_ids = [p["id"] for p in picks]
    alt_ids = [a["id"] for a in alternates]
    pick_reason_map = {p["id"]: p for p in picks}
    alt_reason_map = {a["id"]: a.get("reason") or "" for a in alternates}

    for c in candidates:
        c["selected_for_publish"] = False
        c["curator_reason"] = None
        c["is_hot_duplicate"] = False
        c["curator_source_group"] = None
        c["alternate_promoted"] = False
        c["safety_vet_dropped"] = False

    def _attach_pick_meta(cid: str, reason: str, is_hot: bool, src_group: str):
        cand = by_id.get(cid)
        if cand:
            cand["curator_reason"] = reason
            cand["is_hot_duplicate"] = bool(is_hot)
            cand["curator_source_group"] = src_group

    for p in picks:
        _attach_pick_meta(
            p["id"],
            p.get("reason") or "",
            bool(p.get("is_hot_duplicate")),
            p.get("source_group") or (by_id.get(p["id"], {}).get("discovery_group") or "?"),
        )

    # Step 3 + Step 4 per pick: read + aggressive clean, then safety+interest vet.
    # On drop, pull from alternates queue (up to 2 alternate attempts, per spec).
    deepseek_calls = curator_api_calls
    jina_calls = 0
    tavily_extract_calls = 0
    final_ids: list[str] = []
    alternates_used = 0
    MAX_ALT_FALLBACKS = 2
    alt_queue = list(alt_ids)
    processed_ids: set[str] = set()

    def _read_and_vet_one(cand: dict) -> tuple[bool, str]:
        """Read + vet one candidate. Returns (passed_bool, reason_if_dropped).

        For News: always goes through _read_news_candidate (Tavily/extract +
        aggressive clean) — skips read_candidate's SAFE/CAUTION gate since
        we're vetting AFTER reading in the curator flow.
        """
        nonlocal jina_calls, tavily_extract_calls, deepseek_calls
        tc, keep = _read_news_candidate(cand, keys["tavily"])
        tavily_extract_calls += tc
        if not keep:
            return False, "insufficient_content"
        # Safety + interest vet (Stage 1)
        deepseek_calls += vet_candidate(cand, keys["deepseek"])
        verdict = cand.get("vetter_verdict")
        interest = cand.get("interest_verdict")
        flags = cand.get("vetter_flags") or []
        # Promo / advertorial risk heuristic: treat vetter flags containing
        # "promo" / "advertorial" / "sponsored" with risk >= 3 as reject.
        advertorial_risk = 0
        for f in flags:
            fl = str(f).lower()
            if any(k in fl for k in ("promo", "advertorial", "sponsored", "affiliate")):
                advertorial_risk += 2
        # Explicit advertorial_risk from vetter_payload if present
        vp = cand.get("vetter_payload") or {}
        if isinstance(vp, dict):
            try:
                ar = int(vp.get("advertorial_risk") or 0)
            except Exception:
                ar = 0
            advertorial_risk = max(advertorial_risk, ar)
        cand["advertorial_risk"] = advertorial_risk
        if verdict == "REJECT" or verdict == "ERROR":
            return False, f"safety:{verdict}"
        if interest == "BORING":
            return False, "interest:BORING"
        if advertorial_risk >= 3:
            return False, f"advertorial_risk:{advertorial_risk}"
        return True, "ok"

    for pick_id in pick_ids:
        cand = by_id.get(pick_id)
        if not cand:
            continue
        processed_ids.add(pick_id)
        passed, reason = _read_and_vet_one(cand)
        if passed:
            final_ids.append(pick_id)
            continue
        cand["safety_vet_dropped"] = True
        log.warning("Pick %s dropped (%s); trying alternate", pick_id, reason)
        # Try alternates until one passes, up to MAX_ALT_FALLBACKS total attempts
        while alternates_used < MAX_ALT_FALLBACKS and alt_queue:
            alt_id = alt_queue.pop(0)
            if alt_id in processed_ids or alt_id in final_ids:
                continue
            alt_cand = by_id.get(alt_id)
            if not alt_cand:
                continue
            # R3 constraint: alternate host must not collide with already-selected picks
            used_hosts = {
                (by_id.get(fid, {}).get("source_name")
                 or (by_id.get(fid, {}).get("source_url") or ""))
                for fid in final_ids
            }
            alt_host = alt_cand.get("source_name") or alt_cand.get("source_url") or ""
            if alt_host in used_hosts:
                log.info("skipping alt %s: host collision (%s)", alt_id, alt_host)
                continue
            processed_ids.add(alt_id)
            alternates_used += 1
            alt_cand["alternate_promoted"] = True
            alt_cand["curator_reason"] = f"[alt fallback] {alt_reason_map.get(alt_id, '')}"
            alt_cand["curator_source_group"] = alt_cand.get("discovery_group") or "?"
            log.info("Promoting alternate %s (attempt %d)", alt_id, alternates_used)
            passed_alt, alt_reason = _read_and_vet_one(alt_cand)
            if passed_alt:
                final_ids.append(alt_id)
                break
            else:
                alt_cand["safety_vet_dropped"] = True
                log.warning("Alternate %s dropped (%s)", alt_id, alt_reason)

    # Mark finals
    for fid in final_ids:
        c = by_id.get(fid)
        if c:
            c["selected_for_publish"] = True

    log.info(
        "News curator flow: finals=%d alternates_used=%d duplicates=%d",
        len(final_ids), alternates_used, len(duplicates),
    )
    if len(final_ids) < 3:
        log.warning(
            "News final picks < 3 (%d) after exhausting alternates; publishing what we have",
            len(final_ids),
        )

    # For unreferenced candidates (not processed), we did NOT call vet on them.
    # Assign a conservative placeholder so downstream code + UI don't choke.
    for c in candidates:
        if c.get("vetter_verdict") is None:
            c["vetter_verdict"] = "UNVETTED"
            c["vetter_score"] = None
            c["vetter_flags"] = []
            c["vetter_payload"] = None
            c["vetter_notes"] = "Not curated; not read; not vetted."
            c["interest_scores"] = {"importance": 0, "fun_factor": 0, "kid_appeal": 0}
            c["interest_peak"] = 0
            c["interest_verdict"] = "UNVETTED"

    # Counts + images
    counts = _finalize_images_and_counts(
        category, candidates, discover_meta, out_dir,
        boring_dropped=0, dropped_count=0,
    )

    # Build payload
    payload = {
        "date": out_dir.name,
        "category": category,
        "query": discover_meta["query"],
        "topic": discover_meta["topic"],
        **counts,
        "curator": {
            "duplicates": duplicates,
            "picks": picks,
            "alternates": alternates,
            "warnings": curator_warnings,
            "alternates_used": alternates_used,
        },
        "candidates": [sanitize_candidate_for_output(c) for c in
                       sorted(candidates, key=lambda x: x["discovered_rank"])],
    }

    read_dist = {
        "tavily": 0, "tavily_extract": 0, "jina": 0,
        "html_scrape": 0, "snippet_only": 0, "none": 0,
    }
    for c in candidates:
        k = c.get("read_method") or "none"
        read_dist[k] = read_dist.get(k, 0) + 1

    stats = {
        **counts,
        "discovery_lane_counts": {
            "tavily_tier1": len([c for c in candidates if c.get("discovery_lane") == "tavily_tier1"]),
            "tavily_tier2": len([c for c in candidates if c.get("discovery_lane") == "tavily_tier2"]),
            "rss": len([c for c in candidates if c.get("discovery_lane") == "rss"]),
        },
        "group_counts": discover_meta.get("group_counts", {}),
        "read_method_counts": read_dist,
        "tavily_api_calls": discover_meta["tavily_api_calls"] + tavily_extract_calls,
        "tavily_extract_api_calls": tavily_extract_calls,
        "deepseek_api_calls": deepseek_calls,
        "jina_api_calls": jina_calls,
        "query": discover_meta["query"],
        "topic": discover_meta["topic"],
        "curator_alternates_used": alternates_used,
        "curator_duplicates_count": len(duplicates),
    }
    return payload, stats


def run_category(
    category: str,
    keys: dict,
    out_dir: Path,
) -> tuple[dict, dict]:
    """Returns (category_payload, stats_dict)."""
    log.info("===== %s =====", category)

    # Step 1
    candidates, discover_meta = discover_category(category, keys["tavily"])
    log.info("Step 1 discovered %d candidates (tavily=%d rss=%d)",
             len(candidates),
             discover_meta["tavily_count"], discover_meta["rss_count"])

    # Step 2 — vet all discovered candidates
    deepseek_calls = vet_candidates(candidates, keys["deepseek"])
    verdicts = {"SAFE": 0, "CAUTION": 0, "REJECT": 0, "ERROR": 0}
    interest_verdicts = {"ENGAGING": 0, "MEH": 0, "BORING": 0}
    for c in candidates:
        verdicts[c["vetter_verdict"]] = verdicts.get(c["vetter_verdict"], 0) + 1
        iv = c.get("interest_verdict") or "BORING"
        interest_verdicts[iv] = interest_verdicts.get(iv, 0) + 1
    log.info("Step 2 safety verdicts: %s; interest verdicts: %s", verdicts, interest_verdicts)

    # Drop BORING candidates alongside REJECTs BEFORE the read step (saves Jina calls).
    pre_interest_filter = len(candidates)
    kept_candidates: list[dict] = []
    boring_dropped = 0
    reject_skipped = 0
    for c in candidates:
        if c.get("vetter_verdict") in {"REJECT", "ERROR"}:
            # Keep in list so we still emit the candidate card (marked rejected).
            kept_candidates.append(c)
            reject_skipped += 1
            continue
        if c.get("interest_verdict") == "BORING":
            # Drop outright — not worth kids' time.
            boring_dropped += 1
            log.info(
                "Dropping BORING candidate id=%s peak=%s title=%s",
                c.get("id"), c.get("interest_peak"), (c.get("title") or "")[:80],
            )
            continue
        kept_candidates.append(c)
    log.info(
        "Interest filter: pre=%d post=%d (boring_dropped=%d, reject_kept_for_display=%d)",
        pre_interest_filter, len(kept_candidates), boring_dropped, reject_skipped,
    )
    candidates = kept_candidates

    # Step 3 — read full text for SAFE/CAUTION (non-BORING)
    pre_read_count = len(candidates)
    jina_calls, tavily_extract_calls, candidates = read_candidates(
        candidates, keys["jina"], category, tavily_api_key=keys["tavily"],
    )
    dropped_count = pre_read_count - len(candidates)
    log.info(
        "Step 3 jina calls: %d; tavily_extract calls: %d; kept=%d (dropped=%d) after read-step",
        jina_calls, tavily_extract_calls, len(candidates), dropped_count,
    )

    # Re-rank vetted_rank among remaining SAFE/CAUTION (non-BORING) after read-step drops,
    # using the combined (safety, -interest, -hotness, discovered) key.
    survivors = [
        c for c in candidates
        if c.get("vetter_verdict") in {"SAFE", "CAUTION"}
        and c.get("interest_verdict") != "BORING"
    ]
    survivors.sort(key=_combined_rank_key)
    for i, c in enumerate(survivors, 1):
        c["vetted_rank"] = i

    # ---- Post-vet: pick top N for publish with mix-rule (Fix 5) ----
    for c in candidates:
        c["selected_for_publish"] = False
    top_n: list[dict] = list(survivors[: cfg.FINAL_PUBLISH_COUNT])
    # Mix rule: if top-N is all one lane AND the other lane has >= 1 candidate,
    # swap the worst-ranked top-N pick with the best-ranked from the missing lane.
    if len(top_n) >= 2:
        lanes_present = {c.get("discovery_lane") for c in top_n}
        both_lanes_exist = any(c.get("discovery_lane") == "new_pipeline" for c in survivors) and \
                           any(c.get("discovery_lane") == "rss" for c in survivors)
        if both_lanes_exist and len(lanes_present) == 1:
            missing_lane = "rss" if "new_pipeline" in lanes_present else "new_pipeline"
            rss_cands = [c for c in survivors if c.get("discovery_lane") == missing_lane]
            if rss_cands:
                best_from_missing = rss_cands[0]  # survivors are already ranked
                # Drop the worst-ranked (last) of current top_n, add the best from missing lane
                dropped = top_n.pop()
                top_n.append(best_from_missing)
                log.info(
                    "Mix-rule: swapped worst top-N (id=%s, lane=%s) with best of %s lane (id=%s)",
                    dropped.get("id"), dropped.get("discovery_lane"),
                    missing_lane, best_from_missing.get("id"),
                )
    for c in top_n:
        c["selected_for_publish"] = True
    log.info(
        "Post-vet selection: picked %d of %d survivors for publish (category=%s)",
        len(top_n), len(survivors), category,
    )
    if len(top_n) < cfg.FINAL_PUBLISH_COUNT:
        log.warning(
            "Category %s has only %d publishable candidates (target=%d)",
            category, len(top_n), cfg.FINAL_PUBLISH_COUNT,
        )

    # Post-Step-3: if a Tavily candidate's image_url didn't HEAD-pass during discovery,
    # verify once more here. (Tavily sets image_filter_passed optimistically; we check.)
    # Then download images for all candidates that have an image_url that passes.
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for c in candidates:
        img = c.get("image_url")
        if not img:
            continue
        # If it's a Tavily candidate and filter wasn't confirmed, try HEAD now
        if c["discovery_lane"] == "new_pipeline" and not c.get("image_filter_passed"):
            if image_head_check(img):
                c["image_filter_passed"] = True
            else:
                # keep the url but mark filter not passed; may still display
                pass

        if c.get("image_filter_passed"):
            local = download_image(img, images_dir, c["id"])
            if local:
                c["image_url"] = local  # replace with local relative path

    # Build category payload (recount verdicts after read-step drops)
    post_verdicts = {"SAFE": 0, "CAUTION": 0, "REJECT": 0, "ERROR": 0}
    post_interest = {"ENGAGING": 0, "MEH": 0, "BORING": 0}
    for c in candidates:
        v = c.get("vetter_verdict") or "ERROR"
        post_verdicts[v] = post_verdicts.get(v, 0) + 1
        iv = c.get("interest_verdict") or "BORING"
        post_interest[iv] = post_interest.get(iv, 0) + 1
    selected_count = sum(1 for c in candidates if c.get("selected_for_publish"))
    # Image-match diagnostics (Tavily candidates only)
    tav_cands_ = [c for c in candidates if c.get("discovery_lane") == "new_pipeline"]
    tav_with_image = [c for c in tav_cands_ if c.get("image_url")]
    tav_desc_matched = [c for c in tav_with_image if c.get("image_match_source") == "description_match"]
    image_match_pct = (
        round(100.0 * len(tav_desc_matched) / len(tav_with_image), 1)
        if tav_with_image else 0.0
    )
    counts = {
        "discovered_count": len(candidates),
        "safe_count": post_verdicts.get("SAFE", 0),
        "caution_count": post_verdicts.get("CAUTION", 0),
        "reject_count": post_verdicts.get("REJECT", 0) + post_verdicts.get("ERROR", 0),
        "engaging_count": post_interest.get("ENGAGING", 0),
        "meh_count": post_interest.get("MEH", 0),
        "boring_count": post_interest.get("BORING", 0),
        "boring_dropped_at_interest_filter": boring_dropped,
        "dropped_insufficient_content": dropped_count,
        "selected_count": selected_count,
        "image_match_pct_description": image_match_pct,
        "tavily_images_total": len(tav_with_image),
        "tavily_images_desc_matched": len(tav_desc_matched),
    }
    payload = {
        "date": out_dir.name,
        "category": category,
        "query": discover_meta["query"],
        "topic": discover_meta["topic"],
        **counts,
        "candidates": [sanitize_candidate_for_output(c) for c in
                       sorted(candidates, key=lambda x: x["discovered_rank"])],
    }

    # Read-method distribution
    read_dist = {
        "tavily": 0, "tavily_extract": 0, "jina": 0,
        "html_scrape": 0, "snippet_only": 0, "none": 0,
    }
    for c in candidates:
        k = c.get("read_method") or "none"
        read_dist[k] = read_dist.get(k, 0) + 1

    stats = {
        **counts,
        "discovery_lane_counts": {
            "new_pipeline": discover_meta["tavily_count"],
            "rss": discover_meta["rss_count"],
        },
        "read_method_counts": read_dist,
        "tavily_api_calls": discover_meta["tavily_api_calls"] + tavily_extract_calls,
        "tavily_extract_api_calls": tavily_extract_calls,
        "deepseek_api_calls": deepseek_calls,
        "jina_api_calls": jina_calls,
        "query": discover_meta["query"],
        "topic": discover_meta["topic"],
    }
    return payload, stats


def main() -> int:
    keys = _load_env()

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    out_dir = cfg.TEST_OUTPUT_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    started = now
    per_cat: dict[str, dict] = {}
    totals = {"tavily": 0, "deepseek": 0, "jina": 0}

    for category in cfg.CATEGORIES:
        try:
            if category == "News":
                payload, stats = run_news_category(keys, out_dir)
            else:
                payload, stats = run_category(category, keys, out_dir)
            write_category_json(out_dir, category, payload)
            per_cat[category] = stats
            totals["tavily"] += stats["tavily_api_calls"]
            totals["deepseek"] += stats["deepseek_api_calls"]
            totals["jina"] += stats["jina_api_calls"]
        except Exception as e:
            log.exception("Category %s failed: %s", category, e)
            per_cat[category] = {"error": str(e)}

    finished = datetime.now(timezone.utc)
    summary = {
        "date": date_str,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_sec": round((finished - started).total_seconds(), 2),
        "api_calls": totals,
        "per_category": per_cat,
    }
    write_run_summary(out_dir, summary)

    log.info("\n\n===== RUN SUMMARY =====")
    log.info(json.dumps(summary, indent=2))
    log.info("Output: %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
