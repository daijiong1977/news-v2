"""Article URL discovery for sources of various shapes.

Three feed kinds are supported. All three return a uniform
list[dict] of `{url, title, description}` so downstream code (the
verifier, daily_verify) doesn't care which shape the source has.

  feed_kind='rss'        — XML RSS/Atom feed at rss_url.
                           No feed_config needed.
  feed_kind='sitemap'    — sitemap.xml at rss_url. feed_config:
                             { "subsitemap_filter": "posts-post",  # which sub-sitemap to follow if
                                                                   #   the root is a sitemapindex
                                                                   #   (default: pick first)
                               "url_filter": "/articles/",         # regex; only keep urlset URLs matching
                                                                   #   (default: keep all)
                               "max_items": 50,                    # how many sitemap entries to consider
                             }
  feed_kind='html_list'  — HTML listing page at rss_url. feed_config:
                             { "article_selector": "article h2 a",  # CSS selector for <a> elements
                               "title_selector":   "h2",            # optional: extract title from
                                                                    #   the matched element
                               "exclude_pattern":  "/category/|/tag/",
                             }

Constraint (per project rule): scraping uses Python libs only — NO LLM.

Public entry point:

    discover_article_urls(source: dict, top_n: int = 5) -> list[dict]
        # source is a row from candidates table (dict-like).
        # Returns up to top_n items, newest-first when known.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

UA_DEFAULT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
UA_FIREFOX = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0"
)
UA = UA_DEFAULT  # back-compat
TIMEOUT = 20
ATOM_NS = "{http://www.w3.org/2005/Atom}"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

# Per project rule: if a fetch can't succeed within ~60s after trying 2-3
# common workarounds (UA cycling + retry on transient errors), give up.
TOTAL_BUDGET_SEC = 60


def _fetch_once(url: str, ua: str, timeout: int) -> tuple[str, str, str]:
    req = Request(url, headers={
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/rss+xml,"
            "application/atom+xml,application/xml,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=timeout) as r:
        body = r.read()
        for enc in ("utf-8", "latin-1"):
            try:
                return body.decode(enc), r.headers.get("Content-Type", ""), r.url
            except UnicodeDecodeError:
                continue
        return body.decode("utf-8", errors="replace"), r.headers.get("Content-Type", ""), r.url


def _fetch(url: str, timeout: int = TIMEOUT) -> tuple[str, str, str]:
    """Fetch URL with retry policy: try default UA, then Googlebot, then Firefox.

    Total budget ~60s. Retries cover 403 (WAF rate-limit), timeouts, and
    transient connection errors. Persistent 404 (real bad URL) does NOT retry.
    """
    import time
    deadline = time.time() + TOTAL_BUDGET_SEC
    last_err: Exception | None = None
    for attempt, ua in enumerate([UA_DEFAULT, UA_GOOGLEBOT, UA_FIREFOX], 1):
        if time.time() >= deadline:
            break
        try:
            return _fetch_once(url, ua, min(timeout, max(2, int(deadline - time.time()))))
        except HTTPError as e:
            last_err = e
            if e.code in (404, 410, 451):
                # Real "not there" — UA won't help.
                raise
            # 403 / 429 / 5xx — back off briefly then try next UA
            time.sleep(min(3, max(1, deadline - time.time() - 1)))
        except (URLError, TimeoutError, OSError) as e:
            last_err = e
            time.sleep(min(2, max(1, deadline - time.time() - 1)))
    if last_err:
        raise last_err
    raise RuntimeError("fetch budget exhausted with no specific error")


# ── RSS / Atom ──────────────────────────────────────────────────────

def _from_rss(rss_url: str, top_n: int) -> list[dict]:
    text, _, _ = _fetch(rss_url)
    text = text.lstrip("﻿")
    items: list[dict] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise RuntimeError(f"RSS parse error: {e}") from None

    # RSS 2.0 <item>
    for it in root.iter("item"):
        l = it.find("link"); t = it.find("title"); d = it.find("description")
        link = (l.text or "").strip() if l is not None and l.text else ""
        title = (t.text or "").strip() if t is not None and t.text else ""
        desc = (d.text or "").strip() if d is not None and d.text else ""
        if link:
            items.append({"url": link, "title": title, "description": desc})

    # Atom <entry>
    if not items:
        for entry in root.iter(f"{ATOM_NS}entry"):
            link = ""
            for le in entry.findall(f"{ATOM_NS}link"):
                if (le.get("rel") or "alternate") == "alternate" and le.get("href"):
                    link = le.get("href").strip(); break
            if not link:
                le = entry.find(f"{ATOM_NS}link")
                if le is not None and le.get("href"):
                    link = le.get("href").strip()
            t = entry.find(f"{ATOM_NS}title")
            title = (t.text or "").strip() if t is not None and t.text else ""
            desc = ""
            for tag in (f"{ATOM_NS}summary", f"{ATOM_NS}content"):
                el = entry.find(tag)
                if el is not None and el.text:
                    desc = el.text.strip(); break
            if link:
                items.append({"url": link, "title": title, "description": desc})

    return items[:top_n]


# ── sitemap.xml ─────────────────────────────────────────────────────

def _from_sitemap(
    sitemap_url: str,
    url_filter: str | None,
    subsitemap_filter: str | None,
    max_items: int,
    top_n: int,
) -> list[dict]:
    text, _, _ = _fetch(sitemap_url)
    text = text.lstrip("﻿")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise RuntimeError(f"sitemap parse error: {e}") from None

    # If this is a sitemapindex, follow ONE sub-sitemap (chosen by subsitemap_filter,
    # else the first). Inside that sub-sitemap we still apply url_filter at the
    # urlset level — these two filters are separate concerns and were tangled
    # together in the previous version.
    if root.tag == f"{SITEMAP_NS}sitemapindex":
        sub = [el for el in root.findall(f"{SITEMAP_NS}sitemap/{SITEMAP_NS}loc") if el.text]
        urls = [el.text.strip() for el in sub]
        chosen = None
        if subsitemap_filter:
            for u in urls:
                if subsitemap_filter in u:
                    chosen = u; break
        if not chosen and urls:
            chosen = urls[0]
        if chosen:
            return _from_sitemap(chosen, url_filter, subsitemap_filter, max_items, top_n)
        raise RuntimeError("sitemapindex with no usable sub-sitemap")

    # urlset — apply url_filter (if any) only here.
    items: list[dict] = []
    pat = re.compile(url_filter) if url_filter else None
    for url_el in root.iter(f"{SITEMAP_NS}url"):
        loc_el = url_el.find(f"{SITEMAP_NS}loc")
        last_el = url_el.find(f"{SITEMAP_NS}lastmod")
        if loc_el is None or not loc_el.text:
            continue
        u = loc_el.text.strip()
        if pat and not pat.search(u):
            continue
        items.append({
            "url": u,
            "title": "",  # sitemaps don't carry titles
            "description": "",
            "lastmod": last_el.text.strip() if last_el is not None and last_el.text else "",
        })
        if len(items) >= max_items:
            break

    # newest-first if lastmod present (most sites populate it)
    items.sort(key=lambda x: x.get("lastmod") or "", reverse=True)
    return items[:top_n]


# ── HTML listing page ──────────────────────────────────────────────

def _from_html_list(
    list_url: str,
    article_selector: str,
    title_selector: str | None,
    exclude_pattern: str | None,
    top_n: int,
) -> list[dict]:
    text, _, final_url = _fetch(list_url)
    soup = BeautifulSoup(text, "lxml")

    excl = re.compile(exclude_pattern) if exclude_pattern else None
    seen: set[str] = set()
    items: list[dict] = []

    for el in soup.select(article_selector):
        # If selector targets <a>, that's the link element; otherwise, find <a> inside.
        anchor = el if el.name == "a" else el.find("a")
        if not anchor or not anchor.get("href"):
            continue

        url = urljoin(final_url, anchor["href"].strip())
        if url in seen:
            continue
        if excl and excl.search(url):
            continue
        # filter out fragments and same-page anchors
        if url.startswith("javascript:") or "#" == urlparse(url).fragment[:1]:
            continue
        # only keep same-host links by default (publisher-internal articles)
        if urlparse(url).netloc and urlparse(url).netloc != urlparse(final_url).netloc:
            continue

        # Title extraction
        title = ""
        if title_selector:
            t_el = el.select_one(title_selector) or anchor
            title = t_el.get_text(" ", strip=True)
        else:
            title = anchor.get_text(" ", strip=True) or anchor.get("title", "")
        title = re.sub(r"\s+", " ", title).strip()[:200]

        seen.add(url)
        items.append({"url": url, "title": title, "description": ""})
        if len(items) >= top_n * 3:  # collect extra in case some are duplicates / filtered later
            break

    return items[:top_n]


# ── Public entry point ─────────────────────────────────────────────

def discover_article_urls(source: dict, top_n: int = 5) -> list[dict]:
    """Dispatch to the right shape implementation based on source['feed_kind']."""
    kind = (source.get("feed_kind") or "rss").lower()
    cfg_raw = source.get("feed_config") or "{}"
    cfg: dict[str, Any] = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
    primary_url = source.get("rss_url")

    if kind == "rss":
        return _from_rss(primary_url, top_n)

    if kind == "sitemap":
        return _from_sitemap(
            primary_url,
            cfg.get("url_filter"),
            cfg.get("subsitemap_filter"),
            cfg.get("max_items", 200),
            top_n,
        )

    if kind == "html_list":
        return _from_html_list(
            primary_url,
            cfg["article_selector"],
            cfg.get("title_selector"),
            cfg.get("exclude_pattern"),
            top_n,
        )

    raise ValueError(f"unknown feed_kind: {kind!r}")


__all__ = ["discover_article_urls"]
