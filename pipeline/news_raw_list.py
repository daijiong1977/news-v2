"""Fetch 15 news from NPR+Reuters+BBC+Guardian with no vet.
Writes raw JSON + simple manual-pick HTML page.

Run:  python -m pipeline.news_raw_list
View: http://localhost:18100/news-raw.html
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

# Load .env manually
_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

TAVILY_KEY = os.environ["TAVILY_API_KEY"]
ENDPOINT = "https://api.tavily.com/search"

DOMAINS = ["npr.org", "reuters.com", "bbc.com", "theguardian.com"]
QUERY = "top news stories today"


def fetch() -> dict:
    r = requests.post(ENDPOINT, json={
        "api_key": TAVILY_KEY,
        "query": QUERY,
        "topic": "news",
        "days": 3,
        "search_depth": "advanced",
        "include_raw_content": True,
        "include_images": True,
        "include_image_descriptions": True,
        "include_domains": DOMAINS,
        "max_results": 15,
    }, timeout=60)
    r.raise_for_status()
    return r.json()


def render_html(data: dict) -> str:
    results = data.get("results", []) or []
    images = data.get("images", []) or []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(s or "")

    def img_desc(img):
        if isinstance(img, dict):
            return img.get("description") or ""
        return ""

    def img_url(img):
        if isinstance(img, dict):
            return img.get("url") or ""
        return img or ""

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Raw News — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:960px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:22px;margin:8px 0;}}
  h2{{font-size:16px;margin:28px 0 12px;border-bottom:1px solid #eee;padding-bottom:6px;color:#555;}}
  .meta{{color:#777;font-size:13px;margin-bottom:24px;}}
  table{{width:100%;border-collapse:collapse;margin-bottom:24px;}}
  th,td{{padding:8px 10px;text-align:left;font-size:14px;border-bottom:1px solid #eee;vertical-align:top;}}
  th{{background:#f6f6f6;font-weight:600;color:#444;}}
  tr:hover td{{background:#fafafa;}}
  .host{{font-size:12px;color:#1a6;background:#e6f5ec;padding:2px 6px;border-radius:3px;display:inline-block;}}
  .words{{color:#888;font-size:12px;}}
  .card{{background:#fff;border:1px solid #eee;border-radius:8px;padding:16px;margin:12px 0;}}
  .img-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:24px;}}
  .img-card{{border:1px solid #eee;border-radius:8px;overflow:hidden;background:#fff;}}
  .img-card img{{display:block;width:100%;height:120px;object-fit:cover;}}
  .img-card .desc{{padding:8px 10px;font-size:12px;color:#555;}}
  details{{margin:8px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:13px;user-select:none;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:#fafafa;padding:12px;border-radius:6px;max-height:400px;overflow-y:auto;margin-top:6px;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<h1>Raw News from Tavily — {today}</h1>
<div class="meta">
  Query: <code>{esc(QUERY)}</code> · Domains: {", ".join(DOMAINS)} · days=3 · max_results=15 · Manual pick mode (no vet)
</div>

<h2>Images returned ({len(images)})</h2>
<div class="img-grid">"""]

    for i, img in enumerate(images):
        u = img_url(img)
        d = img_desc(img)
        parts.append(f"""
  <div class="img-card">
    <img src="{esc(u)}" alt="" onerror="this.style.display='none'"/>
    <div class="desc">{esc(d)[:200]}</div>
  </div>""")

    parts.append(f"""
</div>

<h2>Articles ({len(results)})</h2>
<table>
<thead><tr><th>#</th><th>Host</th><th>Title</th><th>Words</th></tr></thead>
<tbody>""")

    for i, r in enumerate(results, 1):
        url = r.get("url", "")
        host = urlparse(url).netloc.replace("www.", "")
        title = r.get("title") or ""
        raw = r.get("raw_content") or ""
        words = len(raw.split()) if raw else 0
        parts.append(f"""
<tr>
  <td>{i}</td>
  <td><span class="host">{esc(host)}</span></td>
  <td><a href="{esc(url)}" target="_blank">{esc(title)}</a></td>
  <td class="words">{words}</td>
</tr>""")

    parts.append("""
</tbody>
</table>

<h2>Full article content</h2>""")

    for i, r in enumerate(results, 1):
        url = r.get("url", "")
        host = urlparse(url).netloc.replace("www.", "")
        title = r.get("title") or ""
        snippet = r.get("content") or ""
        raw = r.get("raw_content") or ""
        words = len(raw.split()) if raw else 0
        parts.append(f"""
<div class="card">
  <div><strong>#{i}. {esc(title)}</strong></div>
  <div><span class="host">{esc(host)}</span> · <span class="words">{words} words</span> · <a href="{esc(url)}" target="_blank">source ↗</a></div>
  <details><summary>Snippet ({len(snippet)} chars)</summary><pre>{esc(snippet)}</pre></details>
  <details><summary>Full raw_content ({words} words)</summary><pre>{esc(raw)}</pre></details>
</div>""")

    parts.append("""
</body>
</html>""")
    return "".join(parts)


def main() -> None:
    print(f"Calling Tavily: domains={DOMAINS}, query='{QUERY}', max_results=15 ...")
    data = fetch()

    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir_date = out_dir / today
    out_dir_date.mkdir(parents=True, exist_ok=True)

    json_path = out_dir_date / "news_raw.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"JSON written: {json_path}")

    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-raw.html")
    html_path.write_text(render_html(data))
    print(f"HTML written: {html_path}")
    print()
    print(f"Results: {len(data.get('results') or [])} articles, {len(data.get('images') or [])} images")
    print(f"View at: http://localhost:18100/news-raw.html")


if __name__ == "__main__":
    main()
