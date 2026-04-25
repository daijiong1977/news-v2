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
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .news_rss_core import (CALL_STATS, check_duplicates, detail_enrich,
                              reset_call_stats, run_source_phase_a,
                              tri_variant_rewrite)
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
    """Per-category cross-source dedup. Picks each source's highest-ranked
    surviving candidate, runs cross-source check_duplicates, on dup
    promotes the next candidate from the weaker source. Operates within a
    single category — see `pick_all_winners_with_xcat_dedup` for the
    unified pass that also catches News-vs-Fun overlaps."""
    return _pick_with_dedup_unified({"_": by_source}, cat_priority=None)["_"]


# Fun > Science > News. On a cross-category dup the lower-priority
# (numerically higher) category drops + promotes its next candidate.
# Editorial reasoning: News has 3 sources fresh every day and the easiest
# pool to swap from; Fun is curated per-weekday (BBC Tennis on Tue/Sat/Sun,
# specific topical feeds) and we want to preserve those picks. Science
# sits in the middle.
CAT_PRIORITY = {"Fun": 1, "Science": 2, "News": 3}


def pick_all_winners_with_xcat_dedup(buckets_by_cat: dict[str, dict]) -> dict[str, list[dict]]:
    """Greedy per-round dedup (kept as a fallback). Use
    holistic_curate_picks() instead for the production path."""
    return _pick_with_dedup_unified(buckets_by_cat, cat_priority=CAT_PRIORITY)


# ---------------------------------------------------------------------------
# Holistic curation — send ALL candidates to DeepSeek in one call, let it
# pick 3 per category with cross-cat dedup + within-cat topic diversity.
# ---------------------------------------------------------------------------

CURATOR_SYSTEM_PROMPT = """You are the Editor-in-Chief of "News Oh, Ye!", a daily
news site for kids ages 8-13. The pipeline mined a pre-vetted pool of
candidates across 3 categories. YOUR JOB: deliver EXACTLY 3 stories per
category — News, Science, Fun — for a total of 9 stories.

Output contract is STRICT: 3 picks for News + 3 picks for Science +
3 picks for Fun. ALWAYS. Returning fewer is a failure.

ALGORITHM you must follow:

  STEP 1 — Initial picks. Start with choice_1 from each of the 3 sources
  in each category (so 3 picks per cat, 9 total).

  STEP 2 — Cross-category dedup. If two categories' picks cover the same
  event (e.g. an Alcaraz tennis injury appearing in News from PBS AND in
  Fun from BBC Tennis on a Tue/Sat/Sun), one MUST be replaced. Tiebreak:
      News × Fun     → keep the Fun pick, REPLACE News' pick from its alternates
      News × Science → keep the Science pick, REPLACE News' pick
      Fun  × Science → keep the Fun pick, REPLACE Science' pick
  Replace by swapping in the next available candidate from the SAME
  source (its choice_2, then alternate_0/1) — so the losing category
  still ends up with 3 picks. If that source has no more candidates,
  swap in any other candidate from a different source in that category.

  STEP 3 — Within-category topic diversity. If your 3 picks in one
  category are all about the same theme (3 election stories, 3 climate
  stories, etc.), swap one to a different topic from the alternates.
  Goal: 3 different topic clusters per category.

  STEP 4 — Final check. You must end up with 9 distinct stories:
  3 News + 3 Science + 3 Fun. No cross-cat dups. Diverse topics within
  each cat. Output each pick as its `cid`.

PREFERENCES (use to break ties between equally-valid options):
  · Lower slot wins (choice_1 > choice_2 > alternate_0 > alternate_1).
  · Different sources within a cat are preferred over two picks from
    the same source on the same day.

DEGRADATION (only when the pool is genuinely too thin to satisfy the
contract): if a category truly has fewer than 3 distinct
non-duplicate stories available across all its candidates, you may
return 2 in that category. Never 1 or 0 unless that category had no
candidates at all in the input.

OUTPUT — valid JSON only, no markdown fences:
{
  "picks": {
    "News":    [<cid>, <cid>, <cid>],
    "Science": [<cid>, <cid>, <cid>],
    "Fun":     [<cid>, <cid>, <cid>]
  },
  "reasoning": "1-3 sentences: which cross-cat dups you caught, which
                within-cat topic-diversity swaps you made, and any
                slot-promotion that wasn't choice_1."
}"""


