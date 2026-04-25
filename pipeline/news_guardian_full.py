"""The Guardian World RSS — LIGHT flow: vet titles+descriptions FIRST, fetch full HTML only for the 2 picked.

Why different from AJ/PBS: Guardian RSS descriptions can be short, but we don't need full
content to judge fit — we just use title + <description> as input to the curator.
After picking 2, we fetch full HTML for those 2 to feed the rewriter.

Run:  python -m pipeline.news_guardian_full
View: http://localhost:18100/news-guardian-full.html
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .cleaner import extract_article_from_html
from .news_rss_core import (
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent

    MIN_PICK_BODY_WORDS,
    SAFETY_DIMS,
    SAFETY_SHORT,
    apply_vet_thresholds,
    build_rewriter_prompt,
    build_vet_prompt,
    deepseek_call,
    fetch_html,
    fetch_rss_entries,
    is_generic_social_image,
    rewriter_input,
    vet_curator_input,
    verdict_class,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("guardian")

GUARDIAN_RSS = "https://www.theguardian.com/world/rss"
SOURCE_LABEL = "The Guardian — World"
OUTPUT_SLUG = "news-guardian-full"
PICK_COUNT = 2
TARGET_WORDS = 400
MAX_RSS = 25

HTML_TAG_RE = re.compile(r"<[^>]+>")
VIDEO_PATH_RE = re.compile(r"/video/", re.I)


def strip_html_tags(s: str) -> str:
    return HTML_TAG_RE.sub("", s or "").strip()


def main() -> None:
    log.info("Step 1: fetch RSS %s", GUARDIAN_RSS)
    rss_entries = fetch_rss_entries(GUARDIAN_RSS, max_entries=MAX_RSS)
    log.info("  %d entries", len(rss_entries))

    # Light pre-filter: drop /video/ URLs, strip HTML from descriptions
    briefs = []
    skipped = []
    for e in rss_entries:
        url = e.get("link") or ""
        if VIDEO_PATH_RE.search(url):
            skipped.append({**e, "skip_reason": "video URL"})
            continue
        desc_clean = strip_html_tags(e.get("summary") or "")
        briefs.append({
            **e,
            # Use cleaned description as the "highlights" equivalent for the curator
            "highlights": [desc_clean[:400]] if desc_clean else [],
            "summary": desc_clean,
        })

    log.info("Step 2: batched vet+cluster+pick (1 call, %d briefs in) — title+description ONLY",
             len(briefs))
    if len(briefs) < PICK_COUNT:
        log.error("Only %d briefs — need ≥ %d", len(briefs), PICK_COUNT)
        return

    batch_vet = deepseek_call(build_vet_prompt(PICK_COUNT),
                              vet_curator_input(briefs, PICK_COUNT),
                              max_tokens=4500, temperature=0.2)

    # Re-apply authoritative thresholds
    for v in batch_vet.get("vet") or []:
        safety = v.get("safety") or {}
        dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
        safety["total"] = sum(dims)
        safety["verdict"] = apply_vet_thresholds(safety)
    # Filter picks that became REJECT
    vet_by_id = {v["id"]: v for v in batch_vet.get("vet") or []}
    filtered_picks = []
    for p in batch_vet.get("picks") or []:
        pid = p.get("id")
        v = vet_by_id.get(pid)
        if v and v.get("safety", {}).get("verdict") == "REJECT":
            log.warning("  dropping pick id=%s — REJECT on strict thresholds", pid)
            continue
        filtered_picks.append(p)
    batch_vet["picks"] = filtered_picks

    picks = filtered_picks
    clusters = batch_vet.get("clusters") or []
    log.info("  clusters: %d (hot: %d)", len(clusters),
             sum(1 for c in clusters if c.get("is_hot")))
    log.info("  picks: %s", [p.get("id") for p in picks])
    for p in picks:
        pid = p.get("id")
        if pid is not None and pid < len(briefs):
            log.info("    ★ [%s] %s", pid, briefs[pid].get("title", ""))

    if not picks:
        log.error("No viable picks — aborting")
        return

    # Step 3: NOW fetch full HTML only for picked articles.
    # If a pick's body is too thin OR its og:image is a generic social default,
    # swap in an alternate from the vet's alternate list.
    log.info("Step 3: fetch full HTML for picks (with alternate fallback)")
    enriched: dict[int, dict] = {}
    alternates_used: list[tuple[int, int, str]] = []   # (original_pid, alt_pid, reason)
    alt_queue = [a.get("id") for a in (batch_vet.get("alternates") or [])
                 if isinstance(a.get("id"), int) and a.get("id") < len(briefs)]

    def fetch_and_check(pid: int) -> dict | None:
        """Fetch + extract; return enriched art dict or None if unusable."""
        if pid is None or pid >= len(briefs):
            return None
        art = dict(briefs[pid])
        url = art.get("link") or ""
        log.info("  fetching [%d] %s", pid, url)
        html_text = fetch_html(url)
        if not html_text:
            log.warning("    HTML fetch failed")
            return None
        extracted = extract_article_from_html(url, html_text)
        art["body"] = extracted.get("cleaned_body") or ""
        art["paragraphs"] = extracted.get("paragraphs") or []
        art["og_image"] = extracted.get("og_image")
        art["word_count"] = len(art["body"].split()) if art["body"] else 0
        bad_image = is_generic_social_image(art["og_image"])
        thin_body = art["word_count"] < MIN_PICK_BODY_WORDS
        reason = None
        if bad_image:
            reason = f"generic social image ({art['og_image']})"
        elif thin_body:
            reason = f"thin body ({art['word_count']}w < {MIN_PICK_BODY_WORDS}w)"
        log.info("    %d words, og:image=%s%s", art["word_count"],
                 "✓" if art["og_image"] and not bad_image else "—",
                 f" · REJECT: {reason}" if reason else "")
        if reason:
            art["_reject_after_fetch"] = reason
            return None
        return art

    for p in picks:
        pid = p.get("id")
        art = fetch_and_check(pid)
        if art:
            enriched[pid] = art
            continue
        # Try alternates
        while alt_queue:
            alt_pid = alt_queue.pop(0)
            if alt_pid in enriched or alt_pid in [x.get("id") for x in picks]:
                continue  # already used
            log.info("  swapping to alternate [%d]", alt_pid)
            art = fetch_and_check(alt_pid)
            if art:
                enriched[alt_pid] = art
                alternates_used.append((pid, alt_pid, "pick failed content check"))
                break
        else:
            log.warning("  no more alternates for failed pick %d", pid)

    if len(enriched) < PICK_COUNT:
        log.warning("Only %d of %d picks had fetchable content", len(enriched), len(picks))
    if not enriched:
        log.error("No fetchable content — aborting rewrite")
        return

    log.info("Step 4: batched rewrite (1 call, %d in)", len(enriched))
    picks_with_arts = list(enriched.items())
    rewrite_result = deepseek_call(build_rewriter_prompt(len(picks_with_arts), TARGET_WORDS),
                                   rewriter_input(picks_with_arts, TARGET_WORDS),
                                   max_tokens=3000, temperature=0.5)
    kids_articles_by_id: dict[int, dict] = {}
    for a in rewrite_result.get("articles") or []:
        sid = a.get("source_id")
        if sid is not None:
            wc = len((a.get("body") or "").split())
            log.info("  ✓ id=%d: %s (%d words)", sid, a.get("headline", "")[:60], wc)
            kids_articles_by_id[sid] = a

    # --------------------------- HTML render ---------------------------
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(str(s) if s is not None else "")

    vet_list = batch_vet.get("vet") or []
    picked_ids = {p.get("id") for p in picks}
    cluster_by_id = {c.get("id"): c for c in clusters}
    article_to_cluster = {v.get("id"): v.get("cluster_id") for v in vet_list}

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(SOURCE_LABEL)} → 12yo — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:24px;margin:8px 0;}}
  h2{{font-size:17px;margin:28px 0 10px;border-bottom:2px solid #eee;padding-bottom:6px;color:#444;}}
  .meta{{color:#777;font-size:13px;margin-bottom:18px;}}
  .stats{{background:#f6f6f6;border-radius:6px;padding:10px 14px;margin:12px 0;font-size:13px;color:#555;}}
  .stats b{{color:#222;}}
  .note{{background:#fff6ed;border-left:4px solid #f0903e;padding:10px 14px;margin:12px 0;border-radius:4px;font-size:13px;}}
  table{{width:100%;border-collapse:collapse;margin-bottom:18px;font-size:12.5px;}}
  th,td{{padding:5px 7px;text-align:left;border-bottom:1px solid #eee;vertical-align:top;}}
  th{{background:#f0f0f0;font-weight:600;font-size:11.5px;}}
  td.n{{text-align:right;font-variant-numeric:tabular-nums;width:28px;}}
  td.tot{{text-align:right;font-weight:700;width:36px;}}
  .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10.5px;font-weight:700;white-space:nowrap;}}
  .v-safe{{background:#d8f3e0;color:#266;}}
  .v-caution{{background:#fff2c4;color:#955;}}
  .v-reject{{background:#f9d6d6;color:#933;}}
  .v-engaging{{background:#d9e8ff;color:#245;}}
  .v-meh{{background:#eee;color:#666;}}
  .v-boring{{background:#f9d6d6;color:#933;}}
  .hot{{background:#ffe5cc;color:#c35;padding:2px 6px;border-radius:4px;font-size:10.5px;font-weight:700;margin-left:4px;}}
  .pick{{background:#fffbea;}}
  .pick td:first-child::before{{content:"★ "; color:#d8a300;}}
  .cluster-box{{background:#fff6ed;border-left:4px solid #f0903e;padding:10px 14px;margin:8px 0;border-radius:4px;}}
  .reason{{background:#eef6ff;border-left:3px solid #4a90e2;padding:8px 12px;margin:8px 0;font-size:13px;}}
  .kids-article{{background:#fff9ef;border:2px solid #ffc83d;border-radius:10px;padding:22px 26px;margin:24px 0;box-shadow:0 2px 6px rgba(0,0,0,.06);}}
  .kids-article .kheadline{{font-size:24px;font-weight:800;color:#1b1230;margin:0 0 6px;font-family:Georgia,serif;line-height:1.2;}}
  .kids-article .ksrc{{font-size:12px;color:#8a6d00;margin-bottom:10px;}}
  .kids-article img{{max-width:100%;border-radius:6px;margin:10px 0;}}
  .kids-article .kbody{{font-size:16px;line-height:1.65;color:#221a10;}}
  .kids-article .kbody p{{margin:0 0 14px;}}
  .kids-article .kwim{{background:#fff3c4;border-left:4px solid #e0a800;padding:10px 14px;margin-top:14px;border-radius:4px;font-style:italic;}}
  details{{margin:8px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:13px;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;background:#fafafa;padding:10px;border-radius:6px;max-height:400px;overflow-y:auto;margin-top:6px;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
  .flags{{font-size:11px;color:#933;margin-top:3px;}}
  .threshold{{background:#ffede6;border-left:4px solid #d04030;padding:8px 12px;margin:12px 0;border-radius:4px;font-size:13px;}}
</style>
</head>
<body>
<h1>{esc(SOURCE_LABEL)} → 12-year-old kids news — {today}</h1>
<div class="meta">
  RSS: <a href="{esc(GUARDIAN_RSS)}" target="_blank">{esc(GUARDIAN_RSS)}</a>
</div>

<div class="note">
  <b>LIGHT FLOW</b> (different from AJ/PBS): vetter judges on RSS title + &lt;description&gt; only.
  Full HTML is fetched ONLY for the 2 picks (instead of all 25). Saves ~20 HTTP fetches per run.
</div>

<div class="threshold">
  <b>Vet thresholds (locked 2026-04-23):</b>
  <span class="pill v-reject">REJECT</span> if any dim ≥ 4 or total > 6 ·
  <span class="pill v-caution">CAUTION</span> if total 5-6 (all dims ≤ 3) ·
  <span class="pill v-safe">SAFE</span> if total 0-4
</div>

<div class="stats">
  <b>RSS entries:</b> {len(rss_entries)} ·
  <b>Pre-filter skipped (video URLs):</b> {len(skipped)} ·
  <b>Briefs sent to vetter:</b> {len(briefs)} ·
  <b>Clusters:</b> {len(clusters)} ·
  <b>Picks after REJECT filter:</b> {len(picks)} ·
  <b>Successful content fetches:</b> {len(enriched)} ·
  <b>Alternates used:</b> {len(alternates_used)} ·
  <b>Kids articles:</b> {len(kids_articles_by_id)}
</div>

{"".join(f'<div class="note"><b>Alt swap:</b> pick id {orig} failed — used alternate id {alt} instead</div>' for orig, alt, _ in alternates_used)}

<h2>Topic clusters</h2>"""]

    hot_clusters = [c for c in clusters if c.get("is_hot")]
    other_clusters = [c for c in clusters if not c.get("is_hot")]
    for c in hot_clusters + other_clusters:
        badge = '<span class="hot">🔥 HOT</span>' if c.get("is_hot") else ""
        member_titles = []
        for mid in c.get("members", []):
            if mid < len(briefs):
                member_titles.append(f"[{mid}] {briefs[mid].get('title', '')[:70]}")
        members_list = "<br>".join(esc(t) for t in member_titles[:10])
        parts.append(f"""
<div class="cluster-box">
  <b>{esc(c.get('theme', '?'))}</b> {badge} — <b>{c.get('size', 0)}</b> articles
  <div style="font-size:12px;color:#555;margin-top:6px;">{members_list}</div>
</div>""")

    # SAFETY TABLE
    parts.append("""
<h2>Vetter Safety Report · 安全审核报告</h2>
<table>
<thead><tr>
  <th>#</th><th>Title</th>""")
    for short in SAFETY_SHORT:
        parts.append(f"<th>{short}</th>")
    parts.append("""<th>Total</th><th>Verdict</th><th>Cluster</th>
</tr></thead><tbody>""")

    for v in vet_list:
        aid = v.get("id")
        if aid >= len(briefs):
            continue
        art = briefs[aid]
        safety = v.get("safety") or {}
        cluster_id = v.get("cluster_id") or ""
        cluster_size = cluster_by_id.get(cluster_id, {}).get("size", 0)
        cluster_badge = f"🔥{cluster_size}" if cluster_size >= 3 else (str(cluster_size) if cluster_size > 1 else "")
        is_pick = aid in picked_ids
        row_cls = ' class="pick"' if is_pick else ""
        title = art.get("title") or ""
        flags = safety.get("flags") or v.get("flags") or []
        flags_html = f'<div class="flags">flags: {esc(", ".join(flags))}</div>' if flags else ""
        parts.append(f"""<tr{row_cls}>
  <td class="n">{aid}</td>
  <td><a href="{esc(art.get('link', ''))}" target="_blank">{esc(title[:70])}</a>{flags_html}</td>""")
        for dim in SAFETY_DIMS:
            parts.append(f'<td class="n">{safety.get(dim, "?")}</td>')
        parts.append(f"""<td class="tot">{safety.get("total", "?")}</td>
  <td><span class="pill {verdict_class(safety.get('verdict', ''), 'safety')}">{esc(safety.get('verdict', ''))}</span></td>
  <td>{esc(cluster_id)} {cluster_badge}</td>
</tr>""")
    parts.append("""</tbody></table>""")

    # INTEREST TABLE
    parts.append("""
<h2>Interest Report · 兴趣评分</h2>
<table>
<thead><tr>
  <th>#</th><th>Title</th><th>Import.</th><th>Fun</th><th>KidAppeal</th><th>Peak</th><th>Verdict</th>
</tr></thead><tbody>""")
    for v in vet_list:
        aid = v.get("id")
        if aid >= len(briefs):
            continue
        art = briefs[aid]
        interest = v.get("interest") or {}
        is_pick = aid in picked_ids
        row_cls = ' class="pick"' if is_pick else ""
        title = art.get("title") or ""
        parts.append(f"""<tr{row_cls}>
  <td class="n">{aid}</td>
  <td>{esc(title[:90])}</td>
  <td class="n">{interest.get("importance", "?")}</td>
  <td class="n">{interest.get("fun_factor", "?")}</td>
  <td class="n">{interest.get("kid_appeal", "?")}</td>
  <td class="tot">{interest.get("peak", "?")}</td>
  <td><span class="pill {verdict_class(interest.get('verdict', ''), 'interest')}">{esc(interest.get('verdict', ''))}</span></td>
</tr>""")
    parts.append("""</tbody></table>""")

    # PICKS
    parts.append("""
<h2>Final picks</h2>""")
    for p in picks:
        pid = p.get("id")
        if pid is None or pid >= len(briefs):
            continue
        art = briefs[pid]
        cluster_id = article_to_cluster.get(pid, "")
        cluster_info = cluster_by_id.get(cluster_id, {})
        hot_badge = f" [🔥 cluster: {cluster_info.get('theme', '')} — {cluster_info.get('size', 0)} articles]" if cluster_info.get("is_hot") else ""
        content_note = ""
        if pid in enriched:
            wc = enriched[pid].get("word_count", 0)
            content_note = f" · Full content: <b>{wc} words</b>"
        else:
            content_note = ' · <span style="color:#c33;">⚠ full content fetch failed</span>'
        parts.append(f"""
<div class="reason">
  <b>Pick id {pid}:</b> <a href="{esc(art.get('link', ''))}" target="_blank">{esc(art.get('title', ''))}</a>{esc(hot_badge)}{content_note}<br>
  <b>Reason:</b> {esc(p.get('reason', ''))}
</div>""")

    # KIDS ARTICLES
    parts.append(f"""
<h2>Generated kids articles ({TARGET_WORDS}-word, 12-year-old level)</h2>""")
    for pid, ka in kids_articles_by_id.items():
        src = enriched.get(pid) or briefs[pid] if pid < len(briefs) else {}
        src_url = src.get("link") or ""
        src_host = urlparse(src_url).netloc.replace("www.", "")
        img = src.get("og_image") or ""
        headline = ka.get("headline") or "(no headline)"
        body = ka.get("body") or ""
        wim = ka.get("why_it_matters") or ""
        body_paragraphs = "\n".join(f"    <p>{esc(p)}</p>" for p in body.split("\n\n") if p.strip())
        wc = len(body.split()) if body else 0
        parts.append(f"""
<div class="kids-article">
  <div class="ksrc">📰 Source: <a href="{esc(src_url)}" target="_blank">{esc(src.get('title', ''))}</a> · {esc(src_host)} · <span style="color:#888;">generated {wc} words</span></div>
  {f'<img src="{esc(img)}" alt=""/>' if img else ''}
  <div class="kheadline">{esc(headline)}</div>
  <div class="kbody">
{body_paragraphs}
  </div>
  <div class="kwim"><b>Why it matters:</b> {esc(wim)}</div>
  <details><summary>Full original article (fetched body)</summary><pre>{esc(src.get('body', ''))}</pre></details>
</div>""")
    parts.append("""
</body>
</html>""")

    # Write output
    out_dir = (_REPO_ROOT / "website/test_output") / today
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{OUTPUT_SLUG}.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rss": GUARDIAN_RSS,
        "flow": "light",
        "counts": {"rss": len(rss_entries), "briefs_to_vet": len(briefs),
                   "skipped": len(skipped), "picks": len(picks),
                   "fetched": len(enriched), "kids_articles": len(kids_articles_by_id)},
        "briefs": [{"id": i, "title": b["title"], "link": b["link"]}
                   for i, b in enumerate(briefs)],
        "skipped": skipped,
        "batch_vet": batch_vet,
        "enriched_word_counts": {str(k): v.get("word_count", 0) for k, v in enriched.items()},
        "kids_articles": kids_articles_by_id,
    }, indent=2, ensure_ascii=False))

    html_path = (_REPO_ROOT / f"website/{OUTPUT_SLUG}.html")
    html_path.write_text("".join(parts))
    log.info("HTML: %s", html_path)
    log.info("View: http://localhost:18100/%s.html", OUTPUT_SLUG)


if __name__ == "__main__":
    main()
