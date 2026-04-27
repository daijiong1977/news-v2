"""Stage 2 of the mega pipeline: a single LLM call sees all (forbidden-
filtered) RSS briefs across all 3 categories and picks 5 ranked
candidates per cat with topic-cluster reasoning + cross-cat dedup.

ranks 1-4 → fed to the rewriter (4 per cat × 3 cats = 12 rewrites)
rank 5    → spare; promoted only if Stage 3 (post-rewrite safety vet)
            rejects one of the rank 1-4 picks for a category

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
daily news site for kids ages 8-13. The pipeline mined ~36 candidates from
9 RSS feeds (3 News + 3 Science + 3 Fun, up to 12 per cat), ran a
forbidden-word safety filter, and now hands you the survivors.

YOUR JOB: rank 5 candidates per category (15 total), in order, ready for
rewriting. Ranks 1-4 are the rewrite pool. Rank 5 is the spare — only
used if a rank-1..4 pick later fails the post-rewrite safety vet.

OUTPUT CONTRACT (strict): exactly 5 ranked picks per category. Score
ONLY the 15 picks inline — do NOT emit per-candidate vet for the full
pool (that blows the token budget).

ALGORITHM (internal, don't output intermediate work):

  1. VET silently: for each candidate rate safety (0-5, lower is safer)
     across violence, sexual, substance, language, fear, adult_themes,
     distress, bias — and interest (0-5, higher is better) across
     importance, fun_factor, kid_appeal. Skip any with safety total > 6
     or any safety dim ≥ 4 — they can never be picked.

  2. CLUSTER: group candidates covering the same real-world story into
     topic clusters. Pick AT MOST ONE candidate per cluster across all
     3 categories combined.

  3. PICK 5 PER CAT, RANKED:
     - Prefer high interest_peak (max of importance / fun / kid_appeal)
       AND low safety_total.
     - Prefer DIFFERENT topic clusters within a cat.
     - HARD RULE — source diversity in top 3: ranks 1, 2, 3 of each
       category MUST come from THREE DIFFERENT sources (different
       `src=` value). Only break this rule if the category has fewer
       than 3 sources contributing candidates after the safety vet —
       in that case state so explicitly in `reasoning`. Ranks 4-5 may
       repeat a source freely (they are spares).
     - Cross-category tiebreak (same cluster wanted by two cats):
         News × Fun     → keep the Fun pick
         News × Science → keep the Science pick
         Fun  × Science → keep the Fun pick
       Losing category picks from a DIFFERENT cluster to fill that rank.

OUTPUT — valid JSON only, no markdown fences. For each of the 15 picks
include its safety + interest scores inline so the downstream pipeline
has the vet signal. Use SHORT integer scores, no totals/peaks, no prose.

{
  "picks": {
    "News": [
      {"rank":1,"id":N,"cluster_id":"<short>",
       "safety":{"violence":N,"sexual":N,"substance":N,"language":N,
                 "fear":N,"adult_themes":N,"distress":N,"bias":N},
       "interest":{"importance":N,"fun_factor":N,"kid_appeal":N}},
      ...5 entries ranked 1..5...
    ],
    "Science": [...5 entries...],
    "Fun":     [...5 entries...]
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
        "Vet, cluster, and pick 5 ranked per category. "
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

    # Reasoner thinking budget shares max_tokens with output. 6k truncated
    # at 34 candidates (run 24921275967), 12k truncated at 89, and 12k
    # also truncated today on DeepSeek V4 Pro at 27 candidates (run
    # 24997954155) — V4 Pro produces longer chain-of-thought than the
    # earlier provider. Bumped to 20k to give the reasoner ~14k of
    # thinking room above the slim 6k output budget.
    res = deepseek_reasoner_call(MEGA_CURATOR_SYSTEM_PROMPT, user_msg,
                                  max_tokens=20000)
    raw_picks = res.get("picks") or {}
    reasoning = res.get("reasoning") or ""

    if reasoning:
        log.info("mega-curator reasoning: %s", reasoning[:400])

    # Build vet dict from the inline scores on the 18 picks
    vet: dict[int, dict] = {}
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
            # Extract inline scores for downstream pipeline
            pick_vet = {
                "id": cid,
                "safety": p.get("safety") or {},
                "interest": p.get("interest") or {},
                "cluster_id": p.get("cluster_id") or "",
            }
            vet[cid] = pick_vet
            out[cat].append({
                "rank": rank,
                "id": cid,
                "source": info["source"],
                "brief": info["brief"],
                "vet": pick_vet,
            })

    out = _enforce_top3_source_diversity(out)

    for cat, picks in out.items():
        log.info("  curator [%s] %d ranked: %s", cat, len(picks),
                 ", ".join(f"rank{p['rank']}={p['source'].name}" for p in picks[:6]))
    return out, vet, reasoning


def _enforce_top3_source_diversity(
    ranked_by_cat: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Enforce: top 3 ranks per category must come from 3 DIFFERENT
    sources. The system prompt asks for this as a HARD RULE but the LLM
    sometimes still picks duplicates when one source dominates the pool.

    Strategy per category:
      - Look at ranks 1-3. If a source repeats, find a swap candidate
        from ranks 4-5 (spares) whose source is NOT already in top 3.
      - Swap the WORST-rank duplicate (e.g. rank 3) with that spare.
      - The spare loses its rank-4/5 slot and gets the vacated rank.
      - Idempotent: clean input passes through; degraded categories
        (fewer than 3 distinct sources in the curator's top 5) are
        left alone with a warning.
    """
    from collections import Counter

    for cat, picks in ranked_by_cat.items():
        if len(picks) < 3:
            continue

        # Iterative swap with a hard guard against infinite loops.
        # Even when the full ranked top 5 has <3 distinct sources we
        # still try, because reducing top 3 from "3 dups of one source"
        # to "2 from one + 1 from another" is real progress. The inner
        # loop bails cleanly when no swap candidate exists.
        for _ in range(4):
            top3 = picks[:3]
            top3_srcs = [p["source"].name for p in top3]
            counter = Counter(top3_srcs)
            dups = [name for name, c in counter.items() if c > 1]
            if not dups:
                break

            # Find the WORST-rank duplicate slot in top 3 (highest rank
            # value among duplicates).
            dup_idx = max(
                (i for i in range(3) if picks[i]["source"].name in dups),
                key=lambda i: picks[i]["rank"],
            )

            # Find a spare (rank 4-5) whose source is NOT in top 3.
            spare_idx = next(
                (j for j in range(3, len(picks))
                 if picks[j]["source"].name not in top3_srcs),
                None,
            )
            if spare_idx is None:
                log.warning("  [%s] source-diversity: dup=%s but no spare "
                            "with a different source — top 3 stays "
                            "degraded (only %d distinct sources in "
                            "curator's top %d)",
                            cat, dups,
                            len({p["source"].name for p in picks}),
                            len(picks))
                break

            old = picks[dup_idx]
            new = picks[spare_idx]
            log.info(
                "  [%s] source-diversity swap: rank%d/%s ↔ rank%d/%s",
                cat, old["rank"], old["source"].name,
                new["rank"], new["source"].name,
            )
            # Swap rank values so list stays in rank order
            old_rank, new_rank = old["rank"], new["rank"]
            picks[dup_idx], picks[spare_idx] = new, old
            picks[dup_idx]["rank"] = old_rank
            picks[spare_idx]["rank"] = new_rank

    return ranked_by_cat