def _build_curator_input(buckets_by_cat: dict[str, dict]) -> tuple[str, dict[int, dict]]:
    """Build the user message + a registry mapping cid → candidate metadata."""
    registry: dict[int, dict] = {}
    cid = 0
    by_cat_lines: dict[str, list[str]] = {cat: [] for cat in buckets_by_cat}

    for cat, by_src in buckets_by_cat.items():
        for src_name, bundle in by_src.items():
            for cand in bundle.get("candidates") or []:
                art = cand["winner"]
                title = (art.get("title") or "")[:240]
                excerpt = (art.get("body") or "")[:400].replace("\n", " ")
                vet = art.get("_vet_info") or {}
                interest = vet.get("interest") or {}
                imp = interest.get("importance", "?")
                fun = interest.get("fun_factor", "?")
                kid = interest.get("kid_appeal", "?")
                line = (f"  [cid={cid}] slot={cand.get('slot','?')} src={src_name} "
                        f"importance={imp} fun={fun} kid_appeal={kid}\n"
                        f"     title: {title}\n"
                        f"     excerpt: {excerpt}")
                by_cat_lines[cat].append(line)
                registry[cid] = {
                    "cat": cat,
                    "src_name": src_name,
                    "source": bundle["source"],
                    "slot": cand.get("slot", "choice_1"),
                    "winner": art,
                }
                cid += 1

    parts = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
    for cat in ("News", "Science", "Fun"):
        lines = by_cat_lines.get(cat, [])
        parts.append(f"=== {cat} ({len(lines)} candidates) ===")
        if not lines:
            parts.append("  (none)")
        else:
            parts.extend(lines)
        parts.append("")
    parts.append("Pick 3 per category. Return the JSON shape from the system prompt.")
    return "\n".join(parts), registry


def holistic_curate_picks(buckets_by_cat: dict[str, dict]) -> dict[str, list[dict]]:
    """Single LLM call that sees all candidates and picks 3 per category
    with cross-cat dedup + within-cat topic diversity in one shot.

    Falls back to the greedy per-round dedup if the curator call fails or
    returns malformed picks."""
    user_msg, registry = _build_curator_input(buckets_by_cat)
    if not registry:
        log.warning("curator: no candidates — nothing to pick")
        return {cat: [] for cat in buckets_by_cat}

    try:
        # Reasoner mode (thinking) — this is exactly the holistic
        # cross-cluster reasoning task that benefits from an explicit
        # reasoning pass.
        from .news_rss_core import deepseek_reasoner_call
        res = deepseek_reasoner_call(CURATOR_SYSTEM_PROMPT, user_msg,
                                       max_tokens=4000)
    except Exception as e:  # noqa: BLE001
        log.warning("curator failed (%s) — falling back to greedy dedup", e)
        return pick_all_winners_with_xcat_dedup(buckets_by_cat)

    picks = (res or {}).get("picks") or {}
    reasoning = (res or {}).get("reasoning") or ""
    if reasoning:
        log.info("curator reasoning: %s", reasoning[:400])

    # Validate shape — picks must be dict[cat → list of int cids that
    # exist in registry, all from the right category]
    out: dict[str, list[dict]] = {cat: [] for cat in buckets_by_cat}
    seen_cids: set[int] = set()
    for cat in buckets_by_cat:
        for cid in (picks.get(cat) or []):
            if not isinstance(cid, int):
                continue
            if cid in seen_cids:
                log.warning("curator returned cid=%d twice — skipping dup", cid)
                continue
            info = registry.get(cid)
            if not info:
                log.warning("curator returned unknown cid=%d — skipping", cid)
                continue
            if info["cat"] != cat:
                log.warning("curator put cid=%d in %s but it's a %s candidate",
                             cid, cat, info["cat"])
                continue
            seen_cids.add(cid)
            out[cat].append({
                "source": info["source"],
                "winner": info["winner"],
                "winner_slot": info["slot"],
            })

    # Log the picks succinctly so the run log is readable
    for cat, ws in out.items():
        slots = ", ".join(f"{w['source'].name}/{w['winner_slot']}" for w in ws)
        log.info("  curator [%s] → %d picks: %s", cat, len(ws), slots or "(none)")

    # Safety net. The contract is 3 per cat (9 total). Anything short of
    # that — including a single short category — falls back to the greedy
    # per-round dedup so we don't ship a degraded run unnoticed. The
    # greedy path also fills toward 3 via candidate promotion.
    short_cats = [cat for cat, picks in out.items() if len(picks) < 3]
    total = sum(len(v) for v in out.values())
    if short_cats:
        # If a category had fewer than 3 candidates available in the input
        # AT ALL, accept the curator's degradation — the greedy fallback
        # can't conjure picks that don't exist.
        truly_thin = []
        for cat in short_cats:
            cand_count = sum(len(b.get("candidates") or [])
                              for b in buckets_by_cat.get(cat, {}).values())
            if cand_count < 3:
                truly_thin.append(cat)
        if set(short_cats) <= set(truly_thin):
            log.warning("curator: %s short due to thin input (%d total picks)",
                         short_cats, total)
            return out
        log.warning("curator returned %d picks (short cats: %s) — "
                     "falling back to greedy", total, short_cats)
        return pick_all_winners_with_xcat_dedup(buckets_by_cat)
    return out


