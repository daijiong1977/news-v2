"""Stage 2 of the mega pipeline: a single LLM call sees all (forbidden-
filtered) RSS briefs across all 3 categories and picks 6 ranked
candidates per cat with topic-cluster reasoning + cross-cat dedup.

ranks 1-4 → fed to the rewriter (4 per cat × 3 cats = 12 rewrites)
ranks 5-6 → spares; promoted only if Stage 3 (post-rewrite safety vet)
            rejects too many of the rank 1-4 picks for a category

Returns a dict suitable for downstream stages:
    {cat: [{"source": <Source>, "winner": <art>, "winner_slot": "rank_N"}, ...]}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .news_rss_core import deepseek_reasoner_call

log = logging.getLogger("mega-curator")


MEGA_CURATOR_SYSTEM_PROMPT = """You are the Editor-in-Chief of "News Oh, Ye!", a
daily news site for kids ages 8-13. The pipeline mined ~60 candidates from
9 RSS feeds (3 News + 3 Science + 3 Fun), ran a forbidden-word safety
filter, and now hands you the survivors.

YOUR JOB: rank 6 candidates per category (18 total), in order, ready for
rewriting. Ranks 1-4 are the rewrite pool. Ranks 5-6 are spares — only
used if a rank-1..4 pick later fails the post-rewrite safety vet.

OUTPUT CONTRACT (strict): exactly 6 ranked picks per category.

ALGORITHM:

  Step 1 — VET: For each candidate, score:
      safety dims (0-5, lower is safer): violence, sexual, substance,
        language, fear, adult_themes, distress, bias
      interest dims (0-5, higher is better): importance, fun_factor,
        kid_appeal
    Drop any with safety total > 6 OR any safety dim ≥ 4 — these can
    never be picked.

  Step 2 — CLUSTER: Identify topic clusters across the full pool. A
    cluster = 2+ candidates covering the same real-world story. Mark
    each candidate's cluster_id. We pick at most ONE per cluster across
    all 3 categories combined.

  Step 3 — PICK 6 PER CAT, RANKED:
    Within each category:
      - Prefer candidates with high interest_peak (max of importance /
        fun / kid_appeal) AND low safety_total.
      - Prefer DIFFERENT topic clusters across the 6 picks (topic
        diversity within a cat).
      - Prefer DIFFERENT sources across the 6 picks.
      - Lower-numbered slot in source ordering ties broken by interest.
    Cross-category tiebreak (when two cats want a candidate from the
    same cluster):
      News × Fun     → keep the Fun pick
      News × Science → keep the Science pick
      Fun  × Science → keep the Fun pick
    The losing category picks a candidate from a DIFFERENT cluster to
    fill that rank.

OUTPUT — valid JSON only, no markdown fences:
{
  "vet": [
    {"id": <int>, "safety": {"violence":N,"sexual":N,"substance":N,"language":N,
                              "fear":N,"adult_themes":N,"distress":N,"bias":N,
                              "total":N},
     "interest": {"importance":N,"fun_factor":N,"kid_appeal":N,"peak":N},
     "cluster_id": "<short string>"},
    ...one entry per candidate...
  ],
  "picks": {
    "News":    [{"rank":1,"id":N},{"rank":2,"id":N},{"rank":3,"id":N},
                {"rank":4,"id":N},{"rank":5,"id":N},{"rank":6,"id":N}],
    "Science": [...6 entries...],
    "Fun":     [...6 entries...]
  },
  "reasoning": "1-3 sentences: cross-cat dups you caught, topic
                diversity choices, cases where rank-1 isn't choice_1."
}"""


def _build_mega_curator_input(briefs_by_cat: dict[str, list[dict]]) -> tuple[str, dict[int, dict]]:
    """Build the user message + a registry mapping cid → metadata.

    `briefs_by_cat = {cat: [brief, ...]}` where each brief is the RSS shape
    plus a `_source` (Source) reference attached by the caller. The brief
    has `title`, `summary`, `link`, optionally `body` and `og_image`.
    """
    registry: dict[int, dict] = {}
    cid = 0
    by_cat_lines: dict[str, list[str]] = {cat: [] for cat in briefs_by_cat}

    for cat, briefs in briefs_by_cat.items():
        for brief in briefs:
            title = (brief.get("title") or "")[:240]
            summary = (brief.get("summary") or "")[:600]
            src_name = (brief.get("_source_name") or "?")
            line = (f"  [id={cid}] src={src_name}\n"
                    f"     title: {title}\n"
                    f"     summary: {summary}")
            by_cat_lines[cat].append(line)
            registry[cid] = {
                "cat": cat,
                "src_name": src_name,
                "source": brief.get("_source"),
                "brief": brief,
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
    parts.append(
        "Vet, cluster, and pick 6 ranked per category. "
        "Return the JSON shape from the system prompt."
    )
    return "\n".join(parts), registry


def mega_curate(
    briefs_by_cat: dict[str, list[dict]]
) -> tuple[dict[str, list[dict]], dict, str]:
    """Run the mega-curator. Returns:
      (picks_by_cat, vet_by_id, reasoning)

    `picks_by_cat = {cat: [{rank, source, brief, vet}, ... up to 6 entries]}`
    sorted by rank ascending. Empty list for any cat the curator couldn't
    fill.
    """
    user_msg, registry = _build_mega_curator_input(briefs_by_cat)
    if not registry:
        log.warning("mega-curator: no input candidates")
        return {cat: [] for cat in briefs_by_cat}, {}, ""

    log.info("mega-curator: %d total candidates across %d categories",
             len(registry), len(briefs_by_cat))

    # 12k is a safe ceiling for ~90 candidates: each vet entry is ~80
    # tokens, plus 18 picks + reasoning. 6k truncated on the first run.
    res = deepseek_reasoner_call(MEGA_CURATOR_SYSTEM_PROMPT, user_msg,
                                  max_tokens=12000)
    vet = {v["id"]: v for v in (res.get("vet") or []) if isinstance(v.get("id"), int)}
    raw_picks = res.get("picks") or {}
    reasoning = res.get("reasoning") or ""

    if reasoning:
        log.info("mega-curator reasoning: %s", reasoning[:400])

    out: dict[str, list[dict]] = {cat: [] for cat in briefs_by_cat}
    for cat in briefs_by_cat:
        cat_picks = raw_picks.get(cat) or []
        # Sort by rank then de-dup by id
        sorted_picks = sorted(cat_picks, key=lambda p: int(p.get("rank") or 99))
        seen_ids: set[int] = set()
        for p in sorted_picks:
            cid = p.get("id")
            rank = p.get("rank")
            if not isinstance(cid, int) or cid in seen_ids:
                continue
            info = registry.get(cid)
            if not info or info["cat"] != cat:
                log.warning("mega-curator returned cid=%d for %s (registry=%s)",
                            cid, cat, info["cat"] if info else "?")
                continue
            seen_ids.add(cid)
            out[cat].append({
                "rank": rank,
                "id": cid,
                "source": info["source"],
                "brief": info["brief"],
                "vet": vet.get(cid) or {},
            })

    for cat, picks in out.items():
        log.info("  curator [%s] %d ranked: %s", cat, len(picks),
                 ", ".join(f"rank{p['rank']}={p['source'].name}" for p in picks[:6]))
    return out, vet, reasoning
