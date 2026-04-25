"""Verify a source by pulling its 3 most-recent articles and rendering a
self-contained HTML preview page (image + body + links). Reuses the exact
same cleanup + og:image stripping the live pipeline uses, so what you see
matches what the pipeline would produce.

Usage:

  # by source id from redesign_source_configs:
  python -m pipeline.verify_source --source-id 5

  # by raw rss url (no DB lookup needed):
  python -m pipeline.verify_source --rss-url 'https://example.com/feed.rss'

  # verify everything in a category:
  python -m pipeline.verify_source --category News

  # verify everything (all rows in redesign_source_configs):
  python -m pipeline.verify_source --all

Outputs land in `out/verify/<YYYYMMDD-HHMMSS>/<source-slug>.html`. Open
the directory's `index.html` for a list of all verified sources.

If `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` are set, the HTML files are
also uploaded to Supabase Storage at
`verify/<YYYYMMDD-HHMMSS>/<source-slug>.html` so an admin in CI can
share a public link.
"""
from __future__ import annotations

import argparse
import html as htmllib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

from .cleaner import extract_article_from_html
from .image_optimize import optimize_bytes, download_image

log = logging.getLogger("verify-source")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HTML_TIMEOUT = 15
N_LATEST = 3


# ─────────────────────────────────────────────────────────────────────
# Pull + extract one article (uses the same cleaner the pipeline uses)
# ─────────────────────────────────────────────────────────────────────
def _fetch_article(link: str) -> dict:
    out: dict = {"link": link, "og_image": None, "body": "", "word_count": 0,
                 "error": None}
    try:
        r = requests.get(link, headers={"User-Agent": UA},
                         timeout=HTML_TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            out["error"] = f"HTTP {r.status_code}"
            return out
        ext = extract_article_from_html(link, r.text)
        out["og_image"] = ext.get("og_image")
        cleaned = ext.get("cleaned_body") or ""
        out["body"] = cleaned[:5000]
        out["word_count"] = len(cleaned.split())
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _maybe_optimize_image(url: str | None) -> tuple[str | None, dict | None]:
    """Try to download + WebP-optimize the og:image (matches what the
    pipeline does on real articles). Returns (data_uri, info_dict) or
    (None, None) on failure."""
    if not url:
        return None, None
    raw = download_image(url)
    if not raw:
        return None, None
    try:
        webp, info = optimize_bytes(raw)
    except Exception as e:  # noqa: BLE001
        return None, {"error": str(e)}
    import base64
    data_uri = "data:image/webp;base64," + base64.b64encode(webp).decode()
    return data_uri, info


# ─────────────────────────────────────────────────────────────────────
# RSS parse → top N items
# ─────────────────────────────────────────────────────────────────────
def _verify_one(rss_url: str, n: int = N_LATEST) -> dict:
    log.info("verify: %s", rss_url)
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:  # noqa: BLE001
        return {"rss_url": rss_url, "error": f"feedparser failed: {e}",
                "items": []}
    if feed.bozo and not getattr(feed, "entries", None):
        return {"rss_url": rss_url,
                "error": f"feed parse error: {feed.bozo_exception}",
                "items": []}

    items = []
    for entry in feed.entries[:n]:
        link = (getattr(entry, "link", "") or "").strip()
        title = htmllib.unescape(getattr(entry, "title", "") or "")
        published = (getattr(entry, "published", "")
                     or getattr(entry, "updated", "") or "")
        if not link:
            items.append({"title": title, "link": "", "published": published,
                          "error": "no link in feed item"})
            continue
        art = _fetch_article(link)
        og_data_uri, og_info = _maybe_optimize_image(art.get("og_image"))
        items.append({
            "title": title,
            "link": link,
            "published": published,
            "og_image": art.get("og_image"),
            "og_image_data_uri": og_data_uri,
            "og_image_dims": og_info.get("dims") if og_info and "dims" in og_info else None,
            "body": art.get("body"),
            "word_count": art.get("word_count"),
            "error": art.get("error"),
        })
    return {
        "rss_url": rss_url,
        "feed_title": getattr(feed.feed, "title", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }


# ─────────────────────────────────────────────────────────────────────
# HTML render
# ─────────────────────────────────────────────────────────────────────
_CSS = """
body{font-family:-apple-system,sans-serif;background:#fff9ef;margin:0;padding:24px;color:#1b1230}
.wrap{max-width:1080px;margin:0 auto}
.card{background:#fff;border:1.5px solid #f0e8d8;border-radius:14px;padding:20px;margin-bottom:18px;box-shadow:0 2px 0 rgba(27,18,48,.05)}
.h{font-family:'Fraunces',serif;font-weight:800;letter-spacing:-.01em}
.muted{color:#6b5c80;font-size:13px}
.pre{font-family:ui-monospace,Menlo,monospace;font-size:11px;background:#1b1230;color:#ffe2a8;padding:3px 8px;border-radius:5px}
.err{background:#fff0e8;color:#c14e2a;padding:8px 12px;border-radius:8px;border:1.5px solid #f4c4ad;font-size:13px}
.ok{background:#e0f6f3;color:#0e8d82;padding:8px 12px;border-radius:8px;border:1.5px solid #8fd6cd;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.art{background:#fbf6ec;border-radius:10px;padding:12px;font-size:13px;display:flex;flex-direction:column;gap:8px}
.art img{width:100%;height:160px;object-fit:cover;border-radius:6px;background:#f0e8d8}
.art .t{font-weight:800;font-size:14px;line-height:1.3}
.art .b{white-space:pre-wrap;color:#3a2a4a;line-height:1.5;max-height:300px;overflow:auto;font-size:12px}
a{color:#1f6bbf;text-decoration:none}
a:hover{text-decoration:underline}
"""


def _render_one(verify_result: dict, source_name: str) -> str:
    items = verify_result.get("items") or []
    rss_url = verify_result.get("rss_url", "")
    feed_title = verify_result.get("feed_title", "")
    feed_err = verify_result.get("error")

    parts: list[str] = [f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>verify: {htmllib.escape(source_name)}</title>
<style>{_CSS}</style></head><body><div class="wrap">"""]

    parts.append(f'<div class="card"><h1 class="h">🔍 {htmllib.escape(source_name)}</h1>')
    parts.append(f'<div class="muted">Feed title: <b>{htmllib.escape(feed_title)}</b> · '
                 f'RSS: <span class="pre">{htmllib.escape(rss_url)}</span> · '
                 f'fetched {htmllib.escape(verify_result.get("fetched_at",""))}</div>')

    if feed_err:
        parts.append(f'<div class="err" style="margin-top:10px">RSS error: {htmllib.escape(feed_err)}</div>')
    parts.append("</div>")  # close header card

    if items:
        parts.append('<div class="card"><h2 class="h" style="margin-top:0">Latest 3</h2><div class="grid">')
        for it in items:
            err = it.get("error")
            og_uri = it.get("og_image_data_uri")
            og_url = it.get("og_image") or ""
            dims = it.get("og_image_dims") or ()
            wc = it.get("word_count") or 0
            parts.append('<div class="art">')
            if og_uri:
                parts.append(f'<img src="{og_uri}">')
                if dims:
                    parts.append(f'<div class="muted" style="font-size:10px">og:image {dims[0]}×{dims[1]}</div>')
            elif og_url:
                parts.append(f'<div class="err" style="font-size:11px">og:image found but optimize failed: {htmllib.escape(og_url)}</div>')
            else:
                parts.append('<div class="err" style="font-size:11px">no og:image</div>')

            parts.append(f'<div class="t">'
                         f'<a href="{htmllib.escape(it.get("link") or "#")}" target="_blank" rel="noopener">'
                         f'{htmllib.escape(it.get("title") or "(no title)")}</a></div>')

            pub = it.get("published") or ""
            if pub:
                parts.append(f'<div class="muted" style="font-size:11px">{htmllib.escape(pub)}</div>')

            if err:
                parts.append(f'<div class="err" style="font-size:11px">fetch error: {htmllib.escape(err)}</div>')
            else:
                parts.append(f'<div class="muted" style="font-size:11px">{wc} words extracted</div>')
                body = it.get("body") or "(no body)"
                parts.append(f'<div class="b">{htmllib.escape(body)}</div>')
            parts.append('</div>')
        parts.append('</div></div>')

    parts.append("</div></body></html>")
    return "".join(parts)


def _render_index(results: list[tuple[str, dict, Path]]) -> str:
    """Top-level index for a multi-source verify run."""
    rows = []
    for name, res, html_path in results:
        items = res.get("items") or []
        ok_count = sum(1 for it in items if not it.get("error") and it.get("og_image"))
        verdict = "ok" if not res.get("error") and len(items) == N_LATEST and ok_count == N_LATEST else "warn"
        cls = "ok" if verdict == "ok" else "err"
        msg = f"{ok_count}/{len(items)} articles fully extracted" if not res.get("error") else f"feed error: {res.get('error')}"
        rows.append(
            f'<div class="art" style="display:flex;justify-content:space-between;align-items:center">'
            f'<div><b><a href="./{html_path.name}">{htmllib.escape(name)}</a></b><br>'
            f'<span class="muted">{htmllib.escape(res.get("rss_url",""))}</span></div>'
            f'<div class="{cls}" style="white-space:nowrap">{htmllib.escape(msg)}</div></div>'
        )
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>verify run</title><style>{_CSS}</style></head>"
            f"<body><div class='wrap'><h1 class='h'>🔍 Verify run · {datetime.now(timezone.utc).isoformat(timespec='seconds')}</h1>"
            f"<div class='card' style='display:flex;flex-direction:column;gap:8px'>"
            + "".join(rows)
            + "</div></div></body></html>")


# ─────────────────────────────────────────────────────────────────────
# DB-backed source lookup (optional)
# ─────────────────────────────────────────────────────────────────────
def _load_sources(by_id: int | None, by_category: str | None,
                  all_rows: bool) -> list[dict]:
    if not (by_id or by_category or all_rows):
        return []
    from .supabase_io import client
    sb = client()
    q = sb.table("redesign_source_configs").select("*").order("category").order("priority")
    if by_id is not None:
        q = q.eq("id", by_id)
    elif by_category:
        q = q.eq("category", by_category)
    res = q.execute()
    return list(res.data or [])


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "source"


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Verify RSS source(s) — render HTML preview")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--source-id", type=int)
    g.add_argument("--rss-url", type=str)
    g.add_argument("--category", type=str)
    g.add_argument("--all", action="store_true")
    p.add_argument("--name", type=str, default="", help="display name when using --rss-url")
    p.add_argument("--out", type=Path, default=None, help="output directory (default: out/verify/<timestamp>/)")
    p.add_argument("--upload", action="store_true",
                   help="also upload to Supabase Storage at verify/<timestamp>/ (needs SUPABASE_*)")
    args = p.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = args.out or Path("out") / "verify" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    # (label, rss_url, source_id-or-None) per target.
    targets_with_id: list[tuple[str, str, int | None]] = []
    if args.rss_url:
        targets_with_id.append((args.name or args.rss_url, args.rss_url, None))
    else:
        rows = _load_sources(args.source_id, args.category, args.all)
        if not rows:
            print("No sources matched.", file=sys.stderr)
            sys.exit(2)
        for r in rows:
            label = f"{r.get('category','?')} · {r.get('name','?')}"
            targets_with_id.append((label, r.get("rss_url") or "", r.get("id")))

    log.info("verifying %d source(s) → %s", len(targets_with_id), out_dir)
    results: list[tuple[str, dict, Path]] = []
    successful_source_ids: list[int] = []  # rows whose verify produced usable extraction

    for name, rss_url, src_id in targets_with_id:
        if not rss_url:
            log.warning("skip (no rss_url): %s", name); continue
        t0 = time.monotonic()
        res = _verify_one(rss_url)
        elapsed = time.monotonic() - t0
        log.info("  %s · %.1fs · %d items", name, elapsed, len(res.get("items") or []))
        html = _render_one(res, name)
        slug = _slug(name)
        path = out_dir / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
        results.append((name, res, path))
        # A "successful" verify = no top-level feed error AND at least
        # one article extracted with body. Lets stale-by-60-days sweep
        # flag truly broken sources without false positives.
        items = res.get("items") or []
        ok = (not res.get("error")) and any(
            (it.get("body") or "").strip() and not it.get("error") for it in items
        )
        if ok and src_id is not None:
            successful_source_ids.append(src_id)

    # Stamp last_verified_at for sources whose verify produced usable
    # extraction. Best-effort — failure here doesn't fail the run.
    if successful_source_ids:
        try:
            from .supabase_io import client
            now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
            sb = client()
            sb.table("redesign_source_configs") \
                .update({"last_verified_at": now_iso}) \
                .in_("id", successful_source_ids) \
                .execute()
            log.info("stamped last_verified_at on %d source(s)", len(successful_source_ids))
        except Exception as e:  # noqa: BLE001
            log.warning("last_verified_at stamp failed: %s", e)

    # index page
    if len(results) > 1:
        idx = out_dir / "index.html"
        idx.write_text(_render_index(results), encoding="utf-8")
        print(f"\n✓ index: {idx}")
    for name, _r, path in results:
        print(f"  · {name:<50}  {path}")

    if args.upload:
        try:
            from .supabase_io import client
            sb = client()
            for path in [p for _n, _r, p in results] + [out_dir / "index.html"]:
                if not path.exists(): continue
                key = f"verify/{ts}/{path.name}"
                sb.storage.from_("redesign-daily-content").upload(
                    key, path.read_bytes(),
                    file_options={"content-type": "text/html", "upsert": "true"},
                )
                pub = sb.storage.from_("redesign-daily-content").get_public_url(key).rstrip("?")
                print(f"  ↑ {pub}")
        except Exception as e:  # noqa: BLE001
            print(f"  upload failed: {e}", file=sys.stderr)
            sys.exit(3)


if __name__ == "__main__":
    main()
