"""Fetch news from Al Jazeera RSS — same flow as PBS (feedparser → HTML fetch → og:image + cleaned body).

Run:  python -m pipeline.news_aj_rss
View: http://localhost:18100/news-aj-rss.html
"""
from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

from .cleaner import extract_article_from_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aj-rss")

AJ_RSS = "https://www.aljazeera.com/xml/rss/all.xml"
MAX_ENTRIES = 15
HTML_FETCH_TIMEOUT = 15
HTML_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 news-v2-bot (+https://news.6ray.com)",
}


def fetch_rss(url: str) -> list[dict]:
    feed = feedparser.parse(url)
    out = []
    for entry in feed.entries[:MAX_ENTRIES]:
        out.append({
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "summary": getattr(entry, "summary", ""),
            "author": getattr(entry, "author", ""),
        })
    return out


def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
                         allow_redirects=True)
        if r.status_code >= 400:
            log.info("HTML fetch %s -> %d", url, r.status_code)
            return None
        return r.text
    except requests.RequestException as e:
        log.info("HTML fetch failed %s: %s", url, e)
        return None


def process_entry(entry: dict) -> dict:
    url = entry["link"]
    log.info("fetching %s", url)
    html_text = fetch_html(url)
    if not html_text:
        return {**entry, "og_image": None, "body": "", "paragraphs": [],
                "word_count": 0, "fetch_error": True}

    extracted = extract_article_from_html(url, html_text)
    body = extracted.get("cleaned_body") or ""
    paragraphs = extracted.get("paragraphs") or []
    og_image = extracted.get("og_image")
    return {
        **entry,
        "og_image": og_image,
        "paragraphs": paragraphs,
        "body": body,
        "word_count": len(body.split()) if body else 0,
        "fetch_error": False,
    }


def render_html(entries: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(s or "")

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Al Jazeera RSS — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:960px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:22px;margin:8px 0;}}
  h2{{font-size:17px;margin:32px 0 12px;border-bottom:1px solid #eee;padding-bottom:6px;color:#444;}}
  .meta{{color:#777;font-size:13px;margin-bottom:24px;}}
  table{{width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px;}}
  th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #eee;vertical-align:top;}}
  th{{background:#f6f6f6;font-weight:600;color:#444;}}
  .host{{font-size:11px;color:#c35;background:#fbe7ec;padding:2px 6px;border-radius:3px;display:inline-block;}}
  .words{{color:#888;font-size:12px;}}
  .card{{background:#fff;border:1px solid #e8e8e8;border-radius:8px;padding:16px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,.04);}}
  .card .hdr{{display:flex;gap:14px;margin-bottom:10px;}}
  .card .thumb{{flex:0 0 180px;}}
  .card .thumb img{{width:180px;height:120px;object-fit:cover;border-radius:6px;border:1px solid #eee;}}
  .card .body{{flex:1;min-width:0;}}
  .card .title{{font-size:16px;font-weight:600;margin:0 0 6px;line-height:1.3;}}
  .card .date{{font-size:12px;color:#888;}}
  .fetch-err{{background:#fff2f2;border-left:3px solid #c33;padding:8px 12px;color:#733;}}
  details{{margin:8px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:13px;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:#fafafa;padding:12px;border-radius:6px;max-height:450px;overflow-y:auto;margin-top:6px;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
  .para-list{{margin:8px 0;padding-left:20px;font-size:13px;color:#444;}}
</style>
</head>
<body>
<h1>Al Jazeera RSS — {today}</h1>
<div class="meta">
  RSS: <a href="{AJ_RSS}" target="_blank">{esc(AJ_RSS)}</a> · Fetched {len(entries)} entries · HTML scrape + og:image + clean_paragraphs (same as PBS)
</div>

<h2>Summary</h2>
<table>
<thead><tr><th>#</th><th>Title</th><th>Published</th><th>Words</th><th>Img?</th></tr></thead>
<tbody>"""]

    for i, e in enumerate(entries, 1):
        title = e.get("title") or ""
        pub = (e.get("published") or "")[:24]
        words = e.get("word_count", 0)
        img_ok = "✓" if e.get("og_image") else "—"
        err = " ⚠" if e.get("fetch_error") else ""
        parts.append(f"""
<tr>
  <td>{i}</td>
  <td><a href="#a{i}">{esc(title)}</a>{err}</td>
  <td>{esc(pub)}</td>
  <td class="words">{words}</td>
  <td>{img_ok}</td>
</tr>""")

    parts.append("""
</tbody>
</table>

<h2>Article cards</h2>""")

    for i, e in enumerate(entries, 1):
        url = e.get("link") or ""
        title = e.get("title") or ""
        pub = (e.get("published") or "")[:24]
        author = e.get("author") or ""
        og_image = e.get("og_image") or ""
        body = e.get("body") or ""
        paragraphs = e.get("paragraphs") or []
        words = e.get("word_count", 0)
        err = e.get("fetch_error", False)

        thumb_html = f'<img src="{esc(og_image)}" alt="" onerror="this.parentNode.innerHTML=\'(image load failed)\'"/>' if og_image else "(no image)"
        err_html = '<div class="fetch-err">⚠ HTML fetch or parse failed</div>' if err else ""

        parts.append(f"""
<div class="card" id="a{i}">
  <div class="hdr">
    <div class="thumb">{thumb_html}</div>
    <div class="body">
      <div class="title">#{i}. <a href="{esc(url)}" target="_blank">{esc(title)}</a></div>
      <div class="date">{esc(pub)}{f' · {esc(author)}' if author else ''} · <span class="words">{words} words</span></div>
    </div>
  </div>
  {err_html}
  <details open><summary>First 5 cleaned paragraphs</summary>
  <div class="para-list">""")

        for p in paragraphs[:5]:
            parts.append(f'<p>• {esc(p[:400])}{"…" if len(p) > 400 else ""}</p>')

        parts.append(f"""
  </div>
  </details>
  <details><summary>Full cleaned body ({words} words)</summary><pre>{esc(body)}</pre></details>
</div>""")

    parts.append("""
</body>
</html>""")
    return "".join(parts)


def main() -> None:
    log.info("Step 1: parse RSS %s", AJ_RSS)
    rss_entries = fetch_rss(AJ_RSS)
    log.info("  %d entries from RSS", len(rss_entries))

    log.info("Step 2: fetch + clean each article's HTML")
    processed = []
    with_image = 0
    with_body = 0
    fetch_errs = 0
    for e in rss_entries:
        p = process_entry(e)
        processed.append(p)
        if p.get("og_image"):
            with_image += 1
        if p.get("word_count", 0) >= 300:
            with_body += 1
        if p.get("fetch_error"):
            fetch_errs += 1

    log.info("  %d/%d got og:image, %d/%d got body ≥300w, %d fetch errors",
             with_image, len(processed), with_body, len(processed), fetch_errs)

    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
              datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "news_aj_rss.json").write_text(
        json.dumps(processed, indent=2, ensure_ascii=False)
    )
    log.info("JSON: %s", out_dir / "news_aj_rss.json")

    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-aj-rss.html")
    html_path.write_text(render_html(processed))
    log.info("HTML: %s", html_path)
    log.info("View at: http://localhost:18100/news-aj-rss.html")


if __name__ == "__main__":
    main()
