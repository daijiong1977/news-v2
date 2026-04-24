"""End-to-end News test: Exa → filter → curator → rewrite → preview.

Pipeline:
  1. Exa search (aljazeera.com + npr.org), 15 results with highlights
  2. Filter: has image AND word_count >= 800 → take first 10 survivors
  3. DeepSeek curator: pick 3 best from 10 briefs
  4. DeepSeek rewriter: generate 500-word kids article per pick from highlights
  5. Render HTML with all stages for user review

Run:  python -m pipeline.news_exa_pipeline
View: http://localhost:18100/news-exa-kids.html
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("exa-pipeline")

# Load .env
_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

EXA_KEY = os.environ["EXA_API_KEY"]
DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]

EXA_ENDPOINT = "https://api.exa.ai/search"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

DOMAINS = ["aljazeera.com", "npr.org"]
QUERY = "top news stories today"
MIN_WORDS = 800
MAX_AFTER_FILTER = 10

# ---------------------------------------------------------------------------
# Step 1: Exa
# ---------------------------------------------------------------------------

def fetch_exa() -> dict:
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
    r = requests.post(EXA_ENDPOINT, json=payload,
                      headers={"x-api-key": EXA_KEY, "Content-Type": "application/json"},
                      timeout=60)
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------------------------
# Step 2: Filter + clean
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip common junk from Exa-returned text."""
    if not text:
        return ""
    # Collapse 3+ newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace per paragraph
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out = []
    for p in paragraphs:
        # Skip obvious junk paragraphs
        low = p.lower()
        if len(p) < 20 and not p.endswith("."):
            continue
        if low.startswith(("subscribe", "sign up", "follow us", "related:", "read more:", "also read:")):
            continue
        if "newsletter" in low and len(p) < 150:
            continue
        out.append(p)
    return "\n\n".join(out)


