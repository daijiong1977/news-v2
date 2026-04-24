"""Step 1 — DISCOVER: collect candidates via Tavily + RSS per category."""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

from . import config as cfg
from .cleaner import extract_article_from_html, _score_image_candidate

log = logging.getLogger(__name__)


HTML_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 news-v2-bot (+https://vocabpalace.6ray.com)",
}
HTML_FETCH_TIMEOUT = 15


def _fetch_article_html(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
                         allow_redirects=True)
        if r.status_code >= 400:
            log.info("HTML fetch %s -> %d", url, r.status_code)
            return None
        ct = r.headers.get("Content-Type", "").lower()
        if "html" not in ct and ct:
            log.info("HTML fetch %s -> non-html (%s)", url, ct)
            return None
        return r.text
    except requests.RequestException as e:
        log.info("HTML fetch failed %s: %s", url, e)
        return None


def _host_is_trusted(img_url: str | None) -> bool:
    if not img_url:
        return False
    try:
        host = urlparse(img_url).netloc.lower()
    except Exception:
        return False
    return any(h in host for h in cfg.TRUSTED_IMAGE_HOSTS)


def _sha1_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _source_name_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return url


def _looks_like_article_url(url: str | None) -> bool:
    """Heuristic: reject homepage / index / archive / social-media pages.

    Real article URLs have paths with enough non-slash characters for a slug
    (typically 15+) AND contain a hyphen or a digit (slug markers or article IDs).
    Homepages, index pages, and social-media profile pages have neither.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    path = parsed.path or ""
    # Blacklist obvious non-article domains
    host = (parsed.netloc or "").lower()
    for bad_host in (
        "facebook.com", "instagram.com", "twitter.com", "x.com",
        "tiktok.com", "youtube.com", "vimeo.com", "pinterest.com",
        "mcsweeneys.net", "theonion.com", "dailymash.co.uk", "babylonbee.com",  # NEW: satire
    ):
        if bad_host in host:
            return False
    # Deals/shopping hosts — reject entirely (see Fix 3)
    for shop_host in cfg.SHOPPING_HOSTS:
        if shop_host in host:
            return False
    # Shopping/deals path segments on known sites
    lower_path = path.lower()
    for shop_path in cfg.SHOPPING_PATH_MARKERS:
        if shop_path in lower_path:
            return False
    # Path must have enough content for a slug
    chars = sum(1 for ch in path if ch != "/")
    if chars < 15:
        return False
    # Real article URLs nearly always have a hyphen (slug) or a digit (article ID).
    # Index pages usually don't: /sports, /news, /experiments, /kids.
    if "-" not in path and "_" not in path and not any(ch.isdigit() for ch in path):
        return False
    # Reject common index-page tails
    lower = path.rstrip("/").lower()
    bad_tails = ("/news", "/archive", "/home", "/stories", "/search", "/category",
                 "/articles", "/topics", "/tag", "/experiments", "/sports")
    if any(lower.endswith(t) for t in bad_tails):
        return False
    return True


def _looks_like_video_article(url: str | None, title: str | None, raw_content: str | None) -> bool:
    """Detect video-first articles whose text body is essentially player chrome.

    Criteria (any one):
      - URL path contains /video/, /videos/, /watch/, /live/, /podcast/
      - Title starts with 'Video:' or 'Watch:'
      - After a rough clean, raw_content word count < 300 AND contains
        repeated video-player markers (LIVE, WATCH, Video Player, UP NEXT, NOW PLAYING)
    """
    if url:
        try:
            path = urlparse(url).path.lower()
        except Exception:
            path = ""
        for marker in ("/video/", "/videos/", "/videonews/", "/watch/", "/live/", "/podcast/"):
            if marker in path:
                return True
    if title:
        t = title.strip().lower()
        if t.startswith("video:") or t.startswith("watch:"):
            return True
    if raw_content:
        words = raw_content.split()
        if len(words) < 300:
            blob = raw_content
            markers = ("LIVE", "WATCH", "Video Player", "UP NEXT", "NOW PLAYING")
            hits = sum(blob.count(m) for m in markers)
            if hits >= 3:
                return True
    return False


def _looks_like_advertisement(url: str | None, title: str | None) -> bool:
    """Detect deals/shopping/listicle content that should be rejected at discovery."""
    title_l = (title or "").lower()
    ad_phrases = (
        "top deals", "best deals", "on sale", "% off",
        "discount", "buy now", "shop these", "our favorite",
        "must-have", "best products", "best gifts",
        "saved countless meltdowns",
    )
    for phrase in ad_phrases:
        if phrase in title_l:
            return True
    if url:
        try:
            host = urlparse(url).netloc.lower()
            path = urlparse(url).path.lower()
        except Exception:
            host, path = "", ""
        for shop_host in cfg.SHOPPING_HOSTS:
            if shop_host in host:
                return True
        for shop_path in cfg.SHOPPING_PATH_MARKERS:
            if shop_path in path:
                return True
    return False


def _image_url_passes_static_filter(url: str | None) -> bool:
    if not url:
        return False
    low = url.lower()
    if any(bad in low for bad in cfg.IMAGE_URL_BLACKLIST):
        return False
    if any(low.split("?", 1)[0].endswith(ext) for ext in cfg.IMAGE_EXT_BLACKLIST):
        return False
    return True


def image_head_check(url: str | None, retries: int = 1) -> bool:
    """HEAD-check an image URL. Returns True if passes, False otherwise.

    Applies URL substring + extension filter, then HEAD request with timeout.
    Rejects 4xx/5xx, timeouts, or Content-Length < 20KB (if Content-Length given).
    """
    if not _image_url_passes_static_filter(url):
        return False
    assert url is not None
    attempt = 0
    while attempt <= retries:
        try:
            r = requests.head(
                url,
                timeout=cfg.IMAGE_HEAD_TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": "kidsnews-v2-pipeline/0.1"},
            )
            if r.status_code >= 400:
                return False
            cl = r.headers.get("Content-Length")
            if cl is not None:
                try:
                    if int(cl) < cfg.IMAGE_MIN_BYTES:
                        return False
                except ValueError:
                    pass
            return True
        except requests.RequestException:
            attempt += 1
    return False


# ---------------------------------------------------------------------------
# Tavily lane
# ---------------------------------------------------------------------------


def tavily_search(
    query: str,
    api_key: str,
    max_results: int = cfg.TAVILY_MAX_RESULTS,
    include_domains: list[str] | None = None,
) -> dict:
    payload = {
        "api_key": api_key,
        "query": query,
        "topic": "news",               # bias toward news articles, not general web homepages
        "days": 3,                     # only content from last 3 days (prevents evergreen pages)
        "search_depth": "advanced",
        "include_raw_content": True,
        "include_images": True,
        "include_image_descriptions": True,  # get per-image descriptions for matching
        "max_results": max_results,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    r = requests.post(cfg.TAVILY_ENDPOINT, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()


_STOPWORDS = {
    "news", "the", "and", "for", "with", "from", "this", "that", "about",
    "says", "will", "their", "have", "into", "after", "over", "more",
    "than", "also", "been", "what", "when", "were", "they", "your",
    "out", "but", "has", "its", "who", "how", "why", "among", "per",
    "org", "com", "reports", "report", "year", "week", "update", "story",
    "new", "first", "just", "now", "today", "could", "would", "should",
    "said", "being", "going", "while", "here", "there",
}


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    out: set[str] = set()
    for w in text.split():
        w2 = w.lower().strip(".,!?:;()[]\"'-–—")
        if len(w2) > 3 and w2 not in _STOPWORDS:
            out.add(w2)
    return out


def _score_image_desc_match(
    desc: str, title: str, snippet: str
) -> tuple[int, int]:
    """Return (title_overlap, snippet_overlap) counts."""
    desc_t = _tokenize(desc)
    if not desc_t:
        return (0, 0)
    title_t = _tokenize(title)
    snippet_t = _tokenize(snippet)
    return (len(desc_t & title_t), len(desc_t & snippet_t))


def _match_image_to_article(
    article_title: str,
    article_snippet: str,
    images_pool: list[dict],
    used: set[str],
    min_overlap: int = 2,
) -> tuple[str | None, str | None]:
    """Pick the image whose description has strong overlap with title or snippet.

    Returns (image_url, match_source) where match_source is "description_match"
    or None. NEVER falls back to "first unused image" — better to return None
    than assign a mismatched image.

    Requires title-overlap >= min_overlap OR snippet-overlap >= min_overlap.
    """
    best_url: str | None = None
    best_combined = 0
    for img in images_pool:
        url = img.get("url") if isinstance(img, dict) else img
        if not url or url in used:
            continue
        desc = (img.get("description") or "") if isinstance(img, dict) else ""
        t_ov, s_ov = _score_image_desc_match(desc, article_title, article_snippet)
        if t_ov < min_overlap and s_ov < min_overlap:
            continue
        # Score: heavily weight title overlap, lightly weight snippet overlap.
        combined = (t_ov * 3) + s_ov
        if combined > best_combined:
            best_combined, best_url = combined, url
    if best_url:
        return best_url, "description_match"
    return None, None


def _build_candidate_from_tavily(
    result: dict,
    images_pool: list[dict],
    used_images: set[str],
    rank: int,
    discovery_lane: str = "new_pipeline",
    discovery_group: str | None = None,
) -> dict | None:
    url = result.get("url")
    title = result.get("title") or ""
    snippet = (result.get("content") or "").strip()
    raw_content = result.get("raw_content")
    if not url or not title:
        return None

    # Strict image matching: no "first unused" fallback. If no image meets the
    # title/snippet word-overlap bar, leave image_url null.
    image_url: str | None = None
    image_passed = False
    image_match_source: str | None = None

    tried: set[str] = set()
    for _ in range(3):  # up to 3 attempts: re-pick next-best after HEAD failures
        candidate, match_source = _match_image_to_article(
            title, snippet, images_pool, used_images | tried
        )
        if not candidate:
            break
        tried.add(candidate)
        if _host_is_trusted(candidate):
            image_url = candidate
            image_passed = True
            image_match_source = match_source
            used_images.add(candidate)
            break
        if image_head_check(candidate):
            image_url = candidate
            image_passed = True
            image_match_source = match_source
            used_images.add(candidate)
            break
        # HEAD failed — do NOT fall back to random image; continue trying
        # next-best matching image.
        continue

    cand = {
        "id": _sha1_id(url),
        "discovery_lane": discovery_lane,
        "discovery_group": discovery_group,
        "source_name": _source_name_from_url(url),
        "source_url": url,
        "title": title.strip(),
        "snippet": snippet[:500] if snippet else "",
        "raw_content": raw_content,
        "read_method": "tavily" if (raw_content and len(raw_content) >= cfg.JINA_MIN_CONTENT_LEN) else None,
        "image_url": image_url,
        "image_filter_passed": image_passed,
        "image_match_source": image_match_source,
        "vetter_score": None,
        "vetter_verdict": None,
        "vetter_flags": [],
        "vetter_payload": None,
        "vetter_notes": "",
        "discovered_rank": rank,
        "vetted_rank": None,
        "tavily_score": result.get("score", 0) or 0,
    }
    return cand


def discover_tavily(
    query: str,
    api_key: str,
    target: int,
    include_domains: list[str] | None = None,
    max_results: int | None = None,
    discovery_lane: str = "new_pipeline",
    discovery_group: str | None = None,
) -> tuple[list[dict], int]:
    """Returns (candidates, api_call_count)."""
    try:
        data = tavily_search(
            query,
            api_key,
            max_results=max_results or cfg.TAVILY_MAX_RESULTS,
            include_domains=include_domains,
        )
    except Exception as e:
        log.warning("Tavily search failed for %r: %s", query, e)
        return [], 1

    results = data.get("results", []) or []
    images_pool_raw = data.get("images", []) or []
    # Normalize each image entry to a dict with {url, description}.
    # Tavily can return either bare strings (legacy) or {url, description} dicts.
    images_pool: list[dict] = []
    for img in images_pool_raw:
        if isinstance(img, str):
            if img:
                images_pool.append({"url": img, "description": ""})
        elif isinstance(img, dict):
            u = img.get("url") or img.get("image")
            if u:
                images_pool.append({"url": u, "description": img.get("description") or ""})

    cands: list[dict] = []
    seen_urls: set[str] = set()
    used_images: set[str] = set()
    for res in results:
        if len(cands) >= target:
            break
        url = res.get("url")
        title = res.get("title") or ""
        raw_content = res.get("raw_content") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if not _looks_like_article_url(url):
            log.info("skipping non-article URL: %s", url)
            continue
        if _looks_like_advertisement(url, title):
            log.info("skipping advertisement/deals listicle: %s | %s", url, title[:80])
            continue
        if _looks_like_video_article(url, title, raw_content):
            log.info("skipping video article: %s | %s", url, title[:80])
            continue
        c = _build_candidate_from_tavily(
            res, images_pool, used_images, rank=len(cands) + 1,
            discovery_lane=discovery_lane,
            discovery_group=discovery_group,
        )
        if c:
            cands.append(c)
    return cands, 1


# ---------------------------------------------------------------------------
# RSS lane
# ---------------------------------------------------------------------------


def _extract_rss_image(entry: Any) -> str | None:
    # media_thumbnail / media_content
    for key in ("media_thumbnail", "media_content"):
        val = entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
        if val:
            try:
                first = val[0]
                url = first.get("url") if isinstance(first, dict) else None
                if url:
                    return url
            except Exception:
                pass
    # enclosures
    for enc in (entry.get("enclosures") if isinstance(entry, dict) else getattr(entry, "enclosures", []) or []):
        url = enc.get("href") or enc.get("url") if isinstance(enc, dict) else None
        if url:
            return url
    # links array
    for link in (entry.get("links") if isinstance(entry, dict) else getattr(entry, "links", []) or []):
        if isinstance(link, dict) and link.get("type", "").startswith("image/"):
            return link.get("href")
    return None


def _build_candidate_from_rss(entry: Any, source_name: str, rank: int) -> dict | None:
    url = entry.get("link") if isinstance(entry, dict) else getattr(entry, "link", None)
    title = entry.get("title") if isinstance(entry, dict) else getattr(entry, "title", None)
    if not url or not title:
        return None
    summary = entry.get("summary") if isinstance(entry, dict) else getattr(entry, "summary", "") or ""
    # strip html tags from summary
    snippet = re.sub(r"<[^>]+>", " ", summary or "")
    snippet = re.sub(r"\s+", " ", snippet).strip()[:500]

    rss_seed_image = _extract_rss_image(entry)

    # --- Fetch the article HTML and run clean extraction (v1 logic) ---
    raw_content: str | None = None
    read_method: str | None = None
    og_image: str | None = None

    html_text = _fetch_article_html(url)
    if html_text:
        try:
            extracted = extract_article_from_html(url, html_text)
            og_image = extracted.get("og_image")
            cleaned_body = extracted.get("cleaned_body") or ""
            if cleaned_body and len(cleaned_body) >= 200:
                raw_content = cleaned_body
                read_method = "html_scrape"
        except Exception as e:
            log.info("extract_article_from_html failed for %s: %s", url, e)

    # Pick best image: prefer og:image (scored), else RSS-seed image
    image_url: str | None = None
    image_filter_passed = False
    candidates: list[str] = []
    if og_image:
        candidates.append(og_image)
    if rss_seed_image and rss_seed_image not in candidates:
        candidates.append(rss_seed_image)
    # Score and pick best
    if candidates:
        scored = sorted(candidates, key=lambda u: _score_image_candidate(u, url), reverse=True)
        best = scored[0]
        if best:
            # Trust known hosts without HEAD check; else HEAD-check
            if _host_is_trusted(best):
                image_url = best
                image_filter_passed = True
            elif _image_url_passes_static_filter(best):
                if image_head_check(best):
                    image_url = best
                    image_filter_passed = True
                else:
                    image_url = best
                    image_filter_passed = False
            else:
                image_url = None

    # snippet fallback: if snippet empty (or thin) and we have cleaned body, use its head
    if (not snippet or len(snippet) < 60) and raw_content:
        snippet = raw_content[:500].replace("\n", " ")

    return {
        "id": _sha1_id(url),
        "discovery_lane": "rss",
        "discovery_group": "C",
        "source_name": source_name,
        "source_url": url,
        "title": title.strip(),
        "snippet": snippet,
        "raw_content": raw_content,
        "read_method": read_method,
        "image_url": image_url,
        "_rss_seed_image": rss_seed_image,
        "_og_image": og_image,
        "image_filter_passed": image_filter_passed,
        "vetter_score": None,
        "vetter_verdict": None,
        "vetter_flags": [],
        "vetter_payload": None,
        "vetter_notes": "",
        "discovered_rank": rank,
        "vetted_rank": None,
        "tavily_score": 0,
    }


def discover_rss(feed_url: str, source_name: str, target: int) -> list[dict]:
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as e:
        log.warning("feedparser failed for %s: %s", feed_url, e)
        return []

    entries = getattr(parsed, "entries", []) or []
    cands: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if len(cands) >= target:
            break
        link = entry.get("link") if isinstance(entry, dict) else getattr(entry, "link", None)
        if not link or link in seen:
            continue
        seen.add(link)
        c = _build_candidate_from_rss(entry, source_name, rank=len(cands) + 1)
        if c:
            cands.append(c)
    return cands


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def discover_category(category: str, tavily_api_key: str) -> tuple[list[dict], dict]:
    """Returns (candidates_in_discovery_order, meta).

    meta includes api_call_counts and the query used.
    """
    weekday = datetime.now(timezone.utc).weekday()

    if category == "News":
        return _discover_news_3lane(tavily_api_key)
    elif category == "Science":
        topic, query = cfg.SCIENCE_ROTATION[weekday]
    elif category == "Fun":
        topic, query = cfg.FUN_ROTATION[weekday]
    else:
        raise ValueError(f"Unknown category {category!r}")

    rss_info = cfg.RSS_FEEDS[category]
    tavily_target = cfg.TAVILY_TARGETS.get(category, cfg.TAVILY_TARGET)
    rss_target = cfg.RSS_TARGETS.get(category, rss_info.get("target", 3))

    tavily_calls = 0
    tav_cands, n = discover_tavily(query, tavily_api_key, target=tavily_target)
    tavily_calls += n

    rss_cands = discover_rss(rss_info["url"], rss_info["source_name"], target=rss_target)

    # Merge + dedup by URL (within-run)
    seen: set[str] = set()
    merged: list[dict] = []
    for c in tav_cands + rss_cands:
        if c["source_url"] in seen:
            continue
        seen.add(c["source_url"])
        merged.append(c)

    # Re-number discovered_rank in final merge order (Tavily first, then RSS)
    for i, c in enumerate(merged, 1):
        c["discovered_rank"] = i

    meta = {
        "query": query,
        "topic": topic,
        "tavily_api_calls": tavily_calls,
        "tavily_count": len([c for c in merged if c["discovery_lane"] == "new_pipeline"]),
        "rss_count": len([c for c in merged if c["discovery_lane"] == "rss"]),
    }
    return merged, meta


def _discover_news_3lane(tavily_api_key: str) -> tuple[list[dict], dict]:
    """News-only 3-lane discovery.

    Group A (Tier 1): Tavily include_domains=[npr.org, reuters.com], max_results=5
    Group B (Tier 2): Tavily include_domains=[apnews.com, bbc.com, theguardian.com], max_results=5
    Group C (RSS):    PBS NewsHour RSS, up to 5

    All filters (URL-shape / video / ad) applied in discover_tavily.
    Dedup by URL across all 3 lanes.
    """
    query = cfg.NEWS_CURATOR_QUERY
    topic = cfg.NEWS_TOPIC

    tavily_calls = 0

    # Group A — Tier 1
    tier1_cands, n = discover_tavily(
        query,
        tavily_api_key,
        target=cfg.NEWS_LANE_MAX_RESULTS,
        include_domains=cfg.NEWS_TIER1_DOMAINS,
        max_results=cfg.NEWS_LANE_MAX_RESULTS,
        discovery_lane="tavily_tier1",
        discovery_group="A",
    )
    tavily_calls += n

    # Group B — Tier 2
    tier2_cands, n = discover_tavily(
        query,
        tavily_api_key,
        target=cfg.NEWS_LANE_MAX_RESULTS,
        include_domains=cfg.NEWS_TIER2_DOMAINS,
        max_results=cfg.NEWS_LANE_MAX_RESULTS,
        discovery_lane="tavily_tier2",
        discovery_group="B",
    )
    tavily_calls += n

    # Group C — PBS RSS
    rss_info = cfg.RSS_FEEDS["News"]
    rss_target = cfg.NEWS_LANE_MAX_RESULTS
    rss_cands = discover_rss(rss_info["url"], rss_info["source_name"], target=rss_target)
    # Force group C (discover_rss already sets it; belt-and-suspenders)
    for c in rss_cands:
        c["discovery_group"] = "C"
        c["discovery_lane"] = "rss"

    # Dedup across all 3 lanes by URL
    seen: set[str] = set()
    merged: list[dict] = []
    for c in tier1_cands + tier2_cands + rss_cands:
        if c["source_url"] in seen:
            continue
        seen.add(c["source_url"])
        merged.append(c)

    for i, c in enumerate(merged, 1):
        c["discovered_rank"] = i

    meta = {
        "query": query,
        "topic": topic,
        "tavily_api_calls": tavily_calls,
        "tavily_count": len([c for c in merged if c.get("discovery_lane", "").startswith("tavily")]),
        "rss_count": len([c for c in merged if c.get("discovery_lane") == "rss"]),
        "group_counts": {
            "A": len([c for c in merged if c.get("discovery_group") == "A"]),
            "B": len([c for c in merged if c.get("discovery_group") == "B"]),
            "C": len([c for c in merged if c.get("discovery_group") == "C"]),
        },
    }
    return merged, meta
