"""Content cleaning utilities ported from v1 `news/mining/data_collector.py`.

Exposes:
  - clean_paragraphs(paragraphs) -> list[str]: remove bylines/promo/boilerplate.
  - _score_image_candidate(img_url, article_url) -> float: image scoring heuristic.
  - extract_article_from_html(url, html_text) -> dict: {og_image, paragraphs, cleaned_body}.
"""
from __future__ import annotations

import html
import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


# Query params used by publisher CMSes (IEEE Spectrum, Squarespace, Imgix-style)
# to pre-crop og:image to a 2:1 social-share banner. Stripping them yields
# the natural-aspect source image — heads/feet stop getting chopped off.
_BANNER_CROP_PARAMS = {"coordinates", "rect", "crop"}


# ---------------------------------------------------------------------------
# Thresholds (formerly from thresholds.json in v1)
# ---------------------------------------------------------------------------

PARAGRAPH_MIN_LENGTH = 30


# ---------------------------------------------------------------------------
# Aggressive cleaner patterns (News-redesign)
# ---------------------------------------------------------------------------

# AI authoring disclaimer (italic paragraph mentioning AI + Gannett/USAToday/ethics)
AI_DISCLAIMER_SIGNALS = (
    "with the assistance of Artificial Intelligence",
    "with the assistance of artificial intelligence",
    "assisted by AI",
    "AI-generated",
    "cm.usatoday.com/ethical-conduct",
    "ethical-conduct",
    "Gannett",
    "gannett",
)

# social-share line (Facebook/Twitter/Email as lone paragraph)
SOCIAL_SHARE_RE = re.compile(
    r"^\s*(\[Facebook\]\([^)]+\)|\[Twitter\]\([^)]+\)|\[X\]\([^)]+\)|Email|\[Email\]\([^)]+\))"
    r"([\s,]+(\[Facebook\]\([^)]+\)|\[Twitter\]\([^)]+\)|\[X\]\([^)]+\)|Email|\[Email\]\([^)]+\)))*\s*$"
)

# "More info/information ... available at [X.org](...)" end-of-article promo
MORE_INFO_RE = re.compile(
    r"^\s*More\s+information\s+.*\savailable\s+at\s+\[",
    re.I,
)

# Byline email tags "[name@domain.com](...)"
EMAIL_LINK_RE = re.compile(
    r"\[[^@\]]+@[^@\]]+\.[a-z]{2,}\]\([^)]+\)",
    re.I,
)

# Newser calendar widget "[img](url) Apr 2026 [img](url)"
CALENDAR_RE = re.compile(
    r"\[\s*(?:Image|!?\[[^\]]*\])[\s\S]*?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}",
    re.I,
)


# ---------------------------------------------------------------------------
# Image candidate scoring (ported verbatim from v1)
# ---------------------------------------------------------------------------


def _score_image_candidate(img_url: str | None, article_url: str) -> float:
    """Return a score for an image candidate to prefer large/original media-host images.

    Heuristics (v1):
      - prefer known media hosts (ichef.bbci.co.uk, bbci.co.uk)
      - prefer URLs with '/standard/<width>/' or '/branded_sport/<width>/'
        and larger widths
      - prefer same-origin images (domain contains article domain)
      - prefer webp/jpg over png placeholders
      - penalize logo/favicon/placeholder/spacer paths
    """
    score = 0.0
    if not img_url:
        return score
    try:
        p = urlparse(img_url)
        host = p.netloc or ""
        path = p.path or ""
    except Exception:
        return score

    if "ichef.bbci.co.uk" in host or "bbci.co.uk" in host:
        score += 10000.0

    try:
        art_host = urlparse(article_url).netloc or ""
        if art_host and art_host in host:
            score += 2000.0
    except Exception:
        pass

    m = re.search(r"/standard/(\d+)", path)
    if not m:
        m = re.search(r"/branded_sport/(\d+)", path)
    if m:
        try:
            w = float(m.group(1))
            score += w
        except Exception:
            pass

    if path.endswith(".webp"):
        score += 50.0
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        score += 30.0

    low = (host + path).lower()
    if any(x in low for x in (
        "logo", "favicon", "apple-touch-icon", "/icons/",
        "placeholder", "spacer", "blank",
    )):
        score -= 5000.0

    return score


# ---------------------------------------------------------------------------
# clean_paragraphs (ported from v1)
# ---------------------------------------------------------------------------


