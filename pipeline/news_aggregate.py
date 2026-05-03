"""News aggregator — runs Phase A (per source), B (cross-source dedup), C (tri-variant rewrite).

Workflow:
  Phase A (serial): for each enabled source, mine RSS → vet → pick winner.
    Tries choice_1 → choice_2 → alternates until content-quality check passes.
    If a source yields no winner after all attempts, pulls from random backup source.
  Phase B (cross-source dedup): DeepSeek compares the 3 winners' titles+excerpts.
    If dup found, drop the weaker one (lower-priority source) → try its choice_2 →
    if still dup, pull from random backup.
  Phase C (batch rewrite): 1 DeepSeek call generates tri-variant output for each
    of the 3 stories: easy_en (170-210w), middle_en (320-350w), zh (300 汉字 summary).

Run:  python -m pipeline.news_aggregate
View: http://localhost:18100/news-today.html
"""
from __future__ import annotations

import html
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .news_rss_core import (
    MIN_PICK_BODY_WORDS,
    SAFETY_DIMS,
    SAFETY_SHORT,
    _fetch_and_enrich,
    apply_vet_thresholds,
    check_duplicates,
    run_source_phase_a,
    tri_variant_rewrite,
    verdict_class,
    verify_article_content,
)
from .news_sources import NewsSource, backup_sources, enabled_sources
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aggregate")


def title_excerpt(art: dict) -> str:
    """First 200 chars of body for dup-check + render."""
    body = art.get("body") or ""
    if not body:
        return (art.get("summary") or "")[:300]
    return body[:400]


def try_next_pick_for_source(phase_a_result: dict, already_used_ids: set[int]) -> dict | None:
    """Try the next non-used pick slot for a source (choice_2 or alternates)."""
    source = phase_a_result["source"]
    briefs = phase_a_result["kept_briefs"]
    # Build full attempt order again from batch_vet
    bv = phase_a_result["batch_vet"]
    vet_by_id = {v["id"]: v for v in bv.get("vet") or []}
    order: list[tuple[str, int]] = []
    for i, p in enumerate((bv.get("picks") or [])[:2]):
        order.append((f"choice_{i+1}", p.get("id")))
    for i, a in enumerate(bv.get("alternates") or []):
        order.append((f"alternate_{i}", a.get("id")))

    used_slot = phase_a_result.get("winner_slot")
    past_slot_used = False
    for slot, cid in order:
        if slot == used_slot:
            past_slot_used = True
            continue
        if not past_slot_used:
            continue
        if cid is None or cid >= len(briefs) or cid in already_used_ids:
            continue
        # Skip REJECTs
        v = vet_by_id.get(cid, {})
        if v.get("safety", {}).get("verdict") == "REJECT":
            continue
        art = dict(briefs[cid])
        if source.flow == "light" or not art.get("body"):
            log.info("[%s]  backfill fetching [%s id=%d]", source.name, slot, cid)
            art = _fetch_and_enrich(art)
        ok, reason = verify_article_content(art)
        if ok:
            art["_vet_info"] = v
            return {
                "source": source,
                "winner": art,
                "winner_slot": slot,
                "batch_vet": bv,
                "kept_briefs": briefs,
                "attempts": phase_a_result["attempts"] + [{"slot": slot, "id": cid, "ok": True, "reason": None}],
            }
    return None


def run_source(source: NewsSource) -> dict | None:
    """Single-pass source run. No backup-swap fallback (Q1=b — backup
    pool folded into primaries via cadence-aware scheduling)."""
    return run_source_phase_a(source)