def apply_filters(results: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split into (kept, rejected) with reasons."""
    kept, rejected = [], []
    for r in results:
        img = r.get("image")
        text = r.get("text") or ""
        cleaned = clean_text(text)
        words = len(cleaned.split())
        reasons = []
        if not img:
            reasons.append("no image")
        if words < MIN_WORDS:
            reasons.append(f"{words}w < {MIN_WORDS}w")
        if reasons:
            r["_reject_reason"] = " + ".join(reasons)
            rejected.append(r)
        else:
            r["_cleaned_text"] = cleaned
            r["_word_count"] = words
            kept.append(r)
    return kept[:MAX_AFTER_FILTER], rejected

# ---------------------------------------------------------------------------
# Step 3: Curator
# ---------------------------------------------------------------------------

CURATOR_PROMPT = """You are curating kid-appropriate news for ages 8-13.
You have news briefs from Al Jazeera and NPR.

Pick exactly 3 stories best for kids. Prefer:
- Important world events with human / kid angle
- Surprising discoveries or stories
- Balance of sources (don't pick 3 from same host if avoidable)

Avoid:
- Pure politics without narrative
- Graphic violence / conflict details
- Gossip, obituaries
- Business / financial jargon without human impact

Return ONLY valid JSON:
{
  "picks": [
    {"id": "<exa_id>", "reason": "one short sentence"},
    {"id": "<exa_id>", "reason": "one short sentence"},
    {"id": "<exa_id>", "reason": "one short sentence"}
  ]
}"""


def curator_input(briefs: list[dict]) -> str:
    lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
    for b in briefs:
        host = urlparse(b.get("url") or "").netloc.replace("www.", "")
        hls = b.get("highlights") or []
        hls_text = " | ".join(hls[:3]) if hls else (b.get("summary") or "")
        lines.append(f"[id: {b['id']}] {b.get('title','')}")
        lines.append(f"  host: {host}")
        lines.append(f"  key points: {hls_text[:300]}")
        lines.append("")
    lines.append("Now return the picks JSON per the rules.")
    return "\n".join(lines)


def deepseek_call(system: str, user: str, max_tokens: int = 800, temperature: float = 0.2) -> dict:
    r = requests.post(DEEPSEEK_ENDPOINT,
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        timeout=60)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    content = re.sub(r"^```json\s*", "", content.strip())
    content = re.sub(r"\s*```\s*$", "", content)
    return json.loads(content)


def curate(briefs: list[dict]) -> dict:
    return deepseek_call(CURATOR_PROMPT, curator_input(briefs), max_tokens=800)

# ---------------------------------------------------------------------------
# Step 4: Rewriter (500-word kids article)
# ---------------------------------------------------------------------------

REWRITER_PROMPT = """You are a children's journalist writing for "News Oh, Ye!" — a news site for ages 8-13.

You will receive: article title, source, key highlights (extracted sentences).
Your job: write a 500-word (±50) kids article at a 5th-6th grade reading level.

RULES:
1. 450-550 words total in the body
2. Grade 5-6 reading level (short sentences, common vocabulary; explain any hard word inline)
3. Engaging tone — active voice, hook at the start, rhetorical questions OK
4. Every fact must come from the highlights/source — no invention
5. Short paragraphs (2-4 sentences each), separated by \\n\\n
6. End with a "Why it matters" paragraph kids can connect to
7. Create a kid-friendly headline (different from the source headline)

Return ONLY valid JSON (no markdown fences):
{
  "headline": "kid-friendly headline",
  "body": "full article body with \\n\\n between paragraphs",
  "why_it_matters": "1-2 sentences about why kids should care",
  "word_count": 500
}"""


def rewriter_input(article: dict) -> str:
    hls = article.get("highlights") or []
    hls_text = "\n".join(f"- {h}" for h in hls) if hls else article.get("summary", "")
    host = urlparse(article.get("url") or "").netloc.replace("www.", "")
    summary = article.get("summary") or ""
    return f"""SOURCE TITLE: {article.get('title', '')}
SOURCE HOST: {host}
EXA SUMMARY: {summary}

KEY HIGHLIGHTS (extracted sentences, most relevant first):
{hls_text}

Write a 500-word kids article covering this story per the rules."""


def rewrite_for_kids(article: dict) -> dict | None:
    try:
        return deepseek_call(REWRITER_PROMPT, rewriter_input(article),
                             max_tokens=1500, temperature=0.4)
    except (requests.HTTPError, json.JSONDecodeError, KeyError) as e:
        log.warning("rewriter failed for %s: %s", article.get("id"), e)
        return None

# ---------------------------------------------------------------------------
# Step 5: HTML render
# ---------------------------------------------------------------------------

def render_html(exa_raw: dict, kept: list[dict], rejected: list[dict],
                curator_result: dict, kids_articles: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(s or "")

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Exa News Pipeline — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:960px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:24px;margin:8px 0;}}
  h2{{font-size:18px;margin:32px 0 12px;border-bottom:2px solid #eee;padding-bottom:6px;color:#444;}}
  h3{{font-size:15px;margin:20px 0 8px;color:#555;}}
  .meta{{color:#777;font-size:13px;margin-bottom:18px;}}
  .stats{{background:#f6f6f6;border-radius:6px;padding:12px 16px;margin:12px 0;font-size:13px;color:#555;}}
  .stats b{{color:#222;}}
  table{{width:100%;border-collapse:collapse;margin-bottom:18px;font-size:13px;}}
  th,td{{padding:6px 8px;text-align:left;border-bottom:1px solid #eee;vertical-align:top;}}
  th{{background:#f0f0f0;font-weight:600;}}
  .host{{font-size:11px;color:#1a6;background:#e6f5ec;padding:2px 6px;border-radius:3px;display:inline-block;}}
  .host.npr{{color:#c35;background:#fbe7ec;}}
  .rejected{{color:#a33;}}
  .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;}}
  .pill.kept{{background:#d8f3e0;color:#266;}}
  .pill.reject{{background:#f9d6d6;color:#933;}}
  .kids-article{{background:#fff9ef;border:2px solid #ffc83d;border-radius:10px;padding:20px 24px;margin:24px 0;box-shadow:0 2px 6px rgba(0,0,0,.06);}}
  .kids-article .kheadline{{font-size:22px;font-weight:800;color:#1b1230;margin:0 0 6px;font-family:Georgia,serif;}}
  .kids-article .ksrc{{font-size:12px;color:#8a6d00;margin-bottom:8px;}}
  .kids-article img{{max-width:100%;border-radius:6px;margin:10px 0;}}
  .kids-article .kbody{{font-size:15px;line-height:1.6;color:#221a10;}}
  .kids-article .kbody p{{margin:0 0 12px;}}
  .kids-article .kwim{{background:#fff3c4;border-left:4px solid #e0a800;padding:10px 14px;margin-top:14px;border-radius:4px;font-style:italic;}}
  .kids-article .kwim b{{color:#8a6d00;}}
  .wc{{color:#666;font-size:12px;}}
  .reason{{background:#eef6ff;border-left:3px solid #4a90e2;padding:6px 10px;margin:8px 0;font-size:13px;color:#204060;}}
  details{{margin:8px 0;}}
  details summary{{cursor:pointer;color:#07c;font-size:13px;}}
  details pre{{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;background:#fafafa;padding:10px;border-radius:6px;max-height:300px;overflow-y:auto;margin-top:6px;}}
  a{{color:#07c;text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
  .highlights{{background:#fffbea;border-left:3px solid #f0c050;padding:8px 12px;margin:8px 0;border-radius:4px;font-size:13px;}}
  .highlights p{{margin:4px 0;color:#3a2d00;}}
</style>
</head>
<body>
<h1>Exa News Pipeline — {today}</h1>
<div class="meta">
  Exa query: <code>{esc(QUERY)}</code> · Domains: {", ".join(DOMAINS)} · filter: image + {MIN_WORDS}+ words · max={MAX_AFTER_FILTER}
</div>

<div class="stats">
  <b>Step 1 Exa:</b> {len(exa_raw.get("results") or [])} results ·
  <b>Step 2 Filter:</b> {len(kept)} kept, {len(rejected)} rejected ·
  <b>Step 3 Curator:</b> {len(curator_result.get("picks") or [])} picks ·
  <b>Step 4 Kids articles:</b> {len(kids_articles)} generated
</div>

<h2>Step 1 → Step 2: Filter results</h2>
<table>
<thead><tr><th>#</th><th>Host</th><th>Title</th><th>Words</th><th>Img</th><th>Status</th></tr></thead>
<tbody>"""]

    for i, r in enumerate(kept, 1):
        url = r.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")
        host_class = "npr" if "npr" in host else ""
        title = r.get("title") or ""
        words = r.get("_word_count", 0)
        img_ok = "✓" if r.get("image") else "—"
        parts.append(f"""
<tr>
  <td>{i}</td>
  <td><span class="host {host_class}">{esc(host)}</span></td>
  <td><a href="{esc(url)}" target="_blank">{esc(title)}</a></td>
  <td>{words}</td>
  <td>{img_ok}</td>
  <td><span class="pill kept">KEPT</span></td>
</tr>""")

    for r in rejected:
        url = r.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")
        host_class = "npr" if "npr" in host else ""
        title = r.get("title") or ""
        text = r.get("text") or ""
        words = len(text.split())
        img_ok = "✓" if r.get("image") else "—"
        reason = r.get("_reject_reason", "")
        parts.append(f"""
<tr class="rejected">
  <td>–</td>
  <td><span class="host {host_class}">{esc(host)}</span></td>
  <td>{esc(title)}</td>
  <td>{words}</td>
  <td>{img_ok}</td>
  <td><span class="pill reject">{esc(reason)}</span></td>
</tr>""")

    parts.append("""
</tbody>
</table>

<h2>Step 3: Curator picks (DeepSeek from 10 briefs)</h2>""")

    picks = curator_result.get("picks") or []
    kept_by_id = {r["id"]: r for r in kept}
    for p in picks:
        pid = p.get("id")
        art = kept_by_id.get(pid)
        if not art:
            parts.append(f'<div class="reason">⚠️ Curator picked id={pid} but not in kept list</div>')
            continue
        url = art.get("url") or ""
        host = urlparse(url).netloc.replace("www.", "")
        parts.append(f"""
<div class="reason"><b>Pick:</b> <a href="{esc(url)}" target="_blank">{esc(art.get('title',''))}</a> ({esc(host)})<br>
<b>Reason:</b> {esc(p.get('reason',''))}</div>""")

    parts.append("""
<h2>Step 4: Generated kids articles (500 words each)</h2>""")

    for ka in kids_articles:
        src = ka.get("source", {})
        kids = ka.get("kids", {})
        src_url = src.get("url") or ""
        src_host = urlparse(src_url).netloc.replace("www.", "")
        img = src.get("image") or ""
        headline = kids.get("headline") or "(no headline)"
        body = kids.get("body") or ""
        body_paragraphs = "\n".join(f"    <p>{esc(p)}</p>" for p in body.split("\n\n") if p.strip())
        wim = kids.get("why_it_matters") or ""
        wc = len(body.split()) if body else 0
        hls = src.get("highlights") or []
        hls_html = "\n".join(f"  <p>• {esc(h)}</p>" for h in hls)

        parts.append(f"""
<div class="kids-article">
  <div class="ksrc">📰 Source: <a href="{esc(src_url)}" target="_blank">{esc(src.get('title',''))}</a> · {esc(src_host)} · <span class="wc">generated {wc} words</span></div>
  {f'<img src="{esc(img)}" alt=""/>' if img else ''}
  <div class="kheadline">{esc(headline)}</div>
  <div class="kbody">
{body_paragraphs}
  </div>
  <div class="kwim"><b>Why it matters:</b> {esc(wim)}</div>

  <details><summary>Show source highlights (Exa)</summary>
  <div class="highlights">
{hls_html}
  </div>
  </details>
</div>""")

    parts.append("""
</body>
</html>""")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Step 1: Exa fetch (domains=%s, n=15)", DOMAINS)
    exa_raw = fetch_exa()

    log.info("Step 2: filter (image + %d+ words, max=%d)", MIN_WORDS, MAX_AFTER_FILTER)
    kept, rejected = apply_filters(exa_raw.get("results") or [])
    log.info("  kept=%d, rejected=%d", len(kept), len(rejected))
    for r in rejected:
        log.info("    rej: %s — %s", (r.get("title") or "")[:60], r.get("_reject_reason"))

    if len(kept) < 3:
        log.error("Only %d candidates after filter — cannot curate 3", len(kept))
        return

    log.info("Step 3: curator (DeepSeek picks 3 of %d)", len(kept))
    curator_result = curate(kept)
    picks = curator_result.get("picks") or []
    log.info("  curator picks: %s", [p.get("id") for p in picks])

    kept_by_id = {r["id"]: r for r in kept}
    log.info("Step 4: rewrite each pick for kids (DeepSeek × %d)", len(picks))
    kids_articles = []
    for p in picks:
        art = kept_by_id.get(p.get("id"))
        if not art:
            continue
        kids = rewrite_for_kids(art)
        if kids:
            kids_articles.append({"source": art, "kids": kids, "curator_reason": p.get("reason")})
            log.info("  ✓ kids article: %s (%d words)", kids.get("headline","")[:60],
                     len((kids.get("body","")).split()))
        else:
            log.warning("  ✗ rewrite failed for %s", art.get("title"))

    out_dir = Path("/Users/jiong/myprojects/news-v2/website/test_output") / \
              datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "exa": {"query": QUERY, "domains": DOMAINS, "raw_count": len(exa_raw.get("results") or [])},
        "kept_count": len(kept), "rejected_count": len(rejected),
        "curator": curator_result,
        "kids_articles": [{"source_id": k["source"]["id"],
                           "source_title": k["source"].get("title"),
                           "source_url": k["source"].get("url"),
                           "source_image": k["source"].get("image"),
                           "source_highlights": k["source"].get("highlights"),
                           "kids": k["kids"],
                           "curator_reason": k["curator_reason"]} for k in kids_articles],
    }
    (out_dir / "news_exa_pipeline.json").write_text(json.dumps(out_json, indent=2, ensure_ascii=False))
    log.info("JSON: %s", out_dir / "news_exa_pipeline.json")

    html_path = Path("/Users/jiong/myprojects/news-v2/website/news-exa-kids.html")
    html_path.write_text(render_html(exa_raw, kept, rejected, curator_result, kids_articles))
    log.info("HTML: %s", html_path)
    log.info("View at: http://localhost:18100/news-exa-kids.html")


if __name__ == "__main__":
    main()