def _pick_with_dedup_unified(
    buckets_by_cat: dict[str, dict],
    cat_priority: dict[str, int] | None,
) -> dict[str, list[dict]]:
    """Workhorse for both within-cat (per-cat) and cross-cat dedup.

    `buckets_by_cat = {cat: {source_name: {source, candidates}}}`. For
    within-cat-only mode, pass a single-cat dict; cat_priority=None
    disables the cross-cat tiebreaker (fall back to source.priority).
    Returns `{cat: [{source, winner, winner_slot}]}`.
    """
    # Flat state list: one entry per (cat, source).
    state = []
    for cat, by_src in buckets_by_cat.items():
        for src_name, bundle in by_src.items():
            state.append({
                "cat": cat,
                "src_name": src_name,
                "source": bundle["source"],
                "candidates": bundle.get("candidates") or [],
                "ptr": 0,
                "exhausted": False,
            })

    def _current(s):
        if s["exhausted"] or s["ptr"] >= len(s["candidates"]):
            return None
        return s["candidates"][s["ptr"]]

    for _round in range(15):  # cap loops for adversarial inputs
        active = [(i, s) for i, s in enumerate(state) if _current(s) is not None]
        if len(active) < 2:
            break
        briefs = [
            {"id": k, "title": _current(s)["winner"].get("title"),
             "source_name": s["src_name"],
             "source_priority": getattr(s["source"], "priority", 9),
             "category": s["cat"],
             "excerpt": (_current(s)["winner"].get("body") or "")[:400]}
            for k, (_, s) in enumerate(active)
        ]
        dup = check_duplicates(briefs)
        if dup.get("verdict") != "DUP_FOUND":
            break

        # Pick which of the duplicated pair to drop. Tiebreak ordering:
        #   1. cross-cat: drop the LOWER-priority category (News=1 wins)
        #   2. within-cat: drop the HIGHER-numbered source.priority (lower-priority source loses)
        pair = dup.get("duplicate_pairs", [{}])[0].get("ids") or []
        if len(pair) < 2:
            drop_id = dup.get("drop_suggestion")
            if drop_id is None or drop_id >= len(active):
                break
        else:
            i, j = pair[0], pair[1]
            if i >= len(active) or j >= len(active):
                break
            si, sj = active[i][1], active[j][1]

            def _tiebreak(s):
                # Higher number = "drop me first"
                cat_rank = (cat_priority.get(s["cat"], 99) if cat_priority else 0)
                src_rank = getattr(s["source"], "priority", 9)
                return (cat_rank, src_rank)

            drop_id = j if _tiebreak(sj) > _tiebreak(si) else i

        drop_state = active[drop_id][1]
        keep_state = active[1 - drop_id][1] if len(pair) >= 2 else None
        keep_label = (f"[{keep_state['cat']}/{keep_state['src_name']}]"
                      if keep_state and cat_priority else "(other)")
        log.info("  dedup drop [%s/%s] %s (promoting next candidate) — kept over %s",
                 drop_state["cat"], drop_state["src_name"],
                 (_current(drop_state)["winner"].get("title") or "")[:50],
                 keep_label)
        drop_state["ptr"] += 1
        if drop_state["ptr"] >= len(drop_state["candidates"]):
            log.warning("  [%s/%s] exhausted candidates — skipping",
                        drop_state["cat"], drop_state["src_name"])
            drop_state["exhausted"] = True

    # Assemble results per category, preserving source order.
    out: dict[str, list[dict]] = {cat: [] for cat in buckets_by_cat}
    for s in state:
        c = _current(s)
        if c is None:
            continue
        out[s["cat"]].append({
            "source": s["source"],
            "winner": c["winner"],
            "winner_slot": c["slot"],
        })
    return out


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

