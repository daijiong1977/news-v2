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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from .news_rss_core import (CALL_STATS, check_duplicates, detail_enrich,
                              fetch_source_entries, filter_safe_rewrites,
                              reset_call_stats, run_source_phase_a,
                              tri_variant_rewrite)
from .run_date import pipeline_run_date
from .image_optimize import fetch_and_optimize
from .supabase_io import insert_run, insert_story, update_run, upload_image
from .news_aggregate import run_source as run_news
from .science_aggregate import run_source as run_sci
from .fun_aggregate import run_source as run_fun

# Phase 2: DB-driven config + checkpoints. Imported as a module so we can
# refer to e.g. `db_config.load_sources` per-call without re-importing.
from . import checkpoints as ckpt
from . import db_config
from .editorial_policy import (editorial_exclusion, publisher_key,
                               prefer_science_publishers, SCIENCE_MIN_PUBLISHERS)
from .editorial_policy import (low_fun_value, important_news, prefer_important_news,
                               explicit_section, below_quality_floor)
from .editorial_policy import prefer_final_editorial_diversity
from .publication_history import (PublicationHistoryGuard, HistoryReviewBudget,
                                  winner_brief, assert_history_clear)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("full-round")

# Wider, metadata-first sampling for Fun gives Jev more independent sports,
# music and culture candidates. Keep News/Science at their existing limit;
# News has only four enabled feeds, and downstream curator/rewrite caps do not
# change. Tune here after comparing source funnel and run-time telemetry.
PHASE_A_SOURCE_LIMITS = {"Fun": 10}
PHASE_A_DEFAULT_SOURCE_LIMIT = 8


def phase_a_source_limit(category: str) -> int:
    return PHASE_A_SOURCE_LIMITS.get(category, PHASE_A_DEFAULT_SOURCE_LIMIT)


# -------------------------------------------------------------------
# 1) Aggregate 3 categories
# -------------------------------------------------------------------

def aggregate_category(label: str, pool: list, runner,
                       want: int = 3,
                       max_attempts: int | None = None) -> dict[str, dict]:
    """Iterate `pool` (in load_sources priority order) through `runner`
    until `want` distinct sources have contributed candidates OR
    `max_attempts` sources have been tried.

    `runner` returns dict | None (None when RSS fetch failed or fewer
    than 2 viable candidates). When None comes back, we skip and try
    the next source — this is the runtime-backfill complement to
    cadence-aware load_sources. Cadence picks "which sources are
    eligible today"; this loop picks "if today's first picks fail to
    produce content, try the next ones".

    Why this matters: 2026-05-04 dry-run picked 3 Fun sources by
    cadence (Polygon + 2 Smithsonians). Both Smithsonians had 0
    articles past the 5-day RSS freshness filter, so all 3 winners
    came from Polygon (gaming-only). With backfill, we'd have tried
    DOGOnews / NG Kids / BBC Swimming / etc until 3 sources contributed.

    Args:
      pool: full prioritized pool from db_config.load_sources(cat, n=10).
      want: number of contributing sources required (default 3).
      max_attempts: cap on iteration. None = try every source in pool.
    """
    cap = max_attempts if max_attempts is not None else len(pool)
    log.info("[%s] aggregating, want=%d, pool=%d, max_attempts=%d",
             label, want, len(pool), cap)

    out: dict[str, dict] = {}
    attempts = 0
    for src_obj in pool[:cap]:
        if len(out) >= want:
            log.info("[%s] target %d contributors reached after %d attempts",
                     label, want, attempts)
            break
        attempts += 1
        res = runner(src_obj)
        if res is None:
            log.info("  [%s] returned no candidates — skipping (attempt %d)",
                     src_obj.name, attempts)
            continue
        out[src_obj.name] = res

    if len(out) < want:
        log.warning(
            "[%s] backfill exhausted: only %d/%d sources contributed "
            "after %d attempts (pool size %d)",
            label, len(out), want, attempts, len(pool))
    return out


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


# Shape used by filter_past_duplicates:
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
news site for kids ages 10-14. The pipeline mined a pre-vetted pool of
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

  STEP 3 — Within-category SOURCE diversity (HARD RULE). Each of the 3
  picks in a category MUST come from a DIFFERENT source unless the
  category genuinely has fewer than 3 distinct sources contributing
  candidates. Concretely:
    · If the category's input has candidates from ≥ 3 different sources,
      your 3 picks must each come from a different source.
    · If only 2 sources contributed, the 3rd pick may repeat one of
      those sources — but pick the one with the most alternates so
      you can still diversify topics.
    · If only 1 source contributed, all 3 picks come from it
      (unavoidable).
  When swapping for source-diversity, prefer the swap that ALSO
  improves topic diversity (Step 4). Promote an alternate_X from the
  under-represented source over a choice_2 from the over-represented
  one.

  STEP 4 — Within-category TOPIC diversity. After source-diversity is
  satisfied, if the 3 picks are all about the same theme (3 election
  stories, 3 climate stories, etc.), swap one to a different topic
  from the alternates. Goal: 3 different topic clusters per category.

  STEP 5 — Final check. You must end up with 9 distinct stories:
  3 News + 3 Science + 3 Fun. No cross-cat dups. Each category's
  3 picks come from 3 different sources (unless the category had
  fewer than 3 sources to begin with). Diverse topics within each
  cat. Output each pick as its `cid`.

PREFERENCES (use to break ties between equally-valid options):
  · Lower slot wins (choice_1 > choice_2 > alternate_0 > alternate_1).

DEGRADATION (only when the pool is genuinely too thin to satisfy the
contract): if a category truly has fewer than 3 distinct
non-duplicate stories available across all its candidates, you may
return 2 in that category. Never 1 or 0 unless that category had no
candidates at all in the input. Source-diversity automatically
relaxes when a category has fewer than 3 sources contributing
(see STEP 3) — you don't need a separate exception for that case.

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


_SLOT_RANK = {"choice_1": 0, "choice_2": 1, "alternate_0": 2, "alternate_1": 3}


def _enforce_source_diversity(
    picks_by_cat: dict[str, list[dict]],
    buckets_by_cat: dict[str, dict],
) -> dict[str, list[dict]]:
    """Walk each category and ensure no source contributes more than one
    pick — unless the category genuinely has fewer than 3 sources.

    Strategy per category:
      1. If <3 sources contributed candidates, leave alone (degrade-OK).
      2. Otherwise, for each duplicated source, find an alternate from
         an UNUSED source bucket (preferring the lowest-slot candidate
         in that bucket so the editorial quality stays intact).
      3. Replace the duplicate's worst-slot pick (e.g. an alternate_1
         beats a choice_1 swap) so the better pick survives.
      4. Repeat until no duplicates OR no unused sources remain.

    Idempotent: a clean input passes through unchanged.
    """
    from collections import Counter

    for cat, picks in picks_by_cat.items():
        if len(picks) < 2:
            continue
        all_src_names = set((buckets_by_cat.get(cat) or {}).keys())
        if len(all_src_names) < 3:
            # Category truly thin on sources — degradation acceptable.
            continue

        used_winner_ids = {id(p["winner"]) for p in picks}

        # Iterative swap loop with a hard guard against infinite loops.
        for _ in range(6):
            srcs_in_use = [p["source"].name for p in picks]
            counter = Counter(srcs_in_use)
            dups = [name for name, c in counter.items() if c > 1]
            if not dups:
                break
            unused_srcs = all_src_names - set(srcs_in_use)
            if not unused_srcs:
                break

            # Pick replacement from the unused source with the lowest-slot
            # candidate (best editorial quality).
            replacement = None
            replacement_src_name = None
            for src_name in sorted(unused_srcs):
                bundle = (buckets_by_cat.get(cat) or {}).get(src_name) or {}
                cands = bundle.get("candidates") or []
                if not cands:
                    continue
                # First candidate from this bundle — they're already
                # ordered by slot in the curator's input.
                cand = cands[0]
                if id(cand["winner"]) in used_winner_ids:
                    continue
                replacement = {
                    "source": bundle.get("source"),
                    "winner": cand["winner"],
                    "winner_slot": cand.get("slot", "choice_1"),
                }
                replacement_src_name = src_name
                break
            if not replacement:
                break

            # Replace the WORST-slot pick from any duplicated source.
            dup_idxs = [i for i, p in enumerate(picks) if p["source"].name in dups]
            dup_idxs.sort(
                key=lambda i: _SLOT_RANK.get(picks[i].get("winner_slot", ""), 99),
                reverse=True,
            )
            replace_at = dup_idxs[0]
            old_src = picks[replace_at]["source"].name
            old_slot = picks[replace_at].get("winner_slot", "?")
            log.info(
                "  [%s] source-diversity swap: %s/%s → %s/%s",
                cat, old_src, old_slot,
                replacement_src_name, replacement["winner_slot"],
            )
            used_winner_ids.discard(id(picks[replace_at]["winner"]))
            used_winner_ids.add(id(replacement["winner"]))
            picks[replace_at] = replacement

    return picks_by_cat


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

    # Post-curator: enforce source-diversity within each category.
    # The system prompt asks the LLM to do this, but it sometimes lapses
    # — particularly when one source has stronger choice_1 + choice_2
    # than other sources' choice_1. This pass swaps duplicate-source
    # picks for an alternate from an unused-source bucket whenever
    # one is available. No-op when the category genuinely has fewer
    # than 3 sources contributing candidates.
    out = _enforce_source_diversity(out, buckets_by_cat)

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


# ─── Mega pipeline helpers ─────────────────────────────────────────────

def phase_a_light(category: str, sources, max_per_source: int = 4) -> list[dict]:
    """Light Phase A for the mega path: feed metadata only — NO body fetch,
    NO LLM. Returns a flat list of brief dicts annotated with _source +
    _category. Bodies + og:images are fetched lazily after the curator
    has narrowed the pool to ranks 1-4.

    Routes through fetch_source_entries (NOT raw feedparser) so that:
      · the 5-day RSS freshness filter applies (bug 2026-05-01 had
        silently regressed on this path), and
      · feed_kind dispatch works — html_list/sitemap sources (DOGOnews,
        NG Kids) produced 0 briefs when this called feedparser directly.
    Bug: docs/bugs/2026-07-08-mega-path-regressions.md
    """
    briefs: list[dict] = []
    for source in sources:
        try:
            entries = fetch_source_entries(source, max_entries=max_per_source)
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] feed fetch failed: %s", source.name, e)
            continue
        for entry in entries:
            excluded = editorial_exclusion(entry)
            if excluded:
                log.info("  [%s] editorial DROP (%s): %s", category,
                         excluded, (entry.get("title") or "")[:100])
                continue
            briefs.append({
                "title": entry.get("title") or "",
                "summary": entry.get("summary") or "",
                "link": entry.get("link") or "",
                "published": entry.get("published") or "",
                "_source_name": source.name,
                "_source": source,
                "_category": category,
            })
    log.info("  [%s] phase_a_light: %d briefs from %d sources",
             category, len(briefs), len(sources))
    return briefs