def clean_paragraphs(paragraphs: Iterable[str]) -> list[str]:
    """Clean and filter paragraphs - remove bylines, feedback prompts, promo lines, etc."""
    TRIM_PREFIXES = (
        "Read More:", "READ MORE:",
        "Watch:", "WATCH:",
        "Notice:", "NOTICE:",
    )
    TRIM_CONTAINS = (
        "Support trusted journalism",
        "Support Provided By:",
        "Subscribe to Here's the Deal",
    )
    ASCII_REPLACEMENTS = {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        " ": " ",
    }

    BYLINE_NAMES = {
        "Nick Schifrin", "Sonia Kopelev", "Geoff Bennett", "Amna Nawaz",
        "Stephanie Kotuby", "Alexa Gold", "Jonah Anderson", "Ismael M. Belkoura",
        "Amalia Hout-Marchand", "Leonardo Pini", "Athan Yanos",
    }

    cleaned: list[str] = []
    for raw in paragraphs:
        if raw is None:
            continue
        text = html.unescape(str(raw).strip())
        for src, dst in ASCII_REPLACEMENTS.items():
            text = text.replace(src, dst)
        text = text.replace("\r", "")

        if not text:
            continue

        # Aggressive cleaner patterns (News-redesign)
        # Drop AI-authoring disclaimer paragraphs.
        if any(sig in text for sig in AI_DISCLAIMER_SIGNALS):
            continue
        # Drop social-share lone-paragraph lines.
        if SOCIAL_SHARE_RE.match(text):
            continue
        # Drop "More information available at [...]" end-of-article promos.
        if MORE_INFO_RE.match(text):
            continue
        # Drop Newser-style calendar/image widgets.
        if CALENDAR_RE.search(text):
            continue
        # Strip in-line byline email tags from otherwise-keepable paragraphs.
        text = EMAIL_LINK_RE.sub("", text).strip()
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        stripped = text.strip()
        parts = stripped.split()

        # Duplicated name like "Nick Schifrin Nick Schifrin"
        if len(parts) == 2 and parts[0] == parts[1]:
            continue

        # Duplicated-byline pattern: "Foo Bar, Baz Foo Bar, Baz" (string == s+" "+s)
        is_duplicated_byline = False
        if len(stripped) < 120:
            half = len(stripped) // 2
            mid_candidates = [
                i for i in range(max(1, half - 4), min(len(stripped), half + 5))
                if stripped[i:i + 1] == " "
            ]
            for mid in mid_candidates:
                a = stripped[:mid].strip()
                b = stripped[mid:].strip()
                if a and a == b:
                    is_duplicated_byline = True
                    break
        if is_duplicated_byline:
            continue

        if stripped in BYLINE_NAMES:
            continue

        if len(parts) <= 3 and stripped.endswith(":"):
            name_part = stripped[:-1].strip()
            if name_part in BYLINE_NAMES:
                continue

        # Skip all-caps short text (like bylines)
        upper_count = sum(1 for ch in text if ch.isupper())
        lower_count = sum(1 for ch in text if ch.islower())
        if upper_count and not lower_count and len(text.split()) <= 6:
            continue

        # Very short proper-case 2-word phrase: likely byline
        if len(parts) <= 3 and all(w[0].isupper() for w in parts if len(w) > 0):
            if len(parts) <= 2 and len(text) < 40:
                continue

        if text.lower() == "leave your feedback":
            continue

        if any(text.startswith(prefix) for prefix in TRIM_PREFIXES):
            continue

        if any(needle in text for needle in TRIM_CONTAINS):
            continue

        if text.startswith("You must confirm your public display name"):
            continue
        if text.startswith("Follow TechRadar") or "Follow TechRadar" in text:
            continue

        if text.startswith("Funding:") or text.startswith("Funding -"):
            continue

        AD_REMOVE_CONTAINS = (
            "techradar",
            "sign up for",
            "sign up",
            "sign in",
            "log in",
            "login",
            "log out",
            "logout",
            "read our full guide",
            "you must confirm your public display name",
            "follow techradar",
            "vpn",
            "nordvpn",
            "sponsored",
            "affiliate",
            "affiliate commission",
            "buy now",
            "get the world",
        )
        low_text = text.lower()

        promo_emojis_start = ("✅", "🔒", "🔥", "⭐", "✨", "💥", "🚨", "🎉")
        if text.lstrip().startswith(promo_emojis_start) and len(text) < 220:
            continue
        # Short emoji-marked lines
        if len(text) < 120 and any(ch in text for ch in promo_emojis_start):
            continue

        if (
            "%" in text
            or " off" in low_text
            or "70% off" in low_text
            or "save" in low_text
            or "discount" in low_text
        ):
            if len(text) < 220 or any(ch in text for ch in promo_emojis_start):
                continue

        if re.search(
            r"\b(subscription|subscribe|monthly|per month|per year|set you back|"
            r"add to your TV package|\$\d|£\d|AU\$|CAN\$|\d+% off)\b",
            low_text,
        ):
            if len(text) < 300:
                continue

        if any(k in low_text for k in AD_REMOVE_CONTAINS):
            continue

        if stripped.lower().startswith("related:"):
            continue

        if len(text) < PARAGRAPH_MIN_LENGTH:
            continue

        if cleaned and text == cleaned[-1]:
            continue

        # Drop sentences mentioning specific source tokens
        SOURCE_TOKENS = [
            "bbc", "ars technica", "the street", "science daily",
            "techradar", "pbs", "new york times", "nyt",
        ]
        sentence_parts = re.split(r"(?<=[\.\?!])\s+", text)
        kept_parts = []
        low_tokens = [t.lower() for t in SOURCE_TOKENS]
        for part in sentence_parts:
            lp = part.lower()
            if any(tok in lp for tok in low_tokens):
                continue
            kept_parts.append(part)

        if not kept_parts:
            continue
        text = " ".join(kept_parts).strip()

        cleaned.append(text)

    # Strip trailing footer-ish lines
    while cleaned:
        last = cleaned[-1]
        low_last = last.lower()
        if (
            "©" in last
            or "future us" in low_last
            or re.search(r"\b\d{5}\b", low_last)
            or ("full" in low_last and "floor" in low_last)
        ):
            cleaned.pop()
            continue
        if len(last.split()) < 10 and re.search(r"\d", last) and "," in last:
            cleaned.pop()
            continue
        break

    return cleaned