def _category_summary(cat: str, by_source: dict, winners: list[dict]) -> dict:
    """Per-category telemetry snapshot — answers 'was this run healthy?'."""
    candidate_total = sum(len(b.get("candidates") or []) for b in by_source.values())
    winners_used_split = bool(by_source.get("_split_batch_used"))  # placeholder
    used_backup = sum(1 for w in winners if w.get("used_backup"))
    sources_with_zero = [name for name, b in by_source.items()
                         if not (b.get("candidates") or [])]
    return {
        "category": cat,
        "winners": len(winners),
        "sources_active": len(by_source),
        "sources_exhausted": sources_with_zero,
        "winners_used_backup_source": used_backup,
        "total_candidates_mined": candidate_total,
    }


def _phase(t0: float) -> float:
    """Seconds elapsed since t0, rounded to 0.1."""
    return round(time.monotonic() - t0, 1)


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    website_dir = Path(__file__).resolve().parent.parent / "website"

    # Telemetry — every phase / category event lands here. Persisted to
    # `redesign_runs.telemetry` (jsonb) so we can answer "was this run
    # healthy?" without grepping CI logs.
    reset_call_stats()
    telemetry: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phases": {},          # phase_name → {seconds: float, notes: str|None}
        "per_category": {},    # cat → snapshot dict
        "warnings": [],        # human-readable list of degraded paths
        "llm_calls": dict(CALL_STATS),  # filled in at end
        "version": "1",
    }
    t_run = time.monotonic()

    run_id = insert_run({"run_date": today, "status": "running"})
    if not run_id:
        log.warning("insert_run failed — continuing without DB persistence")

    def _set_phase(name: str, t0: float, **extra) -> None:
        telemetry["phases"][name] = {"seconds": _phase(t0), **extra}
        if run_id:
            update_run(run_id, {"telemetry": telemetry})

    # ---- AGGREGATE ----
    t = time.monotonic()
    log.info("=== AGGREGATE (up to 4 candidates per source) ===")
    news_bs = aggregate_category("News", news_sources(), news_backups(), run_news)
    science_bs = aggregate_category("Science", science_sources(), sci_backups(), run_sci)
    fun_bs = aggregate_category("Fun", fun_sources(), fun_backups(), run_fun)
    _set_phase("aggregate", t,
               candidate_counts={"News": sum(len(b["candidates"]) for b in news_bs.values()),
                                 "Science": sum(len(b["candidates"]) for b in science_bs.values()),
                                 "Fun": sum(len(b["candidates"]) for b in fun_bs.values())})

    # ---- PAST-DEDUP ----
    t = time.monotonic()
    log.info("=== PAST-DEDUP (3-day lookback · title ≥80%% similar = dup) ===")
    news_bs = filter_past_duplicates("News", news_bs, days=3)
    science_bs = filter_past_duplicates("Science", science_bs, days=3)
    fun_bs = filter_past_duplicates("Fun", fun_bs, days=3)
    _set_phase("past_dedup", t)

    # ---- HOLISTIC CURATION ----
    # Single LLM call sees ALL candidates (~36) + vet scores. Picks 3 per
    # cat with cross-cat dedup + within-cat topic diversity in one shot.
    # Falls back to the greedy per-round dedup automatically if the
    # curator returns short or fails.
    t = time.monotonic()
    log.info("=== CURATOR (1 call, picks 3-per-cat with cross-cat dedup + diversity) ===")
    cat_buckets = {"News": news_bs, "Science": science_bs, "Fun": fun_bs}
    picked = holistic_curate_picks(cat_buckets)
    news = picked.get("News", [])
    science = picked.get("Science", [])
    fun = picked.get("Fun", [])
    stories_by_cat = {"News": news, "Science": science, "Fun": fun}
    for cat, ws in stories_by_cat.items():
        log.info("  %s: %d winners", cat, len(ws))
        snapshot = _category_summary(cat, cat_buckets[cat], ws)
        telemetry["per_category"][cat] = snapshot
        if snapshot["winners"] < 3:
            telemetry["warnings"].append(
                f"{cat}: shipped {snapshot['winners']} (<3) "
                f"after dedup — {len(snapshot['sources_exhausted'])} exhausted"
            )
    _set_phase("pick", t)

    # ---- IMAGES ----
    t = time.monotonic()
    log.info("=== IMAGES (optimize + upload) ===")
    for cat, ws in stories_by_cat.items():
        log.info("[%s] processing %d images", cat, len(ws))
        process_images(ws, today, website_dir)
    _set_phase("images", t)

    # ---- REWRITE + ENRICH ----
    t = time.monotonic()
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
            telemetry["per_category"].setdefault(cat, {}).update({
                "variants": len(v), "detail_slots": len(d),
            })
            # Detect partial enrichment (split-batch produced fewer than ideal).
            ideal = len(ws) * 2
            if len(d) < ideal:
                w = (f"{cat}: enrich produced {len(d)}/{ideal} slots — "
                     "split-batch path or partial recovery")
                telemetry["warnings"].append(w)
                telemetry["per_category"][cat]["partial_enrich"] = True
        except Exception as e:  # noqa: BLE001
            log.error("  [%s] rewrite/enrich FAILED: %s", cat, e)
            failures.append(f"{cat}: {e}")
    _set_phase("rewrite_enrich", t)

    if failures:
        msg = f"{len(failures)} category failures: " + " | ".join(failures)
        telemetry["warnings"].append(msg)
        if run_id:
            update_run(run_id, {"status": "failed",
                                "finished_at": datetime.now(timezone.utc).isoformat(),
                                "notes": msg, "telemetry": telemetry})
        log.error("Aborting — %s", msg)
        raise SystemExit(1)

    # ---- EMIT + PERSIST ----
    t = time.monotonic()
    log.info("=== EMIT v1-shape payload files ===")
    emit_v1_shape(stories_by_cat, variants_by_cat, details_by_cat, today, website_dir)
    _set_phase("emit", t)

    # ---- PDF EXPORT (1 per story × 2 levels = up to 18) ----
    t = time.monotonic()
    log.info("=== PDF EXPORT (printable per article) ===")
    try:
        from .pdf_export import generate_all_pdfs
        pdf_count = generate_all_pdfs(stories_by_cat, today, website_dir)
        _set_phase("pdf_export", t, count=pdf_count)
    except Exception as e:  # noqa: BLE001
        log.warning("PDF export failed (non-fatal): %s", e)
        _set_phase("pdf_export", t, error=str(e)[:200])

    t = time.monotonic()
    log.info("=== PERSIST TO SUPABASE ===")
    count = 0
    if run_id:
        count = persist_to_supabase(stories_by_cat, variants_by_cat, today, run_id)
        update_run(run_id, {"status": "persisted",
                            "notes": f"stories persisted: {count}",
                            "telemetry": telemetry})
    _set_phase("persist", t, stories_persisted=count)

    # ---- PACK + UPLOAD ----
    t = time.monotonic()
    log.info("=== PACK + UPLOAD ZIP (deploy trigger) ===")
    upload_ok = False
    upload_err: str | None = None
    try:
        from .pack_and_upload import main as _pack_upload
        _pack_upload()
        upload_ok = True
    except SystemExit as e:
        upload_err = f"pack_and_upload aborted (SystemExit {e.code})"
        log.error(upload_err)
    except Exception as e:  # noqa: BLE001
        upload_err = f"pack_and_upload exception: {e}"
        log.error(upload_err)
    _set_phase("pack_upload", t, ok=upload_ok, error=upload_err)

    # ---- TERMINAL STATUS ----
    telemetry["llm_calls"] = dict(CALL_STATS)
    if any(CALL_STATS.get(k, 0) for k in ("reasoner_truncated", "reasoner_repaired")):
        if CALL_STATS.get("reasoner_truncated"):
            telemetry["warnings"].append(
                f"reasoner truncated {CALL_STATS['reasoner_truncated']} time(s) "
                "— hit max_tokens, split-batch path used"
            )
        if CALL_STATS.get("reasoner_repaired"):
            telemetry["warnings"].append(
                f"reasoner repaired {CALL_STATS['reasoner_repaired']} time(s) "
                "(deterministic JSON fix)"
            )
    if run_id:
        terminal = {"finished_at": datetime.now(timezone.utc).isoformat(),
                    "telemetry": telemetry}
        if upload_ok:
            if telemetry["warnings"]:
                terminal["status"] = "completed_with_warnings"
                terminal["notes"] = (f"stories persisted: {count}; deployed; "
                                       f"warnings: {len(telemetry['warnings'])}")
            else:
                terminal["status"] = "completed"
                terminal["notes"] = f"stories persisted: {count}; deployed"
        else:
            terminal["status"] = "deploy_failed"
            terminal["notes"] = (f"stories persisted: {count}; "
                                  f"deploy failed: {upload_err}")
        update_run(run_id, terminal)

    log.info("=== DONE (%.1fs total) ===", _phase(t_run))
    total_stories = sum(len(ws) for ws in stories_by_cat.values())
    log.info("Run: %s · Stories: %d · DB persisted: %d · Deployed: %s · Warnings: %d",
             run_id or "(no DB)", total_stories, count, upload_ok,
             len(telemetry["warnings"]))
    for w in telemetry["warnings"]:
        log.warning("  ⚠  %s", w)
    if not upload_ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