def _canonical_source_url(url: str) -> str:
    """Ignore tracking parameters, but preserve query parameters identifying an article."""
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if not host:
        return ""
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query)
                             if not (k.lower().startswith("utm_") or k.lower() in
                                     {"at_medium", "at_campaign", "fbclid"})))
    return f"{host}{parsed.path.rstrip('/') or '/'}?{query}" if query else f"{host}{parsed.path.rstrip('/') or '/'}"


def _drop_dup_briefs(briefs: list[dict], past_titles: list[str],
                     threshold: float = 0.80,
                     past_urls: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Pure core of the mega-path past-run dedup: split briefs into
    (kept, dropped) by title similarity against recently published titles."""
    kept: list[dict] = []
    dropped: list[dict] = []
    past_urls = past_urls or set()
    for b in briefs:
        t = b.get("title") or ""
        url = _canonical_source_url(b.get("link") or "")
        best = max((_title_similarity(t, pt) for pt in past_titles), default=0.0)
        (dropped if best >= threshold or (url and url in past_urls) else kept).append(b)
    return kept, dropped


def filter_past_duplicate_briefs(briefs_by_cat: dict[str, list[dict]],
                                 days: int = 7,
                                 threshold: float = 0.80,
                                 run_date: str | None = None) -> dict[str, list[dict]]:
    """Mega-path counterpart of filter_past_duplicates (which only the
    legacy path calls): drop briefs whose URL matches exactly (ignoring
    tracking parameters) or whose title ≥threshold-matches a story
    the same category published in the `days` days BEFORE this run's date. A
    sticky top-of-feed item on a cadence-1 source would otherwise be eligible
    to republish on consecutive days. Fail-open: any DB error keeps all briefs.

    The window is half-open — [run_date-days, run_date) — because a re-run
    replaces the rows it published earlier today. Without the upper bound it
    matched its own previous attempt and dropped exactly the stories it had
    just judged best. Bug: docs/bugs/2026-09-20-past-dedup-self-poisons-reruns.md"""
    from datetime import date, timedelta
    from .supabase_io import client
    end = run_date or date.today().isoformat()
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    try:
        r = client().table("redesign_stories").select(
            "source_title,source_url,category"
        ).gte("published_date", start).lt("published_date", end).eq(
            "archived", False).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("brief past-dedup skipped — query failed: %s", e)
        return briefs_by_cat

    out: dict[str, list[dict]] = {}
    for cat, briefs in briefs_by_cat.items():
        history = [row for row in (r.data or []) if row.get("category") == cat]
        past_titles = sorted({row["source_title"] for row in history if row.get("source_title")})
        past_urls = {_canonical_source_url(row.get("source_url") or "")
                     for row in history if row.get("source_url")}
        kept, dropped = _drop_dup_briefs(briefs, past_titles, threshold,
                                         past_urls=past_urls)
        for b in dropped:
            log.info("  [%s] past-dup brief drop: %s", cat, (b.get("title") or "")[:70])
        out[cat] = kept
    return out


def _probe_bump(next_pickup_at: str | None, today_iso: str) -> str | None:
    """Bump rule for a picked-but-unshipped source: if its next_pickup_at is
    unset or already due, move it to tomorrow so it stops winning the
    most-overdue rotation slot every day (the failure mode that let a dead
    PBS hog 1 of 3 News slots for a month). A source already scheduled in
    the future is left alone (it was a sleeping filler pick)."""
    npa = (next_pickup_at or "")[:10]
    if npa and npa > today_iso:
        return None
    from datetime import date, timedelta
    return (date.fromisoformat(today_iso) + timedelta(days=1)).isoformat()


def stamp_probe_outcomes(picked_by_cat: dict[str, list],
                         briefs_by_cat: dict[str, list[dict]],
                         shipped_names: set[str]) -> None:
    """Close the pickup feedback loop: record an outcome for every picked
    source that did NOT ship a story today.

      · probe_attempts += 1   (it was picked and produced nothing shippable)
      · probe_errors  += 1    when it produced zero briefs (fetch/parse-level
                              failure — the PBS/WAF class)
      · next_pickup_at → tomorrow when unset/overdue (see _probe_bump)

    Shipped sources are stamped by persist_to_supabase as before. Non-fatal:
    each row is best-effort; a failed PATCH only costs telemetry.
    Bug: docs/bugs/2026-07-08-mega-path-regressions.md
    """
    from datetime import date
    from .supabase_io import client
    today_iso = date.today().isoformat()
    contributed = {b.get("_source_name")
                   for briefs in briefs_by_cat.values() for b in briefs}
    stamped = 0
    for cat, sources in picked_by_cat.items():
        for s in sources:
            if s.name in shipped_names:
                continue
            try:
                rows = client().table("redesign_source_configs") \
                    .select("probe_attempts,probe_errors,next_pickup_at") \
                    .eq("name", s.name).limit(1).execute().data or []
                cur = rows[0] if rows else {}
                fields: dict = {
                    "probe_attempts": int(cur.get("probe_attempts") or 0) + 1,
                }
                if s.name not in contributed:
                    fields["probe_errors"] = int(cur.get("probe_errors") or 0) + 1
                bump = _probe_bump(cur.get("next_pickup_at"), today_iso)
                if bump:
                    fields["next_pickup_at"] = bump
                client().table("redesign_source_configs") \
                    .update(fields).eq("name", s.name).execute()
                stamped += 1
                log.info("  probe-stamp [%s/%s]: %s", cat, s.name,
                         ", ".join(f"{k}={v}" for k, v in fields.items()))
            except Exception as e:  # noqa: BLE001
                log.warning("probe-stamp %s failed (non-fatal): %s", s.name, e)
    if stamped:
        log.info("probe outcomes stamped on %d unshipped source(s)", stamped)


def _interleave_by_source(briefs: list[dict]) -> list[dict]:
    """Round-robin briefs across sources (first-seen source order,
    within-source order preserved). The Stage-1.5 probe cap walks briefs
    in list order, and phase_a_light emits them grouped by source in
    priority order — so with 4 News sources × 4 briefs and cap 10, the
    priority-4 source (BBC) got ZERO probe slots on any day the earlier
    feeds were healthy (found 2026-07-08 via checkpoint reconstruction).
    Interleaving makes the cap sample every source fairly."""
    by_src: dict[str, list[dict]] = {}
    for b in briefs:
        by_src.setdefault(b.get("_source_name") or "", []).append(b)
    queues = list(by_src.values())
    out: list[dict] = []
    while queues:
        queues = [q for q in queues if q]
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


def _partition_probe_results(results: list[dict], min_words: int,
                             max_words: int, cap: int,
                             ) -> tuple[list[dict], dict[str, dict[str, int]]]:
    """Classify probe results per source and apply the per-cat cap.
    Returns (kept_briefs, tally) with tally[src] = {in, kept, thin, long,
    cap_cut}. Unlike the old break-at-cap loop, every brief is classified,
    so a source starved by the cap shows up as cap_cut in telemetry
    instead of vanishing silently."""
    kept: list[dict] = []
    tally: dict[str, dict[str, int]] = {}
    for r in results:
        src = (r["brief"].get("_source_name") or "?")
        t = tally.setdefault(
            src, {"in": 0, "kept": 0, "thin": 0, "long": 0, "cap_cut": 0})
        t["in"] += 1
        wc = r["wc"]
        if wc < min_words:
            t["thin"] += 1
        elif wc > max_words:
            t["long"] += 1
        elif len(kept) >= cap:
            t["cap_cut"] += 1
        else:
            b = r["brief"]
            b["_probe_art"] = r["art"]
            b["word_count"] = wc
            kept.append(b)
            t["kept"] += 1
    return kept, tally


def verify_picks_lazy(ranked_by_cat: dict[str, list[dict]],
                       max_top: int = 4,
                       min_body_words: int = 250,
                       stats: dict | None = None) -> dict[str, list[dict]]:
    """For each category's top-`max_top` ranked picks, fetch HTML body +
    og:image and verify. If a rank-1..4 pick fails, promote rank 5.
    Returns {cat: [story_dict_with_winner, ...]} where story_dict has
    `winner`, `source`, `winner_slot`, `_rank`. Includes the verified
    spares too (so Stage 3 can promote them on safety reject).

    If `stats` (a dict) is passed, it is filled per category/source with
    {"verified": n, "rejects": {reason: n}} for funnel telemetry.
    """
    from .news_rss_core import _fetch_and_enrich, verify_article_content

    out: dict[str, list[dict]] = {}
    for cat, ranked in ranked_by_cat.items():
        verified: list[dict] = []
        used: set[int] = set()

        def _stat(r: dict) -> dict:
            src = getattr(r.get("source"), "name", None) or "?"
            cstats = stats.setdefault(cat, {}) if stats is not None else {}
            return cstats.setdefault(src, {"verified": 0, "rejects": {}})

        # Walk in rank order; verify each. We aim to fill up to max_top
        # AND keep all ranks beyond as un-verified spares (verify lazily
        # later if Stage 3 needs them).
        for r in ranked:
            if len(verified) >= max_top:
                # Don't body-verify spares yet — Stage 3 promotion does it
                # if/when needed.
                break
            cid = r.get("id")
            if cid in used:
                continue
            brief = r["brief"]
            if cat == "Fun" and low_fun_value(brief):
                continue
            if editorial_exclusion(brief):
                log.info("  [%s] verify skipped college recruitment: %s",
                         cat, (brief.get("title") or "")[:80])
                continue
            # Stage 1.5 already body-fetched this brief; reuse the cached
            # article dict to avoid a second HTTP round-trip per pick.
            cached = brief.get("_probe_art") if isinstance(brief, dict) else None
            art = dict(cached) if cached else _fetch_and_enrich(dict(brief))
            if editorial_exclusion(art):
                continue
            ok, reason = verify_article_content(art)
            if not ok:
                log.info("  [%s] rank %s (%s) body-verify FAIL: %s",
                         cat, r.get("rank"),
                         getattr(r.get("source"), "name", "?"), reason)
                if stats is not None:
                    st = _stat(r)
                    st["rejects"][reason] = st["rejects"].get(reason, 0) + 1
                continue
            if (art.get("word_count") or 0) < min_body_words:
                log.info("  [%s] rank %s too thin: %dw < %d",
                         cat, r.get("rank"), art.get("word_count", 0), min_body_words)
                if stats is not None:
                    st = _stat(r)
                    st["rejects"]["too thin"] = st["rejects"].get("too thin", 0) + 1
                continue
            used.add(cid)
            if stats is not None:
                _stat(r)["verified"] += 1
            verified.append({
                "source": r["source"],
                "winner": art,
                "winner_slot": f"rank_{r.get('rank')}",
                "_rank": r.get("rank"),
                "_curator_id": cid,
                "_brief": brief,
            })
            log.info("  [%s] rank %s ✓ verified %s (%dw)",
                     cat, r.get("rank"), r["source"].name,
                     art.get("word_count", 0))
        # Append remaining un-verified spares (rank 5+). Stage 3 promotes
        # one of these only if a top-4 article gets safety-rejected.
        for r in ranked:
            cid = r.get("id")
            if cid in used:
                continue
            verified.append({
                "_unverified_spare": True,
                "source": r["source"],
                "_winner_brief": r["brief"],
                "_rank": r.get("rank"),
                "_curator_id": cid,
            })
        out[cat] = verified
    return out


def _recent_published_titles(today: str, days: int = 7, *, category: str) -> list[str]:
    """Source headlines published in the last `days` days, same category, EXCLUDING
    today — a same-day re-run must not see its own earlier output as the past.
    Fail-open: any DB error returns []."""
    from datetime import date, timedelta
    try:
        from .supabase_io import client
        start = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
        rows = client().table("redesign_stories").select("source_title") \
            .eq("category", category) \
            .gte("published_date", start).lt("published_date", today) \
            .eq("archived", False).execute().data or []
        return sorted({r["source_title"] for r in rows if r.get("source_title")})
    except Exception as e:  # noqa: BLE001
        log.warning("recent-published lookup failed (non-fatal): %s", e)
        return []


def _unpicked_probe_spares(briefs: list[dict], ranked: list[dict],
                           keep_order: bool = False) -> list[dict]:
    """Deep backfill pool (2026-07-08): the curator ranks only 5 per cat,
    so after verify/safety attrition a category could starve while
    probe-kept briefs sat unused — one thin category then aborted the
    whole publish. Turn every probed-but-unranked brief into an
    unverified Stage-3 spare (source-interleaved). Each still passes
    body/image verify + the full safety vet in promote_spare_and_rewrite
    before it can ship — this deepens the pool, it does not lower gates."""
    used_keys = set()
    for r in ranked:
        b = r.get("brief") or {}
        used_keys.add(b.get("link") or b.get("title") or id(b))
    from .jev_rank import CATEGORY_FIT_MIN
    leftovers = [
        b for b in briefs
        if (b.get("link") or b.get("title") or id(b)) not in used_keys
        and float(b.get("_jev_category_fit", 1.0)) >= CATEGORY_FIT_MIN
        and (not explicit_section(b) or explicit_section(b) == b.get("_category"))
        and not editorial_exclusion(b)
        and not (b.get("_category") == "Fun" and low_fun_value(b))
    ]
    out: list[dict] = []
    # keep_order: the pool arrives Jev-ranked, so promote spares best-first.
    ordered = leftovers if keep_order else _interleave_by_source(leftovers)
    for i, b in enumerate(ordered, start=1):
        src = b.get("_source")
        if src is None:
            continue
        out.append({
            "_unverified_spare": True,
            "source": src,
            "_winner_brief": b,
            "_rank": f"probe+{i}",
            "_curator_id": None,
        })
    return out


def _deep_dig_spares(cat: str, sources, exclude_links: set,
                     max_per_source: int = 15) -> list[dict]:
    """Reactive deep backfill (2026-07-11): when a category is short after
    promoting the shallow probe spares, dig DEEPER into the same day's
    sources — phase_a only fetched 4/source, so items 5..max_per_source
    of each feed were never seen. Fetch them, drop already-considered
    links, interleave across sources, and wrap each as an unverified
    Stage-3 spare. Each still passes body/image verify + safety vet +
    title-dedup in promote_spare_and_rewrite — this only widens the
    candidate net with fresh same-day stories; it does not lower gates."""
    from .news_rss_core import fetch_source_entries
    seen = set(exclude_links or ())
    briefs: list[dict] = []
    for source in sources:
        try:
            entries = fetch_source_entries(source, max_entries=max_per_source)
        except Exception as e:  # noqa: BLE001
            log.warning("  [%s] deep-dig fetch failed for %s: %s",
                        cat, getattr(source, "name", "?"), e)
            continue
        for entry in entries:
            link = entry.get("link") or ""
            if not link or link in seen or editorial_exclusion(entry):
                continue
            seen.add(link)
            briefs.append({
                "title": entry.get("title") or "",
                "summary": entry.get("summary") or "",
                "link": link,
                "published": entry.get("published") or "",
                "_source_name": source.name,
                "_source": source,
                "_category": cat,
            })
    briefs = _interleave_by_source(briefs)
    return [{"_unverified_spare": True, "source": b["_source"],
             "_winner_brief": b, "_rank": f"dig+{i}", "_curator_id": None}
            for i, b in enumerate(briefs, start=1)]


def _gate_deep_dig_spares(cat: str, spares: list[dict]) -> list[dict]:
    """Apply the same section-fit threshold as first-round ranking to new RSS items."""
    from .jev_rank import gate_deep_dig_category

    briefs = [s["_winner_brief"] for s in spares]
    eligible = {id(b) for b in gate_deep_dig_category(cat, briefs)}
    return [s for s in spares if id(s["_winner_brief"]) in eligible]


def _split_publishable(final_stories_by_cat: dict,
                       min_per_cat: int = 2) -> tuple[list[str], list[str]]:
    """Partition categories into (fresh_ok, too_thin) for the pack step.
    A thin category no longer sinks the whole bundle — pack runs in merge
    mode publishing the fresh ones while the thin one keeps its current
    live content."""
    ok: list[str] = []
    thin: list[str] = []
    for cat, stories in final_stories_by_cat.items():
        (ok if len(stories) >= min_per_cat else thin).append(cat)
    return ok, thin


def _prefer_final_source_diversity(
    winners: list[dict], articles: list[dict], limit: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Keep the safest ranked order while filling the first three with unique sources.

    Stage 3 can reject a diverse pick and expose a duplicate source at rank 4.
    Reorder only already-vetted, already-verified articles; never manufacture
    diversity by bypassing the safety or category-fit gates.
    """
    paired = list(zip(winners, articles))
    chosen: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    for pair in paired:
        name = (pair[0].get("source") and pair[0]["source"].name) or ""
        if name and name not in seen and len(chosen) < limit:
            chosen.append(pair)
            seen.add(name)
    chosen_ids = {id(pair[0]) for pair in chosen}
    ordered = chosen + [pair for pair in paired if id(pair[0]) not in chosen_ids]
    return [p[0] for p in ordered], [p[1] for p in ordered]


def promote_spare_and_rewrite(
    cat: str,
    spares: list[dict],
    used_source_names: set[str] | None = None,
    used_titles: set[str] | None = None,
    used_briefs: list[dict] | None = None,
    used_event_groups: set[str] | None = None,
    used_topic_groups: set[str] | None = None,
    require_new_source: bool = False,
    used_publishers: set[str] | None = None,
    require_new_publisher: bool = False,
    require_new_topic: bool = False,
    history_guard=None,
) -> tuple[dict | None, dict | None]:
    """Pop the next un-verified spare for `cat`, body+image verify, then
    run a 1-article tri_variant_rewrite. Returns (story_dict, rewrite_art)
    on success or (None, None) if no spare survives verify+rewrite+vet.

    `used_source_names` is the set of source.name strings already in
    the surviving top 3. News uses scored editorial value with a small
    topic bonus; the other sections prefer another topic group, then
    follow the ranked candidate order. A repeated source is eligible
    unless `require_new_source` is set for a diversity-only pass.

    `used_titles` are the headlines already shipping — a probe-pool spare
    (no cluster_id) whose title matches one is the same wire story from a
    third source and is skipped, so promotion can't reintroduce the dup
    that _dedupe_ranked_stories just removed upstream.
    """
    from .news_rss_core import _fetch_and_enrich, verify_article_content
    from .jev_rank import CATEGORY_FIT_MIN
    from .mega_curator import briefs_same_event
    from .news_topics import topic_group
    from .editorial_policy import news_editorial_strength

    used = set(used_source_names or ())
    shipped_briefs = list(used_briefs or ())
    shipped_briefs.extend({"title": t} for t in (used_titles or ()) if t)
    shipped_groups = set(used_event_groups or ())
    topics_used = set(used_topic_groups or ())
    publishers_used = set(used_publishers or ())

    def _try_one(spare: dict):
        if not spare.get("_unverified_spare"):
            return None, None
        brief = spare.get("_winner_brief") or {}
        forced = explicit_section(brief)
        if forced and forced != cat:
            log.info("  [%s] spare skipped — article belongs in %s: %s",
                     cat, forced, (brief.get("title") or "")[:80])
            return None, None
        if cat == "Fun" and low_fun_value(brief):
            return None, None
        if editorial_exclusion(brief):
            log.info("  [%s] spare skipped college recruitment: %s",
                     cat, (brief.get("title") or "")[:80])
            return None, None
        spare_title = (brief.get("title") or "") if isinstance(brief, dict) else ""
        fit = float(brief.get("_jev_category_fit", 1.0))
        if fit < CATEGORY_FIT_MIN:
            log.info("  [%s] spare rank %s skipped — category fit %.2f: %s",
                     cat, spare.get("_rank"), fit, spare_title[:60])
            return None, None
        # A thin section may publish fewer than three fresh stories. Never
        # fill a slot with a candidate that the editor already rated below
        # the section's own quality floor.
        if below_quality_floor(brief):
            rank = brief["_jev_rank"]
            log.info("  [%s] spare rank %s skipped — editorial pick %.2f below %.2f",
                     cat, spare.get("_rank"), float(rank["editorial_pick"]),
                     float(rank["floor"]))
            return None, None
        spare_group = (brief.get("_event_group") or "").strip()
        if ((spare_group and spare_group in shipped_groups)
                or any(briefs_same_event(brief, shipped) for shipped in shipped_briefs)):
            log.info("  [%s] spare rank %s skipped — same story as a shipped "
                     "pick: %s", cat, spare.get("_rank"), spare_title[:60])
            return None, None
        if history_guard is not None and not history_guard.allows(brief):
            return None, None
        cached = brief.get("_probe_art") if isinstance(brief, dict) else None
        art = dict(cached) if cached else _fetch_and_enrich(dict(brief))
        if editorial_exclusion(art):
            return None, None
        ok, _ = verify_article_content(art)
        if not ok:
            return None, None
        rewrite_res = tri_variant_rewrite([(0, art)], category=cat)
        kept, _ = filter_safe_rewrites(rewrite_res, {0: art}, category=cat)
        if not kept:
            log.warning(
                "  [%s] spare rank %s passed body-verify but failed Stage 3 vet",
                cat, spare.get("_rank"),
            )
            return None, None
        log.info(
            "  [%s] spare rank %s promoted (%s)",
            cat, spare.get("_rank"), spare["source"].name,
        )
        return (
            {
                "source": spare["source"],
                "winner": art,
                "winner_slot": f"rank_{spare.get('_rank')}",
                "_rank": spare.get("_rank"),
                "_curator_id": spare.get("_curator_id"),
                "_brief": brief,
            },
            kept[0],
        )

    # Topic variety is a soft preference. In News, a much stronger scored
    # candidate from an already-used broad group must not lose to a weak one.
    # Unscored spares and the other sections retain the existing topic tiers.
    # Failed candidates are consumed; unattempted ones remain available.
    def _priority(spare: dict):
        brief = spare.get("_winner_brief") or {}
        label = topic_group(brief)
        repeats_topic = bool(topics_used) and (not label or label in topics_used)
        if cat == "News":
            strength = news_editorial_strength(brief)
            if strength is not None:
                return (0, -(strength + (0 if repeats_topic else .06)))
            return (1, int(repeats_topic))
        return int(repeats_topic)

    for spare in sorted(spares, key=_priority):
        if require_new_topic:
            topic = topic_group(spare.get("_winner_brief") or {})
            if not topic or topic in topics_used:
                continue
        if require_new_publisher and (not publisher_key(spare.get("source"))
                                      or publisher_key(spare.get("source")) in publishers_used):
            continue
        if require_new_source and ((spare.get("source") and spare["source"].name) or "") in used:
            continue
        spares.pop(next(i for i, candidate in enumerate(spares) if candidate is spare))
        story, art = _try_one(spare)
        if story is not None:
            if ((spare.get("source") and spare["source"].name) or "") in used:
                log.info("  [%s] diversity-fallback: promoting repeated source %s",
                         cat, (spare.get("source") and spare["source"].name) or "?")
            return story, art
    return None, None


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

def rewrite_for_category(stories: list[dict],
                          category: str | None = None) -> tuple[dict[int, dict], dict]:
    """Tri-variant rewrite, then detail enrichment. Returns
    (variants_by_src_id, details_by_slot). Raises if either step ultimately
    fails — callers decide whether that's fatal for the whole run."""
    if not stories:
        return {}, {}
    articles_for_rewrite = [(i, s["winner"]) for i, s in enumerate(stories)]
    rewrite_res = tri_variant_rewrite(articles_for_rewrite, category=category)
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
# 3.5) Partial-run helpers (PIPELINE_CATEGORIES=News → run one category)
# -------------------------------------------------------------------

def _filter_categories(available: list[str], requested: str) -> list[str]:
    """Resolve a comma-separated PIPELINE_CATEGORIES value against the
    DB-active category names (case-insensitive). Unknown names are a
    hard error — a typo must never silently run the full pipeline."""
    by_lower = {c.lower(): c for c in available}
    out: list[str] = []
    unknown: list[str] = []
    for raw in requested.split(","):
        name = raw.strip()
        if not name:
            continue
        canon = by_lower.get(name.lower())
        if canon is None:
            unknown.append(name)
        elif canon not in out:
            out.append(canon)
    if unknown:
        raise SystemExit(
            f"PIPELINE_CATEGORIES unknown: {unknown} (active: {available})")
    if not out:
        raise SystemExit("PIPELINE_CATEGORIES is set but empty")
    return out


def _archive_replaced_stories(cats: list[str], date_str: str) -> None:
    """Partial-run hygiene: mark today's existing rows for the re-run
    categories archived=true and drop their search-index rows, so the
    replaced stories don't double-count in digests or linger in search.
    Non-fatal on error — the re-run content itself is unaffected."""
    from .supabase_io import client
    try:
        sb = client()
        r = (sb.table("redesign_stories")
               .update({"archived": True})
               .eq("published_date", date_str)
               .in_("category", cats)
               .execute())
        rows = r.data or []
        sids = [row.get("payload_story_id") for row in rows
                if row.get("payload_story_id")]
        log.info("partial: archived %d replaced %s stories",
                 len(rows), "/".join(cats))
        if sids:
            sb.table("redesign_search_index").delete() \
              .in_("story_id", sids).execute()
            log.info("partial: dropped %d search-index story ids", len(sids))
    except Exception as e:  # noqa: BLE001
        log.warning("partial: archive/search cleanup failed (non-fatal): %s", e)


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

    # Only the categories actually passed in — a partial run must not
    # emit EMPTY listings for absent categories (the pack merge would
    # ship them over good live content).
    for category in stories_by_cat:
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
            variant = variants.get(slot - 1) or variants.get(str(slot - 1)) or {}
            story_id = s.get("_story_id") or make_story_id(today, category, slot)
            vet = art.get("_vet_info") or {}
            # Mega's independent Stage-3 vet scores the rewritten body, not the
            # source article. Persist that final decision when available so
            # redesign_stories reflects the text children actually read.
            final_eval = variant.get("_safety_eval") or {}
            safety = final_eval.get("scores") or vet.get("safety") or {}
            safety_total = (sum((safety.get(d) or 0) for d in
                                ("violence", "sexual", "substance", "language",
                                 "fear", "adult_themes", "distress", "bias"))
                            if final_eval.get("scores") else safety.get("total"))
            safety_verdict = ("SAFE" if final_eval.get("verdict") == "PASS"
                              else safety.get("verdict"))
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
                "safety_total":      safety_total,
                "safety_verdict":    safety_verdict,
                "interest_importance": interest.get("importance"),
                "interest_fun_factor": interest.get("fun_factor"),
                "interest_kid_appeal": interest.get("kid_appeal"),
                "interest_peak":       interest.get("peak"),
                "interest_verdict":    interest.get("verdict"),
                "vet_flags": safety.get("flags") or vet.get("flags") or [],
                "primary_image_url": s.get("_image_storage_url") or art.get("og_image"),
                "primary_image_local": s.get("_image_local"),
                "primary_image_credit": src_host,
                # Explicit: a freshly-shipped story is never archived. The
                # (date,category,slot) upsert overwrites a partial-run's
                # superseded row, which _archive_replaced_stories just
                # flagged — without this the flag would stick to the NEW row.
                "archived": False,
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

        # Same-day re-run hygiene: a second run that ships FEWER slots than a
        # prior attempt upserts slots 1..N but used to leave the prior run's
        # higher slot rows live under today's date (DB/site divergence for
        # search, digest, archive). Delete anything above today's shipped count.
        try:
            from .supabase_io import client
            gone = client().table("redesign_stories").delete() \
                .eq("published_date", today).eq("category", category) \
                .gt("story_slot", len(stories)).execute().data or []
            if gone:
                log.info("  [%s] removed %d orphan slot row(s) from a prior "
                         "same-day attempt", category, len(gone))
        except Exception as e:  # noqa: BLE001
            log.warning("  [%s] orphan-slot cleanup failed (non-fatal): %s",
                        category, e)
    return count


def stamp_shipped_sources(stories_by_cat) -> None:
    """Stamp last_used_at + next_pickup_at (= today + cadence_days) for every
    source whose article shipped today. Powers the rotation in
    db_config.load_sources — least-recently-used sources surface first.

    Called AFTER pack_and_upload succeeds (was inside persist_to_supabase):
    stamping before deploy meant a deploy_failed day marked today's sources
    ineligible, so a fresh re-run mined a different, possibly weaker bundle.
    Bug: docs/bugs/2026-07-08-p1-reliability.md"""
    used_source_names: set[str] = set()
    for category, stories in stories_by_cat.items():
        for s in stories:
            n = (s.get("source") and s["source"].name) or ""
            if n: used_source_names.add(n)
    if not used_source_names:
        return
    try:
        from .supabase_io import client
        from datetime import timedelta, date as _date
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        today_d = _date.today()
        # Stamp BOTH last_used_at AND next_pickup_at = today + cadence_days.
        # Per-source PATCH because cadence_days varies. Source list is small
        # (≤9 winners per run), so per-row is fine.
        src_rows = client().table("redesign_source_configs") \
            .select("name,cadence_days") \
            .in_("name", list(used_source_names)) \
            .execute().data or []

        for row in src_rows:
            cd = int(row.get("cadence_days") or 1)
            next_pickup = (today_d + timedelta(days=cd)).isoformat()
            client().table("redesign_source_configs") \
                .update({"last_used_at": now_iso, "next_pickup_at": next_pickup}) \
                .eq("name", row["name"]) \
                .execute()
        log.info("  stamped last_used_at + next_pickup_at on %d source(s)",
                 len(src_rows))
    except Exception as e:  # noqa: BLE001
        log.warning("  last_used_at stamp failed: %s", e)


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
    today = pipeline_run_date()
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
    from datetime import date as _date
    today_d = _date.today()
    # Load a deep-enough pool so aggregate_category can backfill if the
    # top-3 cadence picks fail to produce candidates (e.g. weekly source
    # had no articles in the freshness window). want=3 is the diversity
    # target; pool of 12 covers 4× backfill headroom for Fun (largest
    # category) without runaway compute on a fully-failing day.
    POOL_DEPTH = 12
    SOURCES_PER_CATEGORY = 3
    news_bs    = aggregate_category(
        "News",    db_config.load_sources("News",    today=today_d, n=POOL_DEPTH),
        run_news,  want=SOURCES_PER_CATEGORY)
    science_bs = aggregate_category(
        "Science", db_config.load_sources("Science", today=today_d, n=POOL_DEPTH),
        run_sci,   want=SOURCES_PER_CATEGORY)
    fun_bs     = aggregate_category(
        "Fun",     db_config.load_sources("Fun",     today=today_d, n=POOL_DEPTH),
        run_fun,   want=SOURCES_PER_CATEGORY)
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
            v, d = rewrite_for_category(ws, category=cat)
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
            # Rotation stamping moved here from persist_to_supabase: only a
            # DEPLOYED bundle counts as "used" for source rotation.
            stamp_shipped_sources(stories_by_cat)
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


# ─── Mega orchestrator (PIPELINE_VARIANT=mega) ─────────────────────────

def enrich_survivors(stories_by_cat: dict, variants_by_cat: dict, *,
                     max_workers: int = 2, enrich_fn=None) -> tuple[dict, list[str], list[tuple], dict]:
    """Enrich independent categories with at most two concurrent model calls.

    Each category still runs easy then middle serially inside detail_enrich,
    preserving its proven 3-slot output contract. A failed category does not
    discard results from the others; the caller retains the existing abort
    policy after every future has completed.
    """
    if max_workers not in (1, 2):
        raise ValueError("enrich max_workers must be 1 or 2")
    enrich_fn = enrich_fn or detail_enrich
    out: dict[str, dict] = {cat: {} for cat in stories_by_cat}
    failures: list[str] = []
    partial: list[tuple[str, int, int]] = []
    per_category: dict[str, float] = {}
    jobs = []
    for cat, stories in stories_by_cat.items():
        if not stories:
            continue
        variants = variants_by_cat[cat]
        articles = [variants[i] if i in variants else variants[str(i)]
                    for i in range(len(stories))]
        jobs.append((cat, articles))
    if not jobs:
        return out, failures, partial, per_category

    def _one(cat: str, articles: list[dict]):
        started = time.monotonic()
        result = enrich_fn({"articles": articles})
        return result.get("details") or {}, time.monotonic() - started

    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as ex:
        futures = {ex.submit(_one, cat, articles): (cat, len(articles) * 2)
                   for cat, articles in jobs}
        for fut in as_completed(futures):
            cat, expected = futures[fut]
            try:
                details, seconds = fut.result()
            except Exception as e:  # noqa: BLE001 — match the serial path's per-category failure handling
                log.error("  [%s] enrich failed: %s", cat, e)
                failures.append(f"{cat}: {e}")
                continue
            out[cat] = details
            per_category[cat] = round(seconds, 1)
            if len(details) < expected:
                log.warning("  [%s] enrich returned %d slots, expected %d",
                            cat, len(details), expected)
                partial.append((cat, len(details), expected))
    return out, failures, partial, per_category


def main_mega() -> None:
    """Mega-pipeline path: light Phase A → forbidden filter → mega-curator
    → body verify → rewrite-with-safety → Stage 3 Python filter → enrich.

    Reuses emit_v1_shape, persist_to_supabase, and pack_and_upload from
    the current path. Selection logic is the only thing that changes.
    """
    import os
    from .forbidden_filter import filter_briefs
    from .mega_curator import mega_curate

    today = pipeline_run_date()
    website_dir = Path(__file__).resolve().parent.parent / "website"

    reset_call_stats()
    telemetry: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phases": {}, "per_category": {}, "warnings": [],
        "llm_calls": dict(CALL_STATS), "version": "mega-1",
    }
    t_run = time.monotonic()
    run_id = insert_run({"run_date": today, "status": "running"})

    def _set_phase(name: str, t0: float, **extra) -> None:
        telemetry["phases"][name] = {"seconds": _phase(t0), **extra}
        if run_id:
            update_run(run_id, {"telemetry": telemetry})

    # ---- Resume / DB-config bootstrap ----
    # Categories + sources are now DB-driven. Tables: redesign_categories
    # + redesign_source_configs (admin-editable). Hardcoded News/Science/Fun
    # is gone from this code path; if the admin disables a category or
    # adds a 4th, this loop reflects that immediately.
    categories = db_config.load_categories()
    if not categories:
        raise SystemExit("no active rows in redesign_categories — pipeline cannot run")
    cat_names = [c["name"] for c in categories]
    log.info("=== MEGA active categories from DB: %s ===", cat_names)

    # ---- Partial run (PIPELINE_CATEGORIES=News): one category only ----
    # Checkpoints are disabled (a partial save would clobber the day's
    # full-run trail) and pack_and_upload runs in merge mode — the other
    # categories' content is spliced in from the live latest.zip, so the
    # site never loses a category.
    requested_cats = (os.environ.get("PIPELINE_CATEGORIES") or "").strip()
    partial_cats: list[str] | None = None
    if requested_cats:
        if (os.environ.get("RESUME_FROM") or "").strip():
            raise SystemExit(
                "PIPELINE_CATEGORIES cannot be combined with RESUME_FROM")
        cat_names = _filter_categories(cat_names, requested_cats)
        partial_cats = cat_names
        telemetry["partial_categories"] = cat_names
        log.info("=== PARTIAL RUN — categories: %s (checkpoints off, "
                 "pack merges the rest from live bundle) ===", cat_names)

    # Build a {(name, rss_url): NewsSource} map across every category's
    # primary + backup feed list. Checkpoint hydration uses this to
    # resurrect Source dataclass instances from JSON refs.
    all_sources_for_lookup = []
    for cat_name in cat_names:
        # n=999 → every enabled source. The lookup exists to hydrate
        # checkpoint refs; it must cover ANY source a prior attempt might
        # have picked, not just today's top slice.
        all_sources_for_lookup.extend(db_config.load_sources(cat_name, n=999))
    source_lookup = ckpt.build_source_lookup(all_sources_for_lookup)

    resume_target = ckpt.resume_from()
    if resume_target:
        log.info("=== RESUMING: skipping all stages before '%s' ===", resume_target)

    def _load_or_run(stage: str, runner):
        """If we're resuming past `stage`, load the stage's checkpoint.
        Otherwise run `runner()`, save the result, return it.
        Partial runs never checkpoint — a single-category save would
        clobber the day's full-run trail (used for funnel diagnosis)."""
        if partial_cats is not None:
            return runner()
        if resume_target and ckpt.STAGES.index(stage) < ckpt.STAGES.index(resume_target):
            log.info("  [%s] resume: loading checkpoint", stage)
            return ckpt.load(stage, source_lookup, run_date=today)
        result = runner()
        ckpt.save(stage, result, run_date=today)
        return result

    # ---- Phase A* light: feed metadata only, no body, no LLM ----
    # picked_sources_by_cat feeds stamp_probe_outcomes after persist; it
    # stays empty on RESUME runs (phase A skipped), which disables probe
    # stamping for that attempt — acceptable, resume is the rare path.
    picked_sources_by_cat: dict[str, list] = {}
    # News has only four sources and US-relevant civic stories can sit just
    # below the tenth RSS item after a feed refresh. Sample twelve per source;
    # the later body/rank gates still decide what is publishable.
    PHASE_A_PER_SOURCE = {"News": 12}

    def _phase_a_runner():
        t0 = time.monotonic()
        log.info("=== MEGA Phase A* (light feed fetch) ===")
        out = {}
        for cat_name in cat_names:
            # Fun samples ten feeds before Jev ranks the viable articles;
            # News and Science retain eight. Downstream selection caps stay fixed.
            srcs = db_config.load_sources(cat_name, n=phase_a_source_limit(cat_name))
            picked_sources_by_cat[cat_name] = srcs
            out[cat_name] = phase_a_light(
                cat_name, srcs, max_per_source=PHASE_A_PER_SOURCE.get(cat_name, 4))
        # Drop briefs that ~match a story published in the same section in the last
        # 7 days —
        # the mega path previously had NO past-run dedup at all.
        out = filter_past_duplicate_briefs(out, run_date=today)
        _set_phase("phase_a_light", t0,
                   counts={c: len(b) for c, b in out.items()})
        return out
    briefs_by_cat: dict[str, list[dict]] = _load_or_run("phase_a", _phase_a_runner)

    # ---- Stage 1: forbidden-word filter (Python) ----
    def _stage1_runner():
        t0 = time.monotonic()
        log.info("=== MEGA Stage 1 — forbidden-word filter ===")
        rejected_total = 0
        out = {}
        for cat in briefs_by_cat:
            kept, rejected = filter_briefs(briefs_by_cat[cat])
            out[cat] = kept
            rejected_total += len(rejected)
        _set_phase("stage1_forbidden", t0, dropped=rejected_total)
        log.info("  total kept after forbidden filter: %d (dropped %d)",
                 sum(len(b) for b in out.values()), rejected_total)
        return out
    briefs_by_cat = _load_or_run("stage1", _stage1_runner)

    # ---- Stage 1.2: Jev pre-filter (fail-open; see jev_prefilter.py) ----
    # Runs BEFORE the probe so its per-cat cap isn't spent on livestream
    # pages, shopping guides or content that can never ship.
    def _stage1_jev_runner():
        from .jev_prefilter import prefilter_briefs
        t0 = time.monotonic()
        log.info("=== MEGA Stage 1.2 — Jev pre-filter ===")
        out, report = prefilter_briefs(briefs_by_cat)
        for d in report["dropped"]:
            log.info("  [%s] drop (%s): %s", d["cat"], d["why"], (d["title"] or "")[:80])
        for d in report["would_drop"]:
            log.info("  [%s] shadow, would drop (%s): %s", d["cat"], d["why"], (d["title"] or "")[:80])
        _set_phase("stage1_jev", t0, mode=report["mode"], jev=report["jev"],
                   dropped=len(report["dropped"]), would_drop=len(report["would_drop"]),
                   restored=report["restored"])
        log.info("  jev: %s · dropped %d · kept %d", report["jev"],
                 len(report["dropped"]), sum(len(b) for b in out.values()))
        return out
    _pre_jev_sources = {b.get("_source_name") for bs in briefs_by_cat.values() for b in bs}
    try:
        briefs_by_cat = _load_or_run("stage1_jev", _stage1_jev_runner)
    except FileNotFoundError:
        # Resuming a run that started before this stage existed (or whose
        # stage1_jev save failed). The stage is optional: carry stage1 forward.
        log.warning("  [stage1_jev] no checkpoint for this run — skipping the pre-filter")
    # A source whose briefs the Jev pre-filter dropped did deliver; that is an
    # editorial outcome, not a fetch failure (see stamp_probe_outcomes below).
    _jev_dropped = {n for n in _pre_jev_sources
                    - {b.get("_source_name") for bs in briefs_by_cat.values() for b in bs} if n}

    # ---- Stage 1.5: body probe + length gate + per-cat cap ----
    # Fetch each surviving brief's body in parallel, drop if word_count
    # is outside [PROBE_MIN_WORDS, PROBE_MAX_WORDS], then keep the first
    # PROBE_MAX_PER_CAT (RSS feed order ≈ newest first). The fetched
    # article dict is cached on the brief as "_probe_art" so
    # verify_picks_lazy can skip re-fetching downstream.
    PROBE_MIN_WORDS = 350
    PROBE_MAX_WORDS = 1200
    PROBE_MAX_PER_CAT = 10
    # Keep the full probed catalog so Stage 3 can continue searching after
    # safety or event rejections; only curator input remains capped.
    from . import jev_rank
    rank_mode = jev_rank.mode()
    probe_cap = 10_000
    PROBE_WORKERS = 8

    def _probe_one(brief: dict) -> dict:
        from .news_rss_core import _fetch_and_enrich
        try:
            art = _fetch_and_enrich(dict(brief))
        except Exception as e:  # noqa: BLE001
            log.warning("  probe fetch failed for %s: %s",
                        brief.get("link", "")[:80], e)
            art = {"word_count": 0, "body": "", "og_image": None}
        wc = int(art.get("word_count") or 0)
        return {"brief": brief, "art": art, "wc": wc}

    def _stage1_5_runner():
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.monotonic()
        log.info("=== MEGA Stage 1.5 — body probe + length gate (%d ≤ wc ≤ %d, cap %s) ===",
                 PROBE_MIN_WORDS, PROBE_MAX_WORDS,
                 "none — curator input is capped later")
        out: dict[str, list[dict]] = {}
        kept_total = 0
        dropped_thin = 0
        dropped_long = 0
        per_source: dict[str, dict] = {}
        for cat, briefs in briefs_by_cat.items():
            if not briefs:
                out[cat] = []
                continue
            # Interleave across sources so the cap samples every source
            # instead of eating the pool in priority order (BBC starvation,
            # bug 2026-07-08).
            briefs = _interleave_by_source(briefs)
            with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as ex:
                results = list(ex.map(_probe_one, briefs))
            kept, tally = _partition_probe_results(
                results, PROBE_MIN_WORDS, PROBE_MAX_WORDS, probe_cap)
            out[cat] = kept
            per_source[cat] = tally
            kept_total += len(kept)
            dropped_thin += sum(t["thin"] for t in tally.values())
            dropped_long += sum(t["long"] for t in tally.values())
            log.info("  [%s] probe: %d kept / %d input · %s",
                     cat, len(kept), len(briefs),
                     ", ".join(
                         f"{s}:{t['kept']}/{t['in']}"
                         + (f" (cap_cut {t['cap_cut']})" if t["cap_cut"] else "")
                         for s, t in tally.items()))
        _set_phase("phase_a_probe", t0,
                   counts={c: len(b) for c, b in out.items()},
                   dropped_thin=dropped_thin,
                   dropped_long=dropped_long,
                   kept=kept_total,
                   per_source=per_source)
        return out
    briefs_by_cat = _load_or_run("phase_a_probe", _stage1_5_runner)

    # stamp_probe_outcomes records probe_errors for a source that "produced zero
    # briefs". It must judge that on what the probe produced — after ranking,
    # briefs_by_cat is only the top 10 and a healthy source with no high scorer
    # today would be booked as a fetch failure.
    probe_pool_by_cat = {c: list(b) for c, b in briefs_by_cat.items()}
    if _jev_dropped:
        probe_pool_by_cat["_jev_prefiltered"] = [{"_source_name": n} for n in sorted(_jev_dropped)]

    # ---- Stage 1.7: Jev ranks the probe pool (fail-open; see jev_rank.py) ----
    def _legacy_cut(pool: dict[str, list[dict]]) -> dict[str, list[dict]]:
        return pool

    def _jev_rank_runner():
        from .editorial_routing import route_briefs
        from .news_topics import tag_topics

        def _with_topics(pool: dict[str, list[dict]]) -> dict[str, list[dict]]:
            topic_t0 = time.monotonic()
            reports = {}
            for cat, briefs in pool.items():
                reports[cat] = tag_topics(cat, briefs)
                if briefs:
                    report = reports[cat]
                    log.info("  [%s] Jev topic groups: %d tagged, %d uncertain, %d failed",
                             cat, report["tagged"], report["uncertain"], report["failed"])
            _set_phase("editorial_topics", topic_t0, per_category=reports)
            return pool

        t0 = time.monotonic()
        route_t0 = time.monotonic()
        rank_input, route_report = route_briefs(briefs_by_cat)
        for move in route_report["moved"]:
            log.info("  section route [%s→%s] %.2f: %s",
                     move["from"], move["to"], move["confidence"],
                     move["title"][:70])
        _set_phase("section_route", route_t0, mode=route_report["mode"],
                   scored=route_report["scored"], uncertain=route_report["uncertain"],
                   failed=route_report["failed"], moved=len(route_report["moved"]))
        if rank_mode == "off":
            return _with_topics(_legacy_cut(rank_input))
        log.info("=== MEGA Stage 1.7 — Jev ranking (%s) ===", rank_mode)
        try:
            recent_titles_by_cat = {cat: _recent_published_titles(today, category=cat)
                                    for cat in rank_input}
            ranked, report = jev_rank.rank_briefs(
                rank_input, recent_titles=recent_titles_by_cat)
            log.info("  jev: %s", report["jev"])
            for cat, sent in report["sent"].items():
                log.info("  [%s] %s: %s", cat,
                         "would send" if rank_mode == "shadow" else "to curator",
                         " | ".join(f"{x.get('pick') if x.get('pick') is not None else float('nan'):.2f} "
                                    f"{(x.get('title') or '')[:42]}" for x in sent))
            for d in report["skipped"]:
                log.info("  [%s] passed over (%s): %s", d["cat"], d["why"], (d["title"] or "")[:70])
            for cat, n in report.get("below_floor", {}).items():
                if n:
                    log.warning("  [%s] %d of the sent briefs are BELOW the quality floor "
                                "— thin pool, consider adding sources", cat, n)
            applied = ranked is not None and rank_mode == "on"
            _set_phase("jev_rank", t0, mode=rank_mode, jev=report["jev"], applied=applied,
                       pool={c: len(b) for c, b in rank_input.items()},
                       pair_calls=report["pair_calls"], passed_over=len(report["skipped"]),
                       past_event_calls=report["past_event_calls"],
                       past_event_input_tokens=report["past_event_input_tokens"],
                       past_event_output_tokens=report["past_event_output_tokens"],
                       below_floor=report.get("below_floor", {}))
            if applied:
                ranked = _with_topics(ranked)
                from .news_global_rank import rerank_news_catalog
                news_t0 = time.monotonic()
                ranked["News"], news_report = rerank_news_catalog(
                    ranked.get("News") or [], recent_titles_by_cat.get("News") or [])
                _set_phase("news_global_rank", news_t0, **news_report)
                return ranked
        except Exception as e:  # noqa: BLE001 — an optional stage must never break the run
            log.warning("  jev_rank stage failed (%s) — using the legacy cut", e)
        for b in (b for bs in rank_input.values() for b in bs):
            if "_jev_rank" in b:                  # shadow / failure: keep the evidence, not the effect
                b["_jev_rank_shadow"] = b.pop("_jev_rank")
        return _with_topics(_legacy_cut(rank_input))
    try:
        briefs_by_cat = _load_or_run("jev_rank", _jev_rank_runner)
    except FileNotFoundError:
        log.warning("  [jev_rank] no checkpoint for this run — using the legacy cut")
        briefs_by_cat = _legacy_cut(briefs_by_cat)
    # Derived from the data, so a resumed run takes the same path as the original.
    jev_ranked = any("_jev_rank" in b for bs in briefs_by_cat.values() for b in bs)

    # ---- Stage 2: mega-curator (1 LLM call, 5 ranked per cat) ----
    def _stage2_runner():
        t0 = time.monotonic()
        log.info("=== MEGA Stage 2 — curator picks 5 ranked per cat ===")
        curator_pool = (jev_rank.for_curator(briefs_by_cat) if jev_ranked else
                        {cat: briefs[:PROBE_MAX_PER_CAT] for cat, briefs in briefs_by_cat.items()})
        ranked, _vet, _reasoning = mega_curate(curator_pool)
        _set_phase("stage2_curator", t0,
                   picks={c: len(p) for c, p in ranked.items()})
        return ranked
    ranked_by_cat = _load_or_run("stage2_picks", _stage2_runner)

    # ---- Body + og:image verify on rank 1-4 (lazy fetch) ----
    def _verify_runner():
        t0 = time.monotonic()
        log.info("=== MEGA verify body + og:image on rank 1-4 ===")
        vstats: dict = {}
        out = verify_picks_lazy(ranked_by_cat, max_top=4, stats=vstats)
        # Deep backfill: probed-but-unranked briefs join the spare pool so
        # Stage-3 promotion can dig past the curator's 5 ranks instead of
        # starving the category.
        for cat, briefs in briefs_by_cat.items():
            extra = _unpicked_probe_spares(briefs, ranked_by_cat.get(cat) or [],
                                           keep_order=jev_ranked)
            if extra:
                out.setdefault(cat, []).extend(extra)
                log.info("  [%s] +%d probe-pool spares for Stage-3 backfill",
                         cat, len(extra))
        verified_counts = {c: sum(1 for s in v if not s.get("_unverified_spare"))
                           for c, v in out.items()}
        _set_phase("verify", t0, verified=verified_counts, per_source=vstats)
        for cat, ws in out.items():
            verified = [s for s in ws if not s.get("_unverified_spare")]
            log.info("  [%s] %d verified + %d spare ranks",
                     cat, len(verified), len(ws) - len(verified))
        return out
    stories_by_cat = _load_or_run("verify", _verify_runner)

    # ---- Image optimize + upload to Supabase Storage ----
    t = time.monotonic()
    log.info("=== MEGA images (verified picks only) ===")
    for cat, ws in stories_by_cat.items():
        verified_only = [s for s in ws if not s.get("_unverified_spare")]
        process_images(verified_only, today, website_dir)
    _set_phase("images", t)

    # ---- Phase C: rewrite up to 4 per cat (with self-scored safety) ----
    def _rewrite_runner():
        t0 = time.monotonic()
        log.info("=== MEGA rewrite (4 per cat, with safety scores) ===")
        out: dict[str, dict] = {}
        for cat, ws in stories_by_cat.items():
            verified = [s for s in ws if not s.get("_unverified_spare")][:4]
            if not verified:
                log.warning("  [%s] no verified picks to rewrite", cat)
                out[cat] = {"articles": [], "_winners": []}
                continue
            articles = [(i, w["winner"]) for i, w in enumerate(verified)]
            try:
                # Pass category so the rewriter prompt picks up the
                # category-specific style block (News=factual, Science=
                # analogies, Fun=playful).
                rewrite_res = tri_variant_rewrite(articles, category=cat)
            except Exception as e:  # noqa: BLE001
                log.error("  [%s] rewrite failed: %s", cat, e)
                rewrite_res = {"articles": []}
            out[cat] = {**rewrite_res, "_winners": verified}
        _set_phase("rewrite", t0)
        return out
    rewrites_by_cat: dict[str, dict] = _load_or_run("rewrite", _rewrite_runner)

    publication_guards = {}
    publication_review_budget = HistoryReviewBudget()

    def _history_guard(category):
        if category not in publication_guards:
            publication_guards[category] = PublicationHistoryGuard.load(
                today, category, budget=publication_review_budget)
        return publication_guards[category]

    # ---- Stage 3: Python safety filter on rewritten bodies ----
    def _safety_runner():
        t0 = time.monotonic()
        log.info("=== MEGA Stage 3 — Python safety filter "
                 "(strict dims ≥3 / news dims ≥4 = REJECT) ===")
        final_stories: dict[str, list[dict]] = {}
        final_variants: dict[str, dict[int, dict]] = {}
        s3_per_source: dict[str, dict] = {}
        for cat, bundle in rewrites_by_cat.items():
            winners = bundle.get("_winners") or []
            excluded_ids = {i for i, w in enumerate(winners)
                            if editorial_exclusion(w.get("winner") or {})
                            or (explicit_section(w.get("_brief") or {}) not in {None, cat})
                            or below_quality_floor(w.get("_brief") or {})
                            or (cat == "Fun" and low_fun_value(w.get("_brief") or {}))}
            excluded_ids.update(i for i, w in enumerate(winners)
                                if i not in excluded_ids and not _history_guard(cat).allows(winner_brief(w)))
            if excluded_ids:
                log.info("  [%s] excluding %d editorially ineligible rewrites (checkpoint guard)",
                         cat, len(excluded_ids))
            rewrite_res = {"articles": [a for a in bundle.get("articles") or []
                                         if a.get("source_id") not in excluded_ids]}
            # source_id → source article, so the wc-repair pass can draw
            # real details from the source when a body needs expanding.
            srcs_by_id = {i: (w or {}).get("winner") or {}
                          for i, w in enumerate(winners)}
            kept, rejected = filter_safe_rewrites(rewrite_res, srcs_by_id, category=cat)
            cs = s3_per_source.setdefault(cat, {})
            for a in rejected:
                sid = a.get("source_id")
                w = winners[sid] if isinstance(sid, int) and 0 <= sid < len(winners) else None
                name = w["source"].name if w and w.get("source") else "?"
                e = cs.setdefault(name, {"shipped": 0, "safety_rejected": 0})
                e["safety_rejected"] += 1
                reason = ((a.get("_safety_eval") or {}).get("reason") or "")[:120]
                log.info("  [%s] Stage-3 REJECT %s: %s", cat, name, reason)
            kept_by_sid: dict[int, dict] = {a["source_id"]: a for a in kept
                                             if isinstance(a.get("source_id"), int)}
            survived_winners: list[dict] = []
            survived_articles: list[dict] = []
            for i, w in enumerate(winners):
                if i in kept_by_sid:
                    survived_winners.append(w)
                    survived_articles.append(kept_by_sid[i])
            if len(survived_winners) > 3:
                # Safety may remove a diverse pick and move rank 4 into the
                # published three. Reapply the soft topic preference to the
                # already-safe rewrites without making another model call.
                from .mega_curator import _prefer_top3_topic_diversity
                indexed = [{"rank": i + 1, "source": w["source"],
                            "brief": w.get("_brief") or {}, "index": i}
                           for i, w in enumerate(survived_winners)]
                ordered = _prefer_top3_topic_diversity({cat: indexed})[cat]
                survived_winners = [survived_winners[p["index"]] for p in ordered]
                survived_articles = [survived_articles[p["index"]] for p in ordered]
            spare_pool = [s for s in stories_by_cat.get(cat, [])
                          if s.get("_unverified_spare")]
            promotions = 0

            def _drain(pool):
                # Diversity-aware spare promotion: prefer a source NOT
                # already in the surviving top 3, and skip any spare that
                # is the same story as one already shipping. Falls back to
                # a duplicate source only when nothing else survives.
                nonlocal promotions
                while len(survived_winners) < 3 and pool:
                    used_names = {w["source"].name for w in survived_winners
                                  if w.get("source")}
                    used_titles = {(w.get("winner") or {}).get("title") or ""
                                   for w in survived_winners}
                    used_briefs = [
                        w.get("_brief") or w.get("_winner_brief")
                        or w.get("winner") or {}
                        for w in survived_winners
                    ]
                    used_event_groups = {
                        (b.get("_event_group") or "").strip()
                        for b in used_briefs if (b.get("_event_group") or "").strip()
                    }
                    from .news_topics import topic_group
                    used_topic_groups = {topic_group(b) for b in used_briefs if topic_group(b)}
                    pw, pa = promote_spare_and_rewrite(
                        cat, pool, used_source_names=used_names,
                        used_titles=used_titles, used_briefs=used_briefs,
                        used_event_groups=used_event_groups,
                        used_topic_groups=used_topic_groups,
                        history_guard=_history_guard(cat))
                    if not pw:
                        break
                    survived_winners.append(pw)
                    survived_articles.append(pa)
                    promotions += 1

            _drain(spare_pool)

            def _topics():
                from .news_topics import topic_group
                return {topic_group(winner_brief(w)) for w in survived_winners} - {""}

            def _needs_topics():
                return len(survived_winners) >= 3 and 0 < len(_topics()) < 3

            def _improve_topics(pool):
                nonlocal promotions
                while _needs_topics() and pool:
                    pw, pa = promote_spare_and_rewrite(
                        cat, pool, used_briefs=[winner_brief(w) for w in survived_winners],
                        used_source_names={w["source"].name for w in survived_winners},
                        used_topic_groups=_topics(), require_new_topic=True,
                        history_guard=_history_guard(cat))
                    if not pw:
                        break
                    survived_winners.append(pw)
                    survived_articles.append(pa)
                    promotions += 1

            # A safety rejection can leave three publishable stories but only
            # two sources. The ordinary refill runs only when the story count
            # is short, so try a *new-source* spare here as well. This is a
            # preference, not a license to ship an unvetted or wrong-section
            # article merely to satisfy the digest's 3/3 source metric.
            needs_publisher = cat == "Science" and len({
                publisher_key(w.get("source")) for w in survived_winners
            } - {""}) < SCIENCE_MIN_PUBLISHERS
            needs_source = len({
                w["source"].name for w in survived_winners if w.get("source")
            }) < 3
            if len(survived_winners) >= 3 and (needs_source or needs_publisher) and spare_pool:
                used_names = {w["source"].name for w in survived_winners if w.get("source")}
                used_briefs = [w.get("_brief") or w.get("_winner_brief")
                               or w.get("winner") or {} for w in survived_winners]
                from .news_topics import topic_group
                pw, pa = promote_spare_and_rewrite(
                    cat, spare_pool, used_source_names=used_names,
                    used_briefs=used_briefs,
                    used_event_groups={(b.get("_event_group") or "").strip()
                                       for b in used_briefs if b.get("_event_group")},
                    used_topic_groups={topic_group(b) for b in used_briefs if topic_group(b)},
                    require_new_source=True,
                    used_publishers={publisher_key(w.get("source")) for w in survived_winners},
                    require_new_publisher=needs_publisher,
                    history_guard=_history_guard(cat),
                )
                if pw:
                    survived_winners.append(pw)
                    survived_articles.append(pa)
                    promotions += 1

            _improve_topics(spare_pool)

            # Short on count or topics? Try deeper items in today's feeds.
            dug = 0
            if (len(survived_winners) < 3 or _needs_topics()) and picked_sources_by_cat.get(cat):
                seen_links: set[str] = set()
                for r in (ranked_by_cat.get(cat) or []):
                    seen_links.add(((r.get("brief") or {}).get("link")) or "")
                for s in stories_by_cat.get(cat, []):
                    b = s.get("_winner_brief") or s.get("_brief") or {}
                    seen_links.add((b.get("link")) or "")
                    seen_links.add(((s.get("winner") or {}).get("link")) or "")
                for w in survived_winners:
                    seen_links.add(((w.get("winner") or {}).get("link")) or "")
                # Include every initially probed link, even ones rejected by
                # ranking or routing. Otherwise a deep feed fetch can re-add
                # a low-quality or wrong-section first-round candidate.
                for b in probe_pool_by_cat.get(cat, []):
                    seen_links.add(b.get("link") or "")
                dig_pool = _deep_dig_spares(cat, picked_sources_by_cat[cat],
                                            seen_links, max_per_source=15)
                if dig_pool:
                    dig_pool = _gate_deep_dig_spares(cat, dig_pool)
                    if dig_pool:
                        from .news_topics import tag_topics
                        tag_topics(cat, [s.get("_winner_brief") or {} for s in dig_pool])
                if dig_pool:
                    before = len(survived_winners)
                    log.info("  [%s] short on count or topic variety (%d candidates) — deep-digging "
                             "%d more feed items", cat, before, len(dig_pool))
                    _drain(dig_pool)
                    _improve_topics(dig_pool)
                    dug = len(survived_winners) - before

            survived_winners, survived_articles = _prefer_final_source_diversity(
                survived_winners, survived_articles)
            if cat in {"Science", "News"}:
                choices = [{"source": w.get("source"),
                            "brief": w.get("_brief") or w.get("_winner_brief") or {},
                            "winner": w, "article": a}
                           for w, a in zip(survived_winners, survived_articles)]
                choices = (prefer_science_publishers(choices) if cat == "Science"
                           else prefer_important_news(choices))
                survived_winners = [x["winner"] for x in choices]
                survived_articles = [x["article"] for x in choices]
            choices = prefer_final_editorial_diversity(cat, [
                {"source": w.get("source"), "brief": winner_brief(w), "winner": w, "article": a}
                for w, a in zip(survived_winners, survived_articles)])
            survived_winners = [x["winner"] for x in choices]
            survived_articles = [x["article"] for x in choices]
            final_stories[cat] = survived_winners[:3]
            final_variants[cat] = {i: art for i, art in enumerate(survived_articles[:3])}
            from .news_topics import topic_group
            final_topics = {topic_group(winner_brief(w)) for w in final_stories[cat]} - {""}
            if len(final_topics) < len(final_stories[cat]):
                telemetry["warnings"].append(
                    f"{cat}: only {len(final_topics)} known distinct final topics after safe replacements")
            if cat == "News" and not any(important_news(
                    w.get("_brief") or w.get("_winner_brief") or {}) for w in final_stories[cat]):
                telemetry["warnings"].append("News: no qualified high-importance story in final selection")
            if cat == "Science":
                publishers = {publisher_key(w.get("source")) for w in final_stories[cat]} - {""}
                if len(publishers) < SCIENCE_MIN_PUBLISHERS:
                    telemetry["warnings"].append(
                        f"Science: only {len(publishers)}/{SCIENCE_MIN_PUBLISHERS} safe publishers available")
            if len(final_stories[cat]) >= 3:
                unique_sources = len({w["source"].name for w in final_stories[cat]
                                      if w.get("source")})
                min_sources = 2 if cat == "Science" else 3
                if unique_sources < min_sources:
                    telemetry["warnings"].append(
                        f"{cat}: only {unique_sources}/{min_sources} distinct safe sources available")
            for w in final_stories[cat]:
                name = w["source"].name if w.get("source") else "?"
                cs.setdefault(name, {"shipped": 0, "safety_rejected": 0})["shipped"] += 1
            if promotions:
                telemetry["warnings"].append(
                    f"{cat}: Stage 3 promoted {promotions} safe spare(s)"
                    + (f" ({dug} via deep-dig into today's feeds)" if dug else ""))
            if len(survived_winners) < 3:
                log.info("  [%s] %d fresh stories after catalog and feed search",
                         cat, len(survived_winners))
            log.info("  [%s] final: %d published from %d safe candidates "
                     "(%d rejected, %d promoted, %d deep-dug)",
                     cat, len(final_stories[cat]), len(survived_winners),
                     len(rejected), promotions, dug)
        _set_phase("stage3_safety", t0, per_source=s3_per_source,
                   published_counts={c: len(ws) for c, ws in final_stories.items()},
                   publisher_counts={c: len({publisher_key(w.get("source")) for w in ws} - {""})
                                     for c, ws in final_stories.items()})
        # Bundle both products into a single checkpoint payload.
        return {"final_stories_by_cat": final_stories, "final_variants_by_cat": final_variants}

    safety_bundle = _load_or_run("stage3_safety", _safety_runner)
    final_stories_by_cat = safety_bundle["final_stories_by_cat"]
    final_variants_by_cat = safety_bundle["final_variants_by_cat"]
    # Checkpoint resumes and late promotions get the same lexical-gate-free audit.
    try:
        for cat, stories in final_stories_by_cat.items():
            assert_history_clear({cat: stories}, _history_guard(cat))
    finally:
        telemetry["publication_history"] = {cat: guard.report()
                                            for cat, guard in publication_guards.items()}

    # Process images for any newly promoted spares (their image hasn't
    # been processed yet — verify_picks_lazy only ran image-fetch on the
    # initial rank-1..4 picks).
    for cat, stories in final_stories_by_cat.items():
        unprocessed = [s for s in stories if not s.get("_image_local")]
        if unprocessed:
            log.info("[%s] processing %d promoted spare images", cat, len(unprocessed))
            process_images(unprocessed, today, website_dir)

    # ---- Phase D: enrich the 9 survivors ----
    enrich_failures: list[str] = []
    def _enrich_runner():
        t0 = time.monotonic()
        log.info("=== MEGA Phase D — enrich 9 survivors only ===")
        try:
            workers = max(1, min(2, int(os.environ.get("ENRICH_WORKERS", "2"))))
        except ValueError:
            log.warning("invalid ENRICH_WORKERS; using 2")
            workers = 2
        log.info("  enrich concurrency: %d categor%s", workers,
                 "y" if workers == 1 else "ies")
        out, failures, partial, per_category = enrich_survivors(
            final_stories_by_cat, final_variants_by_cat, max_workers=workers)
        enrich_failures.extend(failures)
        telemetry["warnings"].extend(
            f"{cat}: partial enrich ({got}/{expected})"
            for cat, got, expected in partial)
        _set_phase("enrich", t0, workers=workers, per_category=per_category)
        return out
    final_details_by_cat = _load_or_run("enrich", _enrich_runner)
    failures = enrich_failures

    if failures:
        msg = f"{len(failures)} enrich failures: " + " | ".join(failures)
        if run_id:
            update_run(run_id, {"status": "failed",
                                 "finished_at": datetime.now(timezone.utc).isoformat(),
                                 "notes": msg, "telemetry": telemetry})
        log.error("Aborting — %s", msg)
        raise SystemExit(1)

    # ---- Reuse emit + persist + pack from the current path ----
    # Emit always re-runs (writes to disk; in CI the disk is fresh each
    # run, so cached checkpoints alone wouldn't have the JSON files
    # pack_and_upload reads). When resuming, the upstream stages were
    # loaded from DB checkpoints — we still need their data on disk for
    # the bundler.
    t = time.monotonic()
    log.info("=== EMIT + PERSIST + PACK (shared with current pipeline) ===")
    emit_v1_shape(final_stories_by_cat, final_variants_by_cat,
                  final_details_by_cat, today, website_dir)
    _set_phase("emit", t)

    t = time.monotonic()
    count = 0
    if run_id:
        # Skip persist when resuming from a later stage — the stories are
        # already in the DB from the original run. (Re-persisting would be
        # safe via the unique constraint, but it's wasted work.)
        if resume_target and ckpt.STAGES.index("persist") < ckpt.STAGES.index(resume_target):
            log.info("=== resume: skipping persist (already done) ===")
        else:
            if partial_cats:
                # Replacing today's content for these categories — mark the
                # superseded rows + purge their search-index entries first.
                _archive_replaced_stories(partial_cats, today)
            count = persist_to_supabase(final_stories_by_cat,
                                         final_variants_by_cat, today, run_id)
            update_run(run_id, {"status": "persisted",
                                 "notes": f"stories persisted: {count}",
                                 "telemetry": telemetry})
            if partial_cats is None:
                ckpt.save("persist", {"stories_persisted": count}, run_date=today)
    _set_phase("persist", t, stories_persisted=count)

    # Close the pickup loop: record outcomes for picked-but-unshipped
    # sources (probe_* counters + next_pickup bump) so a failing source
    # degrades gracefully instead of hogging a rotation slot for weeks.
    if picked_sources_by_cat:
        shipped_names = {(s.get("source") and s["source"].name) or ""
                         for stories in final_stories_by_cat.values()
                         for s in stories}
        stamp_probe_outcomes(picked_sources_by_cat, probe_pool_by_cat, shipped_names)
    else:
        log.info("probe-stamp skipped (resume run — picked sources unknown)")

    t = time.monotonic()
    log.info("=== PACK + UPLOAD ZIP ===")
    upload_ok = False
    upload_err: str | None = None
    # A 1-2-story category still publishes its qualified fresh articles.
    ok_cats, thin_cats = _split_publishable(final_stories_by_cat, min_per_cat=1)
    short_cats = [c for c in ok_cats
                  if len(final_stories_by_cat.get(c) or []) < 3]
    try:
        from .pack_and_upload import main as _pack_upload
        if thin_cats and not ok_cats:
            # Nothing publishable at all — refuse; site keeps its bundle.
            raise SystemExit(
                f"no publishable category (all 0 stories): {thin_cats}")
        if thin_cats:
            telemetry["warnings"].append(
                f"degraded publish — {', '.join(thin_cats)} kept previous "
                f"live content; fresh: {', '.join(ok_cats)}")
            log.warning("degraded publish — %s keep live content; "
                        "publishing fresh %s via merge", thin_cats, ok_cats)
        if short_cats:
            log.info("pack will publish fresh catalog survivors for %s", short_cats)
        os.environ["PACK_FRESH_CATALOG_ONLY"] = "1"
        if thin_cats:
            os.environ["PACK_MERGE_CATEGORIES"] = ",".join(ok_cats)
        elif partial_cats:
            # Merge mode: pack splices the other categories' content from
            # the live latest.zip; validation still gates the publish.
            os.environ["PACK_MERGE_CATEGORIES"] = ",".join(partial_cats)
        _pack_upload()
        upload_ok = True
    except SystemExit as e:
        upload_err = f"pack_and_upload aborted (SystemExit {e.code})"
    except Exception as e:  # noqa: BLE001
        upload_err = f"pack_and_upload exception: {e}"
    if upload_err:
        log.error(upload_err)
    _set_phase("pack_upload", t, ok=upload_ok, error=upload_err)

    telemetry["llm_calls"] = dict(CALL_STATS)
    if run_id:
        terminal = {"finished_at": datetime.now(timezone.utc).isoformat(),
                    "telemetry": telemetry}
        if upload_ok:
            # Rotation stamping moved here from persist_to_supabase: only a
            # DEPLOYED bundle counts as "used" for source rotation. On a
            # degraded publish, a thin category's stories did NOT deploy.
            deployed_by_cat = {c: s for c, s in final_stories_by_cat.items()
                               if c not in thin_cats}
            stamp_shipped_sources(deployed_by_cat)
            terminal["status"] = ("completed_with_warnings" if telemetry["warnings"]
                                   else "completed")
            terminal["notes"] = (f"stories persisted: {count}; deployed "
                                  f"({len(telemetry['warnings'])} warnings)")
        else:
            terminal["status"] = "deploy_failed"
            terminal["notes"] = (f"stories persisted: {count}; "
                                  f"deploy failed: {upload_err}")
        update_run(run_id, terminal)

    log.info("=== MEGA DONE (%.1fs) · %d total stories · LLM calls: %s",
             _phase(t_run),
             sum(len(v) for v in final_stories_by_cat.values()),
             {k: v for k, v in CALL_STATS.items() if v})
    for w in telemetry["warnings"]:
        log.warning("  ⚠  %s", w)
    if not upload_ok:
        raise SystemExit(2)


if __name__ == "__main__":
    import os as _os
    variant = (_os.environ.get("PIPELINE_VARIANT") or "current").lower()
    if variant == "mega":
        log.info(">>> PIPELINE_VARIANT=mega — running mega orchestrator")
        main_mega()
    else:
        main()