# ---------------------------------------------------------------------------
# HTML article extraction
# ---------------------------------------------------------------------------


def _choose_best_from_srcset(srcset: str | None) -> str | None:
    if not srcset:
        return None
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    best_url = None
    best_val = -1.0
    for part in parts:
        segs = part.split()
        url = segs[0]
        val = 0.0
        if len(segs) > 1:
            desc = segs[1]
            try:
                if desc.endswith("w"):
                    val = float(desc[:-1])
                elif desc.endswith("x"):
                    val = float(desc[:-1]) * 1000.0
                else:
                    val = float(desc)
            except Exception:
                val = 0.0
        if val > best_val:
            best_val = val
            best_url = url
    return best_url


def _strip_banner_crop_params(url: str) -> str:
    """Strip publisher CMS pre-crop directives from an og:image URL.

    IEEE Spectrum, Squarespace and Imgix-style URLs include query params
    (`coordinates=`, `rect=`, `crop=`) that pre-crop the source image to a
    2:1 social-share banner — frequently chopping heads/feet from portraits.
    Removing these returns the natural-aspect original.
    """
    if not url or "?" not in url:
        return url
    try:
        parts = urlparse(url)
        kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                if k.lower() not in _BANNER_CROP_PARAMS]
        new_query = urlencode(kept)
        return urlunparse(parts._replace(query=new_query))
    except Exception:
        return url


def _extract_og_image(soup: BeautifulSoup) -> str | None:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return _strip_banner_crop_params(og.get("content"))
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return _strip_banner_crop_params(tw.get("content"))
    link_img = soup.find("link", rel=lambda x: x and "image_src" in x)
    if link_img and link_img.get("href"):
        return _strip_banner_crop_params(link_img.get("href"))
    return None


def _extract_paragraphs_from_soup(soup: BeautifulSoup) -> list[str]:
    # Remove scripts/styles/noscript only. Do NOT decompose <nav>, <form>,
    # or <aside> — some CMSes (e.g. PBS NewsHour) nest the <article> inside
    # these containers, and killing them would wipe out the body.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Try article > p first, fall back to all p
    ps: list = []
    containers = soup.select(
        "article p, main p, div.article p, div[role='main'] p, "
        "div.body-text p, div.post-body p, div.entry-content p, "
        "div.article-body p, div.articleBody p, div.content p"
    )
    if len(containers) >= 3:
        ps = containers
    else:
        ps = soup.find_all("p")

    raw = []
    for p in ps:
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        text = re.sub(r"\s+", " ", text).strip()
        if text and len(text) > 10:
            raw.append(text)
    return raw


def extract_article_from_html(url: str, html_text: str) -> dict:
    """Parse HTML -> {og_image, paragraphs (cleaned list), cleaned_body (joined str)}."""
    result = {"og_image": None, "paragraphs": [], "cleaned_body": ""}
    if not html_text:
        return result
    try:
        soup = BeautifulSoup(html_text, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
        except Exception:
            return result

    og = _extract_og_image(soup)
    if og:
        try:
            result["og_image"] = urljoin(url, og)
        except Exception:
            result["og_image"] = og

    raw_paragraphs = _extract_paragraphs_from_soup(soup)

    # Skip first couple paragraphs that are very short (byline territory) in v1 style
    content_start = 0
    for i, p in enumerate(raw_paragraphs):
        if len(p) > 50:
            content_start = i
            break
    filtered = raw_paragraphs[content_start:]

    cleaned = clean_paragraphs(filtered)
    # Cap to first ~20 paragraphs to keep size sane
    if len(cleaned) > 20:
        cleaned = cleaned[:20]

    result["paragraphs"] = cleaned
    result["cleaned_body"] = "\n\n".join(cleaned)
    return result
