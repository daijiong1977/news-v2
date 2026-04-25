"""Fetch 15 news from aljazeera.com + npr.org via Exa.ai.

Exa returns per-article images + highlights (extracted key sentences).

Run:  python -m pipeline.news_exa_list
View: http://localhost:18100/news-exa.html
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

EXA_KEY = os.environ["EXA_API_KEY"]
ENDPOINT = "https://api.exa.ai/search"

DOMAINS = ["aljazeera.com", "npr.org"]
QUERY = "top news stories today"


def fetch() -> dict:
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")
    payload = {
        "query": QUERY,
        "numResults": 15,
        "category": "news",
        "includeDomains": DOMAINS,
        "startPublishedDate": two_days_ago,
        "contents": {
            "text": {"maxCharacters": 12000},
            "highlights": {"numSentences": 3, "highlightsPerUrl": 5, "query": QUERY},
            "summary": True,
            "livecrawl": "fallback",
        },
    }
    r = requests.post(
        ENDPOINT,
        json=payload,
        headers={"x-api-key": EXA_KEY, "Content-Type": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def render_html(data: dict) -> str:
    results = data.get("results", []) or []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(s or "")

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Raw News (Exa) — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:960px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:22px;margin:8px 0;}}
  h2{{font-size:17px;margin:32px 0 12px;border-bottom:1px solid #eee;padding-bottom:6px;color:#444;}}
  .meta{{color:#777;font-size:13px;margin-bottom:24px;}}
  table{{width:100%;border-collapse:collapse;margin-bottom:24px;}}
  th,td{{padding:8px 10px;text-align:left;font-size:14px;border-bottom:1px solid #eee;vertical-align:top;}}
  th{{background:#f6f6f6;font-weight:600;color:#444;}}
  tr:hover td{{background:#fafafa;}}
  .host{{font-size:12px;color:#1a6;background:#e6f5ec;padding:2px 6px;border-radius:3px;display:inline-block;}}
  .host.npr{{color:#c35;background:#fbe7ec;}}
  .words{{color:#888;font-size:12px;}}
  .card{{background:#fff;border:1px solid #e8e8e8;border-radius:8px;padding:16px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,.04);}}
  .card .hdr{{display:flex;gap:14px;margin-bottom:10px;}}
  .card .thumb{{flex:0 0 160px;}}
  .card .thumb img{{width:160px;height:110px;object-fit:cover;border-radius:6px;border:1px solid #eee;}}
  .card .body{{flex:1;min-width:0;}}
  .card .title{{font-size:16px;font-weight:600;margin:0 0 6px;line-height:1.3;}}
  .card .summary{{font-size:13px;color:#555;margin:6px 0 10px;}}
  .highlights{{background:#fffbea;border-left:3px solid #f0c050;padding:10px 14px;margin:10px 0;border-radius:4px;}}
  .highlights h4{{font-size:12px;font-weight:700;color:#a87a00;margin:0 0 6px;text-transform:uppercase;letter-spacing:.04em;}}
  .highlights p{{margin:6px 0;font-size:13px;color:#3a2d00;}}
  details{{margin:8px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:13px;user-select:none;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:#fafafa;padding:12px;border-radius:6px;max-height:400px;overflow-y:auto;margin-top:6px;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<h1>Raw News from Exa — {today}</h1>
<div class="meta">
  Query: <code>{esc(QUERY)}</code> · Domains: {", ".join(DOMAINS)} · last 2 days · numResults=15 · Manual pick mode (no vet)
</div>

<h2>Articles ({len(results)})</h2>
<table>
<thead><tr><th>#</th><th>Host</th><th>Title</th><th>Published</th><th>Words</th><th>Img?</th></tr></thead>
<tbody>"""]

    for i, r in enumerate(results, 1):
        url = r.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")
        host_class = "npr" if "npr" in host else ""
        title = r.get("title") or ""
        pub = (r.get("publishedDate") or "")[:10]
        text = r.get("text") or ""
        words = len(text.split()) if text else 0
        img = "✓" if r.get("image") else ""
        parts.append(f"""
<tr>
  <td>{i}</td>
  <td><span class="host {host_class}">{esc(host)}</span></td>
  <td><a href="#a{i}">{esc(title)}</a></td>
  <td>{esc(pub)}</td>
  <td class="words">{words}</td>
  <td>{img}</td>
</tr>""")

    parts.append("""
</tbody>
</table>

<h2>Article cards (highlights + summary + full text)</h2>""")

    for i, r in enumerate(results, 1):
        url = r.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")
        host_class = "npr" if "npr" in host else ""
        title = r.get("title") or ""
        pub = (r.get("publishedDate") or "")[:10]
        author = r.get("author") or ""
        image = r.get("image") or ""
        text = r.get("text") or ""
        summary = r.get("summary") or ""
        highlights = r.get("highlights") or []
        words = len(text.split()) if text else 0

        thumb_html = f'<img src="{esc(image)}" alt="" onerror="this.parentNode.innerHTML=\'(no image)\'"/>' if image else "(no image)"
        highlights_html = ""
        if highlights:
            h_items = "\n".join(f"  <p>• {esc(h)}</p>" for h in highlights)
            highlights_html = f'<div class="highlights"><h4>Key highlights (Exa extraction)</h4>{h_items}</div>'

        parts.append(f"""
<div class="card" id="a{i}">
  <div class="hdr">
    <div class="thumb">{thumb_html}</div>
    <div class="body">
      <div class="title">#{i}. <a href="{esc(url)}" target="_blank">{esc(title)}</a></div>
      <div><span class="host {host_class}">{esc(host)}</span> · {esc(pub)} · {esc(author)} · <span class="words">{words} words</span></div>
      <div class="summary"><strong>Exa summary:</strong> {esc(summary)}</div>
    </div>
  </div>
  {highlights_html}
  <details><summary>Full text ({words} words)</summary><pre>{esc(text)}</pre></details>
</div>""")

    parts.append("""
</body>
</html>""")
    return "".join(parts)


def main() -> None:
    print(f"Calling Exa: domains={DOMAINS}, query='{QUERY}', numResults=15 ...")
    data = fetch()

    out_dir = (_REPO_ROOT / "website/test_output")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir_date = out_dir / today
    out_dir_date.mkdir(parents=True, exist_ok=True)

    json_path = out_dir_date / "news_exa.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"JSON written: {json_path}")

    html_path = (_REPO_ROOT / "website/news-exa.html")
    html_path.write_text(render_html(data))
    print(f"HTML written: {html_path}")

    results = data.get("results") or []
    print()
    print(f"Results: {len(results)} articles")
    hosts = {}
    with_img = 0
    with_hl = 0
    for r in results:
        h = urlparse(r.get("url") or "").netloc.replace("www.", "")
        hosts[h] = hosts.get(h, 0) + 1
        if r.get("image"):
            with_img += 1
        if r.get("highlights"):
            with_hl += 1
    print(f"Per host: {hosts}")
    print(f"With image: {with_img}/{len(results)}")
    print(f"With highlights: {with_hl}/{len(results)}")
    print(f"View at: http://localhost:18100/news-exa.html")


if __name__ == "__main__":
    main()
