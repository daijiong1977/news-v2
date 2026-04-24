"""Step 3 — READ: get full article text for SAFE/CAUTION survivors."""
from __future__ import annotations

import logging
import os
import re
from typing import Iterable

import requests

from . import config as cfg
from .cleaner import clean_paragraphs, extract_article_from_html
from .discover import (
    _fetch_article_html,
    _image_url_passes_static_filter,
    image_head_check,
)

log = logging.getLogger(__name__)


def tavily_extract(url: str, api_key: str) -> str | None:
    """Call Tavily /extract and return cleaner markdown raw_content for the URL.
    Returns None on failure or missing content.
    """
    body = {
        "api_key": api_key,
        "urls": [url],
        "format": "markdown",
        "extract_depth": "advanced",
        "include_images": True,
    }
    try:
        r = requests.post(
            cfg.TAVILY_EXTRACT_ENDPOINT,
            json=body,
            timeout=cfg.TAVILY_EXTRACT_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.info("tavily /extract failed for %s: %s", url, e)
        return None
    results = data.get("results") or []
    if not results:
        failed = data.get("failed_results") or []
        if failed:
            log.info("tavily /extract failed_results for %s: %s", url, failed[:1])
        return None
    rc = results[0].get("raw_content")
    if not rc:
        return None
    return rc


MARKDOWN_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def extract_markdown_images(markdown: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for m in MARKDOWN_IMG_RE.finditer(markdown or ""):
        u = m.group(1).strip()
        u = u.split(" ", 1)[0]
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def fetch_jina(url: str, jina_api_key: str | None) -> str:
    headers = {"Accept": "text/plain", "User-Agent": "kidsnews-v2-pipeline/0.1"}
    if jina_api_key:
        headers["Authorization"] = f"Bearer {jina_api_key}"
    full_url = cfg.JINA_ENDPOINT + url
    r = requests.get(full_url, headers=headers, timeout=cfg.JINA_TIMEOUT)
    r.raise_for_status()
    return r.text


def _pick_image_for_rss(markdown: str) -> tuple[str | None, bool]:
    """From Jina markdown, return (first_image_url_passing_full_check, passed_bool)."""
    for img in extract_markdown_images(markdown):
        if image_head_check(img):
            return img, True
    for img in extract_markdown_images(markdown):
        if _image_url_passes_static_filter(img):
            return img, False
    return None, False


def _word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


_MD_LINK_ONLY_RE = re.compile(r"^\s*[\*\-+\d.]*\s*\[[^\]]*\]\([^)]+\)\s*$")
_MD_IMG_ONLY_RE = re.compile(r"^\s*\!?\[[^\]]*\]\([^)]+\)\s*[\*\-]?\s*$")
# Line made entirely of image-link markdown concatenated (e.g. `[![img](u)](u)![img](u)`).
# Matches any mix of `[![..](..)](..)`, bare `![..](..)`, and `[..](..)` repeated.
# URL body: anything except `)`, plus one level of nested parens, plus quoted
# title strings like `(url "some title")`.
_URL_INNER = r"(?:[^)]|\([^)]*\))*"
_MD_CONCAT_IMGLINK_RE = re.compile(
    r"^\s*(?:"
    rf"\[\!\[[^\]]*\]\({_URL_INNER}\)\]\({_URL_INNER}\)"   # [![img](u)](u)
    rf"|\!\[[^\]]*\]\({_URL_INNER}\)"                     # ![img](u)
    rf"|\[[^\]]*\]\({_URL_INNER}\)"                       # [text](u) — stray text links
    r"\s*)+\s*$"
)
_MD_NAV_MARKER_RE = re.compile(r"^\s*\*\s+\[")
_MD_HR_RE = re.compile(r"^\s*[-*_]{3,}\s*$")


def _prefilter_markdown_lines(text: str) -> str:
    """Drop markdown chrome lines (nav links, image-only lines, horizontal rules).

    Leaves paragraphs intact; converts runs of dropped lines into a blank line
    so clean_paragraphs' \\n\\n-splitting still works.
    """
    kept: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            kept.append("")
            continue
        if _MD_HR_RE.match(line):
            kept.append("")
            continue
        # Nav markers: "* [Label](url)" or "- [Label](url)" or "1. [Label](url)"
        if _MD_NAV_MARKER_RE.match(line):
            kept.append("")
            continue
        if _MD_LINK_ONLY_RE.match(line):
            kept.append("")
            continue
        if _MD_IMG_ONLY_RE.match(line):
            kept.append("")
            continue
        if _MD_CONCAT_IMGLINK_RE.match(line):
            kept.append("")
            continue
        # Numbered list with a link only
        if re.match(r"^\s*\d+\.\s*\[[^\]]+\]\([^)]+\)\s*$", line):
            kept.append("")
            continue
        kept.append(line)
    # Collapse 3+ consecutive blanks to one
    out: list[str] = []
    last_blank = False
    for l in kept:
        if not l.strip():
            if not last_blank:
                out.append("")
            last_blank = True
        else:
            out.append(l)
            last_blank = False
    return "\n".join(out)


def _clean_wrap(text: str | None) -> str:
    """Run clean_paragraphs over text split on double newlines (fallback: single).

    For markdown-formatted input (common with Tavily /extract), first strip
    navigation-link-only lines and image-only lines so paragraphs collapse
    into proper \\n\\n-separated blocks.
    """
    if not text:
        return ""
    # Pre-filter: remove markdown chrome lines
    filtered = _prefilter_markdown_lines(text)
    if "\n\n" in filtered:
        paras = filtered.split("\n\n")
    else:
        paras = filtered.split("\n")
    # Collapse intra-paragraph newlines to single space so clean_paragraphs
    # sees one logical paragraph per item.
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in paras]
    cleaned = clean_paragraphs(paras)
    return "\n\n".join(cleaned)


def _best_cleaned(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """Given a list of (method_label, raw_text) tuples, run clean_paragraphs
    on each and return (best_method, best_cleaned_text) — the one with the
    most words after cleaning. Returns ("none", "") if nothing.
    """
    best_method = "none"
    best_text = ""
    best_wc = 0
    for method, raw in candidates:
        if not raw:
            continue
        cleaned = _clean_wrap(raw)
        wc = _word_count(cleaned)
        if wc > best_wc:
            best_wc = wc
            best_text = cleaned
            best_method = method
    return best_method, best_text


def _read_news_candidate(cand: dict, tavily_api_key: str | None) -> tuple[int, bool]:
    """News-lane reader: Tavily-only with HTML-scrape fallback. No Jina.

    For Tavily-lane candidates, also call /extract and keep whichever produces
    more clean words. Returns (tavily_extract_calls, keep_bool).
    """
    raw = cand.get("raw_content") or ""
    method = cand.get("read_method")
    lane = cand.get("discovery_lane")
    calls = 0

    # 1) RSS candidates: apply clean_paragraphs over the existing scrape, then a
    # second pass on top. Sufficient text threshold applies.
    if lane == "rss" and method == "html_scrape" and raw:
        cleaned_once = _clean_wrap(raw)
        cleaned_twice = _clean_wrap(cleaned_once)
        final = cleaned_twice or cleaned_once
        if _word_count(final) >= cfg.TAVILY_CONTENT_MIN_WORDS // 3:
            cand["raw_content"] = final
            cand["read_method"] = "html_scrape"
            return calls, True
        # fall through to html_scrape retry

    # 2) Tavily lane: try /extract and compare against the existing raw_content.
    if lane in ("new_pipeline", "tavily_tier1", "tavily_tier2"):
        candidates_pool: list[tuple[str, str]] = []
        if raw:
            candidates_pool.append(("tavily", raw))
        url = cand.get("source_url")
        if url and tavily_api_key:
            extract_rc = tavily_extract(url, tavily_api_key)
            calls += 1
            if extract_rc:
                candidates_pool.append(("tavily_extract", extract_rc))
        best_method, best_text = _best_cleaned(candidates_pool)
        if best_text and _word_count(best_text) >= cfg.TAVILY_CONTENT_MIN_WORDS // 3:
            cand["raw_content"] = best_text
            cand["read_method"] = best_method
            return calls, True
        # fall through to HTML-scrape

    # 3) RSS fallback / final fallback: HTML scrape directly from article URL
    url = cand.get("source_url")
    if url:
        html_text = _fetch_article_html(url)
        if html_text:
            try:
                extracted = extract_article_from_html(url, html_text)
                body = extracted.get("cleaned_body") or ""
                body = _clean_wrap(body)  # double-pass clean
                if body and _word_count(body) >= cfg.TAVILY_CONTENT_MIN_WORDS // 3:
                    cand["raw_content"] = body
                    cand["read_method"] = "html_scrape"
                    if not cand.get("image_url") and extracted.get("og_image"):
                        cand["image_url"] = extracted["og_image"]
                        cand["image_filter_passed"] = False
                    return calls, True
            except Exception as e:
                log.info("html_scrape extract failed for %s: %s", url, e)

    # 4) Neither Tavily nor HTML scrape produced enough content — DROP.
    cand["read_method"] = "insufficient_content"
    log.info("DROP News candidate (insufficient content): %s", url)
    return calls, False


def _read_general_candidate(
    cand: dict, jina_api_key: str | None, tavily_api_key: str | None
) -> tuple[int, int]:
    """Non-News-lane reader: Tavily/extract preferred, Jina fallback, snippet last.

    Returns (jina_calls, tavily_extract_calls).
    """
    raw = cand.get("raw_content") or ""
    jina_calls = 0
    tav_calls = 0

    # RSS lane with html_scrape content — apply double clean pass; also try
    # tavily_extract as an alternative and keep whichever has more words.
    if cand["discovery_lane"] == "rss" and raw and cand.get("read_method") == "html_scrape":
        cleaned_twice = _clean_wrap(_clean_wrap(raw))
        pool: list[tuple[str, str]] = [("html_scrape", cleaned_twice)]
        best_method, best_text = _best_cleaned([("html_scrape", cleaned_twice)])
        # Apply whatever double-cleaned result we have
        if best_text:
            cand["raw_content"] = best_text
            cand["read_method"] = "html_scrape"
        else:
            cand["raw_content"] = cleaned_twice
        return jina_calls, tav_calls

    # Tavily lane: always try /extract and compare.
    if cand["discovery_lane"] in ("new_pipeline", "tavily_tier1", "tavily_tier2"):
        pool2: list[tuple[str, str]] = []
        if raw:
            pool2.append(("tavily", raw))
        url = cand.get("source_url")
        if url and tavily_api_key:
            extract_rc = tavily_extract(url, tavily_api_key)
            tav_calls += 1
            if extract_rc:
                pool2.append(("tavily_extract", extract_rc))
        best_method, best_text = _best_cleaned(pool2)
        if best_text and _word_count(best_text) >= 120:
            cand["raw_content"] = best_text
            cand["read_method"] = best_method
            return jina_calls, tav_calls
        # else fall through to Jina

    # Jina fallback for anything insufficient
    if not raw or len(raw) < cfg.JINA_MIN_CONTENT_LEN:
        try:
            text = fetch_jina(cand["source_url"], jina_api_key)
            jina_calls += 1
            cand["raw_content"] = _clean_wrap(_clean_wrap(text))
            cand["read_method"] = "jina"
            if cand["discovery_lane"] == "rss" and not cand.get("image_url"):
                img, passed = _pick_image_for_rss(text)
                if img:
                    cand["image_url"] = img
                    cand["image_filter_passed"] = passed
        except Exception as e:
            log.warning("Jina failed for %s: %s", cand["source_url"], e)
            cand["raw_content"] = cand.get("snippet") or ""
            cand["read_method"] = "snippet_only"
    else:
        cand["raw_content"] = _clean_wrap(_clean_wrap(raw))
        cand["read_method"] = "tavily"

    return jina_calls, tav_calls


def read_candidate(
    cand: dict,
    jina_api_key: str | None,
    tavily_api_key: str | None,
    category: str,
) -> tuple[int, int, bool]:
    """Populates raw_content / read_method / image_url in-place.

    Returns (jina_calls, tavily_extract_calls, keep_candidate_bool).
    """
    if cand["vetter_verdict"] not in {"SAFE", "CAUTION"}:
        return 0, 0, True

    if category in cfg.SKIP_JINA_CATEGORIES:
        tav_calls, keep = _read_news_candidate(cand, tavily_api_key)
        return 0, tav_calls, keep

    jina_calls, tav_calls = _read_general_candidate(cand, jina_api_key, tavily_api_key)
    return jina_calls, tav_calls, True


def read_candidates(
    candidates: Iterable[dict],
    jina_api_key: str | None,
    category: str,
    tavily_api_key: str | None = None,
) -> tuple[int, int, list[dict]]:
    """Returns (total_jina_calls, total_tavily_extract_calls, kept_candidates)."""
    total_jina = 0
    total_tav = 0
    kept: list[dict] = []
    for c in candidates:
        jc, tc, keep = read_candidate(c, jina_api_key, tavily_api_key, category)
        total_jina += jc
        total_tav += tc
        if keep:
            kept.append(c)
        else:
            log.info("dropping candidate id=%s (%s)", c.get("id"), c.get("source_url"))
    return total_jina, total_tav, kept