def main() -> None:
    enabled = enabled_sources()
    backups = backup_sources()
    log.info("Enabled sources: %s", [s.name for s in enabled])
    log.info("Backup sources: %s", [s.name for s in backups])

    # ---- PHASE A ----
    log.info("\n=== PHASE A — per-source mining ===")
    winners: list[dict] = []
    used_backup_names: set[str] = set()
    for source in enabled:
        result = run_source(source)
        if result:
            if result.get("used_backup"):
                used_backup_names.add(result["source"].name)
            winners.append(result)

    if len(winners) < 2:
        log.error("Only %d winners — aborting", len(winners))
        return

    # ---- PHASE B — cross-source dup check ----
    log.info("\n=== PHASE B — cross-source dedup ===")
    dup_rounds = 0
    while dup_rounds < 2:
        dup_check_briefs = [
            {
                "id": i,
                "title": w["winner"].get("title"),
                "source_name": w["source"].name,
                "source_priority": w["source"].priority,
                "excerpt": title_excerpt(w["winner"]),
            }
            for i, w in enumerate(winners)
        ]
        dup_result = check_duplicates(dup_check_briefs)
        log.info("Dup check: verdict=%s pairs=%d",
                 dup_result.get("verdict"),
                 len(dup_result.get("duplicate_pairs") or []))

        if dup_result.get("verdict") != "DUP_FOUND":
            break

        # Drop the weaker of the pair (highest priority number = lowest priority = weakest)
        drop_id = dup_result.get("drop_suggestion")
        if drop_id is None and dup_result.get("duplicate_pairs"):
            pair = dup_result["duplicate_pairs"][0]["ids"]
            drop_id = max(pair, key=lambda i: winners[i]["source"].priority)
        if drop_id is None or drop_id >= len(winners):
            log.warning("Dup but no valid drop — stopping dedup")
            break

        dropped = winners[drop_id]
        log.info("Dropping dup [%d] %s (source %s)", drop_id,
                 dropped["winner"].get("title", "")[:60], dropped["source"].name)

        # Try same-source choice_2 first
        already_used_ids = {drop_id}
        next_pick = try_next_pick_for_source(dropped, already_used_ids)
        if next_pick:
            winners[drop_id] = next_pick
            log.info("  → filled with same-source %s", next_pick["winner_slot"])
        else:
            # Fall back to random backup
            available_backups = [b for b in backups if b.name not in used_backup_names]
            if available_backups:
                random.shuffle(available_backups)
                for backup in available_backups:
                    res = run_source_phase_a(backup)
                    if res:
                        res["primary_source_name"] = dropped["source"].name
                        res["used_backup"] = True
                        used_backup_names.add(backup.name)
                        winners[drop_id] = res
                        log.info("  → filled with backup %s", backup.name)
                        break
                else:
                    log.warning("  no backup produced a winner; dropping this slot")
                    del winners[drop_id]
                    break
            else:
                log.warning("  no backups left; dropping this slot")
                del winners[drop_id]
                break

        dup_rounds += 1

    if not winners:
        log.error("Aggregation left zero winners — aborting")
        return

    # ---- PHASE C — batched tri-variant rewrite ----
    log.info("\n=== PHASE C — batched tri-variant rewrite ===")
    articles_for_rewrite = [(i, w["winner"]) for i, w in enumerate(winners)]
    rewrite_result = tri_variant_rewrite(articles_for_rewrite)
    articles_out = {a.get("source_id"): a for a in rewrite_result.get("articles") or []}
    for sid, a in articles_out.items():
        ec = len((a.get("easy_en", {}).get("body") or "").split())
        mc = len((a.get("middle_en", {}).get("body") or "").split())
        zc = len(a.get("zh", {}).get("summary") or "")
        log.info("  ✓ id=%s: easy_en=%dw middle_en=%dw zh=%d字", sid, ec, mc, zc)

    # ---- Render + write ----
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(str(s) if s is not None else "")

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>News Today — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:26px;margin:8px 0;}}
  h2{{font-size:18px;margin:28px 0 10px;border-bottom:2px solid #eee;padding-bottom:6px;color:#444;}}
  h3{{font-size:15px;margin:16px 0 8px;color:#555;}}
  .meta{{color:#777;font-size:13px;margin-bottom:18px;}}
  .stats{{background:#f6f6f6;border-radius:6px;padding:10px 14px;margin:12px 0;font-size:13px;color:#555;}}
  .story{{background:#fff9ef;border:2px solid #ffc83d;border-radius:10px;padding:22px 26px;margin:28px 0;box-shadow:0 2px 6px rgba(0,0,0,.06);}}
  .story .hero{{display:flex;gap:16px;align-items:flex-start;margin-bottom:12px;}}
  .story .hero img{{flex:0 0 260px;width:260px;height:180px;object-fit:cover;border-radius:6px;border:1px solid #eee;}}
  .story .src{{font-size:12px;color:#8a6d00;margin-bottom:6px;}}
  .story .src .backup{{background:#ffe5cc;color:#c35;padding:1px 6px;border-radius:3px;font-weight:700;margin-left:6px;}}
  .story .src a{{color:#8a6d00;}}
  .variant{{background:#fff;border-left:4px solid #ffc83d;padding:14px 18px;margin:14px 0;border-radius:4px;}}
  .variant h3{{color:#1b1230;margin-top:0;font-family:Georgia,serif;font-weight:800;font-size:20px;}}
  .variant .label{{display:inline-block;background:#ffc83d;color:#1b1230;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px;}}
  .variant .label.middle{{background:#95c6a6;}}
  .variant .label.zh{{background:#e98e94;color:#fff;}}
  .variant p{{margin:0 0 10px;font-size:15px;line-height:1.6;}}
  .variant .wim{{background:#fff3c4;border-left:4px solid #e0a800;padding:8px 12px;margin-top:10px;border-radius:4px;font-style:italic;font-size:14px;}}
  .wc{{color:#888;font-size:11px;margin-left:8px;}}
  details{{margin:12px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:12px;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;background:#fafafa;padding:10px;border-radius:6px;max-height:350px;overflow-y:auto;margin-top:6px;}}
  .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10.5px;font-weight:700;margin-left:4px;}}
  .v-safe{{background:#d8f3e0;color:#266;}}
  .v-caution{{background:#fff2c4;color:#955;}}
  .v-reject{{background:#f9d6d6;color:#933;}}
  .v-engaging{{background:#d9e8ff;color:#245;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<h1>News Today — {today}</h1>
<div class="meta">
  Aggregated from enabled sources; backups used when needed. Tri-variant output per story.
</div>

<div class="stats">
  <b>Enabled sources:</b> {", ".join(s.name for s in enabled)}<br>
  <b>Backup pool:</b> {", ".join(s.name for s in backups)}<br>
  <b>Final stories:</b> {len(winners)} (of {len(enabled)} slots)<br>
  <b>Backups used:</b> {", ".join(used_backup_names) if used_backup_names else "none"}
</div>
"""]

    for i, w in enumerate(winners):
        src = w["source"]
        src_art = w["winner"]
        src_url = src_art.get("link") or ""
        src_host = urlparse(src_url).netloc.replace("www.", "")
        src_image = src_art.get("og_image") or ""
        safety_info = (src_art.get("_vet_info") or {}).get("safety") or {}
        interest_info = (src_art.get("_vet_info") or {}).get("interest") or {}
        vet_pills = f'<span class="pill {verdict_class(safety_info.get("verdict",""), "safety")}">{esc(safety_info.get("verdict",""))} {safety_info.get("total","?")}/40</span>'
        vet_pills += f' <span class="pill {verdict_class(interest_info.get("verdict",""), "interest")}">{esc(interest_info.get("verdict",""))} peak={interest_info.get("peak","?")}</span>'
        backup_badge = f'<span class="backup">BACKUP for {esc(w.get("primary_source_name",""))}</span>' if w.get("used_backup") else ""
        variants = articles_out.get(i) or {}
        rewrite_attempts = ""
        for att in w.get("attempts") or []:
            marker = "✓" if att.get("ok") else "✗"
            rewrite_attempts += f"\n{marker} {att['slot']} id={att['id']} — {att.get('title','')[:60]} ({att.get('reason') or 'ok'})"

        parts.append(f"""
<div class="story">
  <div class="src">
    📰 <b>Source:</b> {esc(src.name)}{backup_badge} · <a href="{esc(src_url)}" target="_blank">{esc(src_art.get('title',''))}</a> · {esc(src_host)} · picked slot: {esc(w.get('winner_slot',''))} · {vet_pills}
  </div>
  <div class="hero">
    {f'<img src="{esc(src_image)}" alt=""/>' if src_image else ''}
    <div>
      <div style="font-size:14px;color:#555;">Source body: <b>{src_art.get('word_count',0)} words</b></div>
      <details><summary>Phase A attempts for this source</summary><pre>{esc(rewrite_attempts)}</pre></details>
    </div>
  </div>
""")

        easy = variants.get("easy_en") or {}
        if easy:
            body_p = "\n".join(f"    <p>{esc(p)}</p>" for p in (easy.get("body") or "").split("\n\n") if p.strip())
            parts.append(f"""
  <div class="variant">
    <span class="label">EASY 🌱 · Sprout · ages 8-9</span><span class="wc">{len((easy.get('body','') or '').split())} words</span>
    <h3>{esc(easy.get('headline',''))}</h3>
{body_p}
    <div class="wim"><b>Why it matters:</b> {esc(easy.get('why_it_matters',''))}</div>
  </div>""")

        middle = variants.get("middle_en") or {}
        if middle:
            body_p = "\n".join(f"    <p>{esc(p)}</p>" for p in (middle.get("body") or "").split("\n\n") if p.strip())
            parts.append(f"""
  <div class="variant">
    <span class="label middle">MIDDLE 🌳 · Tree · age 12</span><span class="wc">{len((middle.get('body','') or '').split())} words</span>
    <h3>{esc(middle.get('headline',''))}</h3>
{body_p}
    <div class="wim"><b>Why it matters:</b> {esc(middle.get('why_it_matters',''))}</div>
  </div>""")

        zh = variants.get("zh") or {}
        if zh:
            parts.append(f"""
  <div class="variant">
    <span class="label zh">中文 · 简短摘要</span><span class="wc">{len(zh.get('summary','') or '')} 汉字</span>
    <h3>{esc(zh.get('headline',''))}</h3>
    <p>{esc(zh.get('summary',''))}</p>
  </div>""")

        parts.append("""
  <details><summary>Full original source body</summary><pre>""" + esc(src_art.get("body", "")) + """</pre></details>
</div>""")

    parts.append("""
</body>
</html>""")

    today_dir = (_REPO_ROOT / "website/test_output") / today
    today_dir.mkdir(parents=True, exist_ok=True)
    (today_dir / "news_today.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "enabled_sources": [s.name for s in enabled],
        "backup_sources": [s.name for s in backups],
        "winners": [
            {
                "source": w["source"].name,
                "used_backup": w.get("used_backup", False),
                "primary_source_name": w.get("primary_source_name"),
                "winner_slot": w.get("winner_slot"),
                "title": w["winner"].get("title"),
                "url": w["winner"].get("link"),
                "word_count": w["winner"].get("word_count"),
                "og_image": w["winner"].get("og_image"),
                "safety": (w["winner"].get("_vet_info") or {}).get("safety"),
                "interest": (w["winner"].get("_vet_info") or {}).get("interest"),
                "attempts": w.get("attempts"),
            } for w in winners
        ],
        "variants": articles_out,
    }, indent=2, ensure_ascii=False))

    html_path = (_REPO_ROOT / "website/news-today.html")
    html_path.write_text("".join(parts))
    log.info("HTML: %s", html_path)
    log.info("View: http://localhost:18100/news-today.html")


if __name__ == "__main__":
    main()
