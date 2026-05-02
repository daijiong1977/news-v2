"""Shared core for RSS → filter → batched vet+cluster → batched rewrite.

Used by news_aj_full.py and news_pbs_full.py. Parameterized by:
  - RSS URL
  - source label (for HTML title)
  - MAX_KEPT (cap on articles sent to vetter)
  - PICK_COUNT (how many the curator picks)
  - TARGET_WORDS (kids article length)
  - output filenames

Vet thresholds (locked 2026-04-23):
  - REJECT if any dim >= 4 OR total > 6
  - CAUTION if total 5-6 AND every dim <= 3
  - SAFE if total 0-4 AND every dim <= 3
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

from .cleaner import extract_article_from_html
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


log = logging.getLogger("rss-core")

# Load .env once on module import
_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

# Default model for the env-fallback path. The DB-driven provider lookup
# (db_config.select_provider) is the primary path; these defaults apply
# only when the redesign_ai_providers table is empty/unavailable.
DEEPSEEK_MODEL_CHAT = os.environ.get("DEEPSEEK_MODEL_CHAT", "deepseek-v4-flash")
DEEPSEEK_MODEL_REASONER = os.environ.get("DEEPSEEK_MODEL_REASONER", "deepseek-v4-flash")


# Provider resolution — module-level cache; populated lazily on first
# use. To force a fresh lookup (e.g. between admin edits), call
# `pipeline.db_config.reset_caches()`.
_resolved_chat: tuple[str, str, str] | None = None       # (api_key, endpoint, model)
_resolved_reasoner: tuple[str, str, str] | None = None


def _provider_to_tuple(p) -> tuple[str, str, str]:
    """Provider → (api_key, endpoint, model). Endpoint = base_url + /chat/completions."""
    return (p.api_key, p.base_url + "/chat/completions", p.model_id)


def _resolve_chat_provider() -> tuple[str, str, str]:
    """Pick the chat-side provider once, cache. Roles: rewriter > any.
    Falls back to env-var DeepSeek if the table is empty or lookup fails."""
    global _resolved_chat
    if _resolved_chat is not None:
        return _resolved_chat
    try:
        from .db_config import select_provider
        p = select_provider("rewriter") or select_provider("any")
        if p:
            _resolved_chat = _provider_to_tuple(p)
            log.info("chat provider: %s (%s) via DB", p.name, p.model_id)
            return _resolved_chat
    except Exception as e:  # noqa: BLE001
        log.warning("chat provider DB lookup failed (%s); using env defaults", e)
    if not DEEPSEEK_KEY:
        raise RuntimeError("no chat provider available — DB has none and DEEPSEEK_API_KEY is unset")
    _resolved_chat = (DEEPSEEK_KEY, DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL_CHAT)
    return _resolved_chat


def _resolve_reasoner_provider() -> tuple[str, str, str]:
    """Pick the reasoner-side provider. Roles: enricher > curator > any."""
    global _resolved_reasoner
    if _resolved_reasoner is not None:
        return _resolved_reasoner
    try:
        from .db_config import select_provider
        p = select_provider("enricher") or select_provider("curator") or select_provider("any")
        if p:
            _resolved_reasoner = _provider_to_tuple(p)
            log.info("reasoner provider: %s (%s) via DB", p.name, p.model_id)
            return _resolved_reasoner
    except Exception as e:  # noqa: BLE001
        log.warning("reasoner provider DB lookup failed (%s); using env defaults", e)
    if not DEEPSEEK_KEY:
        raise RuntimeError("no reasoner provider available — DB has none and DEEPSEEK_API_KEY is unset")
    _resolved_reasoner = (DEEPSEEK_KEY, DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL_REASONER)
    return _resolved_reasoner


def reset_provider_resolution() -> None:
    """Invalidate the cached provider tuples — used between pipeline runs
    if the admin edited the registry mid-process. Most pipeline runs are
    one-shot so this is rarely needed."""
    global _resolved_chat, _resolved_reasoner
    _resolved_chat = None
    _resolved_reasoner = None

MIN_WORDS_DEFAULT = 500
MAX_RSS_DEFAULT = 25
VIDEO_PATH_RE = re.compile(r"/video/", re.I)
HTML_FETCH_TIMEOUT = 15
HTML_FETCH_HEADERS = {
    # Real browser UA — NPR and some others block bot-flavored UAs.
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SAFETY_DIMS = ["violence", "sexual", "substance", "language", "fear",
               "adult_themes", "distress", "bias"]
SAFETY_SHORT = ["Viol", "Sex", "Subst", "Lang", "Fear", "Adult", "Distr", "Bias"]

# Generic social-share default images (usually a site logo or blank template,
# not a real article image). Detected by URL substring.
BAD_IMAGE_PATTERNS = (
    "facebook-default",
    "twitter-default",
    "og-default",
    "share-default",
    "default-share",
    "default-og",
    "default-social",
)

MIN_PICK_BODY_WORDS = 250   # fall back to alternate if pick's body is thinner than this


def is_generic_social_image(url: str | None) -> bool:
    if not url:
        return True
    u = url.lower()
    return any(p in u for p in BAD_IMAGE_PATTERNS)


# ---------------------------------------------------------------------------
# Vet threshold evaluator (Python-side, authoritative)
# ---------------------------------------------------------------------------

def apply_vet_thresholds(safety: dict) -> str:
    """Authoritative verdict from safety scores.

    REJECT if any dim >= 4 OR total > 6.
    CAUTION if total 5-6 AND every dim <= 3.
    SAFE if total 0-4 AND every dim <= 3.
    """
    dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
    total = safety.get("total")
    if total is None:
        total = sum(dims)
    max_dim = max(dims) if dims else 0
    if max_dim >= 4 or total > 6:
        return "REJECT"
    if 5 <= total <= 6:
        return "CAUTION"
    return "SAFE"


# ---------------------------------------------------------------------------
# Step 1+2: RSS + HTML scrape + filter
# ---------------------------------------------------------------------------

MAX_RSS_AGE_DAYS_DEFAULT = 5   # drop entries published > 5 days ago at the
                               # source. Some RSS feeds (especially "trending"
                               # / "popular" lists) silently include weeks-old
                               # articles in their latest feed; without this
                               # filter, stale stories end up in today's
                               # bundle. 5 days (admin choice) trades a small
                               # amount of staleness tolerance for safety
                               # against running out of fresh content from
                               # weekly-publishing sources. See bug record
                               # 2026-05-01-rss-freshness-no-filter.


def _entry_age_days(entry) -> float | None:
    """Return entry age in days from now (UTC). None if no parseable date.

    Tries `published_parsed` (feedparser pre-parsed UTC struct_time) first;
    falls back to RFC 822 parsing of the `published` / `updated` strings.
    Returns None if neither yields a usable datetime — caller MUST treat
    None as 'unknown' (do NOT drop on missing date — that would silently
    eat any feed without proper publish dates)."""
    import calendar
    import time as _time
    parsed = (getattr(entry, "published_parsed", None)
              or getattr(entry, "updated_parsed", None))
    if parsed:
        try:
            ts = calendar.timegm(parsed)   # struct_time → UTC epoch
            return (_time.time() - ts) / 86400.0
        except Exception:
            pass
    pub_str = getattr(entry, "published", "") or getattr(entry, "updated", "")
    if pub_str:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        except Exception:
            pass
    return None


def fetch_rss_entries(url: str, max_entries: int = MAX_RSS_DEFAULT,
                     max_age_days: float = MAX_RSS_AGE_DAYS_DEFAULT) -> list[dict]:
    """Pull recent entries from an RSS feed, dropping any older than
    `max_age_days` from their source publish date.

    Walks the feed in order (most feeds are date-DESC, but we don't rely
    on it). Stops once we've collected `max_entries` fresh entries.
    Entries with no parseable date are KEPT (safer to err on inclusion
    when the source feed doesn't provide dates)."""
    feed = feedparser.parse(url)
    out: list[dict] = []
    dropped_old = 0
    no_date_kept = 0
    for entry in feed.entries:
        if len(out) >= max_entries:
            break
        age = _entry_age_days(entry)
        if age is not None and age > max_age_days:
            dropped_old += 1
            continue
        out.append({
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "summary": getattr(entry, "summary", ""),
        })
        if age is None:
            no_date_kept += 1
    if dropped_old or no_date_kept:
        log.info("rss freshness [%s]: kept=%d (max_age=%sd), dropped_old=%d, no_date_kept=%d",
                 url[:80], len(out), max_age_days, dropped_old, no_date_kept)
    return out


def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=HTML_FETCH_TIMEOUT, headers=HTML_FETCH_HEADERS,
                         allow_redirects=True)
        if r.status_code >= 400:
            return None
        return r.text
    except requests.RequestException:
        return None


def process_entry(entry: dict, min_words: int = MIN_WORDS_DEFAULT) -> dict:
    url = entry["link"]
    if VIDEO_PATH_RE.search(url):
        return {**entry, "og_image": None, "body": "", "word_count": 0,
                "skip_reason": "video URL", "highlights": [], "paragraphs": []}
    html_text = fetch_html(url)
    if not html_text:
        return {**entry, "og_image": None, "body": "", "word_count": 0,
                "skip_reason": "html fetch failed", "highlights": [], "paragraphs": []}
    extracted = extract_article_from_html(url, html_text)
    body = extracted.get("cleaned_body") or ""
    paragraphs = extracted.get("paragraphs") or []
    og_image = extracted.get("og_image")
    wc = len(body.split()) if body else 0
    skip_reason = None
    if wc < min_words:
        skip_reason = f"{wc}w < {min_words}w"
    elif not og_image:
        skip_reason = "no og:image"
    hls = [p for p in paragraphs if len(p.split()) >= 12][:3]
    return {
        **entry,
        "og_image": og_image,
        "body": body,
        "word_count": wc,
        "paragraphs": paragraphs,
        "highlights": hls,
        "skip_reason": skip_reason,
    }


# ---------------------------------------------------------------------------
# Step 3: BATCHED vet+cluster+curate (1 DeepSeek call)
# ---------------------------------------------------------------------------

def build_vet_prompt(pick_count: int) -> str:
    return f"""You are a content reviewer + curator for a kids news site (readers age 12).

You will receive a numbered list of news articles (id 0..N-1), each with title + first paragraphs.

TASK 1 — Vet every article on 8 safety dimensions and 3 interest dimensions.

  Safety (score each 0-5, where 0=none, 5=severe):
    violence, sexual, substance, language, fear, adult_themes, distress, bias
    Compute total = sum of 8 dims.
    Initial safety_verdict (we will re-apply strict thresholds downstream):
      any_dim >= 4 or total > 6  -> REJECT
      total 5-6 (and all dims <= 3) -> CAUTION
      total 0-4 -> SAFE

  Interest (score each 0-5):
    importance  — how globally significant
    fun_factor  — how delightful / surprising / fun
    kid_appeal  — how likely a 12-year-old would want to read this
    interest_peak = max(importance, fun_factor, kid_appeal)
    interest_verdict:
      peak >= 3 -> ENGAGING
      peak == 2 -> MEH
      peak <= 1 -> BORING

TASK 2 — Detect topic clusters.
  A cluster = 2+ articles on the SAME real-world story/topic.
  Give each cluster a short id and theme. Size-3+ clusters are HOT.

TASK 3 — Pick exactly {pick_count} stories for publishing.
  Rules:
    R1: NEVER pick a REJECT (any_dim >= 4 or total > 6).
    R2: Prefer HOT cluster members at SAFE level. CAUTION is acceptable only
        if no SAFE hot-cluster member exists.
    R3: Prefer interest_verdict=ENGAGING. Never pick BORING unless no alternative.
    R4: Diversify — picks should come from DIFFERENT clusters if possible.
    R5: Avoid gossip, obituaries, dry business jargon, sports-results-only.

TASK 4 — List 3-4 RANKED alternates (next-best IDs) in case a pick fails the
  later content-quality check (thin body, missing real image, etc.).
  Do not repeat picks in alternates.

Return ONLY valid JSON (no markdown fences):
{{
  "vet": [
    {{
      "id": 0,
      "safety": {{"violence": 0, "sexual": 0, "substance": 0, "language": 0,
                  "fear": 0, "adult_themes": 0, "distress": 0, "bias": 0,
                  "total": 0, "verdict": "SAFE"}},
      "interest": {{"importance": 0, "fun_factor": 0, "kid_appeal": 0,
                    "peak": 0, "verdict": "ENGAGING"}},
      "cluster_id": "cluster_x",
      "flags": ["..."]
    }},
    ... one per input ...
  ],
  "clusters": [
    {{"id": "cluster_x", "theme": "...", "members": [0,1], "size": 2, "is_hot": false}}
  ],
  "picks": [
    {{"id": 0, "reason": "must cite safety verdict, interest peak, and cluster status"}},
    ... {pick_count} total ...
  ],
  "alternates": [
    {{"id": 7, "reason": "..."}},
    {{"id": 12, "reason": "..."}},
    {{"id": 3, "reason": "..."}}
  ]
}}"""


# Lightweight per-process counters — orchestrator reads these into the
# `telemetry` blob written to redesign_runs. Never gates control flow.
CALL_STATS: dict[str, int] = {
    "chat_calls": 0, "chat_retries": 0, "chat_repaired": 0,
    "reasoner_calls": 0, "reasoner_content_retries": 0,
    "reasoner_transport_retries": 0, "reasoner_repaired": 0,
    "reasoner_truncated": 0,
}


def reset_call_stats() -> None:
    for k in CALL_STATS:
        CALL_STATS[k] = 0


def _retry_sleep_for(err: Exception, attempt: int) -> float:
    """Tiered backoff per failure class:
      · 429 rate limit → honor Retry-After header, fall back to 30s × attempt
      · 5xx server error → exponential 4s/8s/16s
      · network errors (Connection/Timeout) → exponential 4s/8s/16s
      · JSON parse → quick retry 1s/2s (model needs to re-roll, usually works)
    """
    if isinstance(err, requests.HTTPError):
        resp = getattr(err, "response", None)
        status = resp.status_code if resp is not None else 0
        if status == 429:
            ra = (resp.headers.get("Retry-After") if resp is not None else None) or ""
            try:
                wait = float(ra)
            except (TypeError, ValueError):
                wait = 30.0 * attempt
            return min(wait, 120.0)
        if status >= 500:
            return min(4.0 * (2 ** (attempt - 1)), 60.0)
        return 2.0 * attempt  # other 4xx → quick retry
    if isinstance(err, (requests.ConnectionError, requests.Timeout)):
        return min(4.0 * (2 ** (attempt - 1)), 60.0)
    if isinstance(err, json.JSONDecodeError):
        return 1.0 * attempt
    return 2.0 * attempt


def _try_repair_json(text: str) -> tuple[dict | None, str | None]:
    """Best-effort deterministic JSON repair for near-valid output.
    Returns (parsed, repair_kind) or (None, None) if all attempts fail.

    Handles:
      · trailing commas before } or ]
      · Python-style True/False/None
      · single-quoted strings (on top-level structural tokens only)
      · stray content after the closing brace (truncated explanation, etc.)
    Does NOT attempt to recover from `finish_reason: length` truncation —
    callers should detect that separately and split-batch instead.
    """
    if not text:
        return None, None
    # 1) Trailing commas
    candidate = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(candidate), "trailing-commas"
    except json.JSONDecodeError:
        pass
    # 2) Python literals
    candidate2 = candidate.replace(": True", ": true").replace(
        ": False", ": false").replace(": None", ": null")
    try:
        return json.loads(candidate2), "python-literals"
    except json.JSONDecodeError:
        pass
    # 3) Trim trailing junk after the last balanced }
    last = text.rfind("}")
    if last > 0:
        try:
            return json.loads(text[: last + 1]), "trim-trailing-junk"
        except json.JSONDecodeError:
            pass
    return None, None


class DeepSeekResult:
    """Container for a single DeepSeek call's parsed output + metadata."""
    __slots__ = ("parsed", "raw_content", "finish_reason",
                 "parse_error", "repair_kind", "usage")

    def __init__(self, parsed: dict | None, raw_content: str,
                 finish_reason: str, parse_error: Exception | None = None,
                 repair_kind: str | None = None, usage: dict | None = None):
        self.parsed = parsed
        self.raw_content = raw_content
        self.finish_reason = finish_reason
        self.parse_error = parse_error
        self.repair_kind = repair_kind
        self.usage = usage or {}


def _deepseek_post(payload: dict, timeout: int,
                    *, api_key: str | None = None, endpoint: str | None = None) -> DeepSeekResult:
    """Single HTTP call to a DeepSeek-compatible provider. Pass `api_key`
    + `endpoint` to override the env-default DeepSeek; the DB-driven
    callers do this. Raises on bad HTTP status. Returns DeepSeekResult —
    `parsed` is None if JSON parse + repair both fail; callers detect
    truncation via `finish_reason == 'length'`."""
    api_key = api_key or DEEPSEEK_KEY
    endpoint = endpoint or DEEPSEEK_ENDPOINT
    r = requests.post(
        endpoint,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    raw = msg.get("content") or ""
    finish_reason = choice.get("finish_reason") or "unknown"
    usage = body.get("usage") or {}
    cleaned = re.sub(r"^```json\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return DeepSeekResult(parsed, raw, finish_reason, None, None, usage)
    except json.JSONDecodeError as e:
        repaired, kind = _try_repair_json(cleaned)
        if repaired is not None:
            log.info("repaired malformed JSON via %s (finish_reason=%s)",
                     kind, finish_reason)
            return DeepSeekResult(repaired, raw, finish_reason, None, kind, usage)
        return DeepSeekResult(None, raw, finish_reason, e, None, usage)


def _deepseek_call_with_model(model: str, system: str, user: str,
                                max_tokens: int, temperature: float,
                                max_attempts: int, json_mode: bool,
                                api_key: str, endpoint: str) -> dict:
    """Inner loop: max_attempts retries against ONE model. On exhaust
    raises so the caller can fall through to a different model."""
    payload = {
        "model": model,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            res = _deepseek_post(payload, timeout=120, api_key=api_key, endpoint=endpoint)
            if res.parsed is not None:
                if res.repair_kind:
                    CALL_STATS["chat_repaired"] += 1
                return res.parsed
            if res.finish_reason == "length":
                raise RuntimeError(
                    f"chat output truncated (max_tokens={max_tokens} hit); "
                    "repair failed — caller should reduce payload"
                )
            last_err = res.parse_error or json.JSONDecodeError("repair failed", "", 0)
            CALL_STATS["chat_retries"] += 1
            # Log the raw content snippet so we can see what the model
            # actually emitted. Without this, "JSON parse failed" is
            # an opaque signal — we can't tell if the model returned
            # markdown-wrapped JSON, prose-then-JSON, Python literals,
            # truncated mid-string, etc.
            raw = res.raw_content or ""
            head = raw[:300].replace("\n", "\\n")
            tail = raw[-200:].replace("\n", "\\n") if len(raw) > 500 else ""
            log.warning("chat attempt %d/%d on %s: JSON parse failed (finish=%s, len=%d)",
                        attempt, max_attempts, model, res.finish_reason, len(raw))
            log.warning("  raw[:300] = %r", head)
            if tail:
                log.warning("  raw[-200:] = %r", tail)
            if attempt < max_attempts:
                time.sleep(_retry_sleep_for(last_err, attempt))
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            last_err = e
            CALL_STATS["chat_retries"] += 1
            wait = _retry_sleep_for(e, attempt)
            log.warning("chat attempt %d/%d on %s failed (%s): waiting %.1fs",
                        attempt, max_attempts, model, type(e).__name__, wait)
            if attempt < max_attempts:
                time.sleep(wait)
    raise RuntimeError(f"deepseek_call exhausted {max_attempts} attempts on {model}") from last_err


def deepseek_call(system: str, user: str, max_tokens: int, temperature: float = 0.2,
                  max_attempts: int = 3, json_mode: bool = True) -> dict:
    """Call the active chat provider (resolved from `redesign_ai_providers`,
    falling back to env-var DeepSeek). JSON mode (response_format) on by
    default.

    Aggressive fallback strategy: try the primary model ONCE; if that
    fails (any reason — JSON parse OR network), immediately fall
    through to deepseek-v4-flash with the full max_attempts retry
    budget. Don't waste retries on the primary model — content-shape
    failures from V4 Pro discount on a given prompt tend to be sticky
    (same prompt → same flakiness), so re-retrying same model is
    cargo-cult. Network errors are usually transient enough that
    Flash's first try will catch them too.

    Net behavior:
      - Primary model (Pro): 1 attempt
      - Flash fallback: max_attempts attempts (default 3)

    If the primary IS already Flash, just use full max_attempts on it
    (no fallback-to-self loop)."""
    api_key, endpoint, model = _resolve_chat_provider()
    CALL_STATS["chat_calls"] += 1
    fallback = "deepseek-v4-flash"
    primary_is_flash = "flash" in model.lower()

    if primary_is_flash:
        return _deepseek_call_with_model(model, system, user, max_tokens,
                                           temperature, max_attempts,
                                           json_mode, api_key, endpoint)

    # Primary is non-Flash → ONE attempt, then bail to Flash.
    try:
        return _deepseek_call_with_model(model, system, user, max_tokens,
                                           temperature, max_attempts=1,
                                           json_mode=json_mode,
                                           api_key=api_key, endpoint=endpoint)
    except RuntimeError as primary_err:
        log.warning("primary model %s failed once; switching to %s with %d retries",
                    model, fallback, max_attempts)
        try:
            return _deepseek_call_with_model(fallback, system, user, max_tokens,
                                               temperature, max_attempts,
                                               json_mode, api_key, endpoint)
        except RuntimeError as fallback_err:
            raise RuntimeError(
                f"primary ({model}, 1 try) and fallback ({fallback}, {max_attempts} tries) both failed"
            ) from fallback_err


def vet_curator_input(briefs: list[dict], pick_count: int) -> str:
    lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
             f"Articles to vet + cluster + pick {pick_count}:", ""]
    for i, b in enumerate(briefs):
        hls = b.get("highlights") or []
        hls_text = " ".join(hls)[:400] if hls else (b.get("summary", "") or "")[:400]
        lines.append(f"[id: {i}] {b.get('title','')}")
        lines.append(f"  first paragraphs: {hls_text}")
        lines.append("")
    return "\n".join(lines)


def vet_and_curate(briefs: list[dict], pick_count: int) -> dict:
    result = deepseek_call(build_vet_prompt(pick_count), vet_curator_input(briefs, pick_count),
                           max_tokens=3500, temperature=0.2)
    # Re-apply thresholds authoritatively on Python side
    for v in result.get("vet") or []:
        safety = v.get("safety") or {}
        # Recompute total from dims (trust dim scores, not model's stated total)
        dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
        safety["total"] = sum(dims)
        safety["verdict"] = apply_vet_thresholds(safety)
    # Filter out any picks that are REJECT under the new rule
    vet_by_id = {v["id"]: v for v in result.get("vet") or []}
    filtered_picks = []
    for p in result.get("picks") or []:
        pid = p.get("id")
        v = vet_by_id.get(pid)
        if v and v.get("safety", {}).get("verdict") == "REJECT":
            log.warning("  dropping picked id=%s — REJECT on strict thresholds", pid)
            continue
        filtered_picks.append(p)
    result["picks"] = filtered_picks
    return result


# ---------------------------------------------------------------------------
# Step 4: BATCHED rewrite (1 DeepSeek call)
# ---------------------------------------------------------------------------

def build_rewriter_prompt(pick_count: int, target_words: int) -> str:
    return f"""You are a news writer for "News Oh, Ye!", a news site for 12-year-old readers.

You will receive {pick_count} source articles (with title + full body). Rewrite EACH as a
kid-friendly news story at a 12-year-old / 7th-grade reading level.

WORD COUNT — STRICT:
  Each article's `body` MUST be {target_words - 20}-{target_words + 20} words.
  Count silently before returning; if under, add a concrete example or vivid detail.

READING LEVEL:
  Aim for 12 years old (7th grade). That means:
  · Use real, interesting vocabulary — not baby talk. Words like
    "crucial", "controversial", "ambitious", "negotiation", "historic",
    "escalate", "diplomat", "coalition", "sanction", "evacuate",
    "unprecedented", "stabilize", "devastation" are fair game.
  · The FIRST time you use any specialized term, EXPLAIN it inline in
    plain English:
    "a ceasefire (when both sides agree to stop fighting for a while)"
    "sanctions — rules that block trade and money between countries"
  · Mix sentence lengths: some short and punchy, some longer with clauses.

TONE & STRUCTURE (every article):
  Para 1 — HOOK (surprising detail, vivid scene, or question) + the
           essential WHO, WHAT, WHERE, WHEN in 2-4 sentences.
  Para 2-3 — EXPLAIN the background a 12-year-old needs to understand why.
  Para 4 — PERSPECTIVES: what do different sides think?
  Para 5 — "WHY IT MATTERS": 1-2 sentences connecting to the reader's world.

ACCURACY:
  Every fact MUST come from the source. Don't invent names, dates, numbers.

HEADLINE:
  A NEW kid-friendly headline — different wording from the source.

OUTPUT — valid JSON only (no markdown fences):
{{
  "articles": [
    {{
      "source_id": <int>,
      "headline": "...",
      "body": "paragraph 1\\n\\nparagraph 2\\n\\n...",
      "why_it_matters": "..."
    }},
    ... one per input ...
  ]
}}"""


def rewriter_input(articles_with_ids: list[tuple[int, dict]], target_words: int) -> str:
    lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.", ""]
    for src_id, art in articles_with_ids:
        host = urlparse(art.get("link") or "").netloc.replace("www.", "")
        body = art.get("body") or ""
        words = body.split()
        body_trimmed = " ".join(words[:2500])
        lines.append(f"=== SOURCE [id: {src_id}] ===")
        lines.append(f"Title: {art.get('title','')}")
        lines.append(f"Host: {host}")
        lines.append(f"Date: {art.get('published','')}")
        lines.append("")
        lines.append("Full body:")
        lines.append(body_trimmed)
        lines.append("")
    lines.append(f"Write {len(articles_with_ids)} kids articles. Each body: "
                 f"{target_words - 20}-{target_words + 20} words.")
    return "\n".join(lines)


def rewrite_batch(articles_with_ids: list[tuple[int, dict]], target_words: int) -> dict:
    return deepseek_call(build_rewriter_prompt(len(articles_with_ids), target_words),
                         rewriter_input(articles_with_ids, target_words),
                         max_tokens=3000, temperature=0.5)


# ---------------------------------------------------------------------------
# Tri-variant rewriter (easy_en + middle_en + zh-summary)
# ---------------------------------------------------------------------------

TRI_VARIANT_REWRITER_PROMPT = """You are a 小记者 (junior reporter) at "News Oh, Ye!" — YOU
are a kid yourself, writing for OTHER kids. Your voice is curious, excited, and
engaging — like a smart older sibling who just found a cool story and can't wait
to tell their friends. Don't sound like a grown-up news anchor. NEVER be boring.

What real kid reporters do:
  · Start with a HOOK — a surprising detail, a vivid scene, or a direct
    question to the reader. NEVER open with a dry "who did what" summary.
  · Use "you" to pull the reader in ("Have you ever wondered…?", "Imagine…")
  · Find the WEIRD, COOL, or SURPRISING part of the story and lead with it
  · Use specific details (real numbers, names, places) — concrete beats vague
  · Compare new concepts to things kids already know
    ("about the size of a school bus", "as tall as a 10-story building",
     "that's like filling 50 swimming pools with…")
  · Mix sentence lengths. Short ones for impact. Longer ones for explaining.
  · Show enthusiasm — let the "wow, did you know?!" energy come through

You will receive N source articles. For EACH, produce THREE variants:

1. easy_en — English. READER IS A 10-YEAR-OLD (grade 4).
   · body: 170-210 words (STRICT — count before returning)
   · Simple but not baby-talk; explain any hard word inline in plain English:
     "a ceasefire (when both sides agree to stop fighting for a while)"
   · Short, punchy sentences; lead with a hook — not a summary
   · card_summary: 2-3 sentences, MAX 50 words. Shown on the home-page card
     and inside the pick-3 picker. Opens with a hook, covers WHAT happened
     and to WHOM / WHERE in plain words. Include ONE concrete detail (a
     name, number, or place). NOT a restatement of the headline. Ends with
     punctuation. Stay under 50 words — the kid is scanning, not reading.

2. middle_en — English. READER IS A MIDDLE SCHOOLER (grade 7-8, age 12-14).
   · body: target 320-380 words; HARD MAXIMUM 400 words.
     STRICT — count silently before returning.
     Under 320 → add more vivid details, specific names, or a direct
     quote from the source. NEVER invent.
     Over 380 → trim padding (redundant phrasing, less-essential
     paragraph). Over 400 is unacceptable; cut something rather than
     ship it long. Do NOT cut mid-thought.
   · Richer vocabulary ("crucial", "unprecedented", "diplomat", "negotiation",
     "escalate", "sanction", "controversial", "coalition"); explain inline
     the first time you use a specialized term
   · Mix short impact sentences with longer, complex ones
   · card_summary: 2-3 sentences, MAX 50 words. Shown on the home-page card
     and inside the pick-3 picker. Opens with a hook, covers WHAT happened
     and ONE specific detail (name, number, place, or stake). NOT a
     restatement of the headline. Ends with punctuation. Stay under 50
     words — the middle-schooler is scanning, not reading deeply.

3. zh — 简体中文. 摘要卡片 only (no body, no quiz, no keywords).
   · headline: 有意思的中文标题 (可保留 CEO / iPhone / iPad 等专有名词为英文)
   · summary: 260-300 汉字 (STRICT — count silently, must not exceed 300)
     保持小记者的口吻 — 好奇、生动、抓住读者注意。
     不要写成干巴巴的新闻摘要。用具体细节、用比喻、用提问。

RULES (all variants):
  · ACCURACY — every fact must come from the source. No invented names, dates,
    numbers, or quotes.
  · NEW HEADLINE per variant — don't copy the source headline verbatim.
  · NO dry summary tone — you're a kid reporter excited about a story,
    not a wire-service editor.

POST-WRITE SAFETY SCORING (REQUIRED):
Score the MIDDLE_EN body on 8 safety dimensions. Score CONSERVATIVELY —
better to flag a borderline article than miss something a parent would
object to. Each dim 0-5 (lower=safer). We only score middle_en because
easy_en is a simplified subset (shorter sentences, plainer words, same
facts) so if middle passes, easy is safe by construction. The zh summary
is for parents/grown-ups reading with kids, so safety scoring isn't
applied there.

  Dimensions (score on middle_en body):
    violence       — gory imagery, harm to people/animals
    sexual         — sexual themes, innuendo, explicit references
    substance      — drugs, alcohol, vaping, addiction
    language       — strong / crude / offensive language
    fear           — content that could scare a young reader
    adult_themes   — divorce, infidelity, abuse, financial ruin, death
    distress       — heavy emotional content (grief, despair)
    bias           — unbalanced or one-sided framing

OUTPUT — valid JSON only (no markdown fences):
{
  "articles": [
    {
      "source_id": <int>,
      "easy_en":   {"headline": "...", "card_summary": "...", "body": "..."},
      "middle_en": {"headline": "...", "card_summary": "...", "body": "..."},
      "zh":        {"headline": "...", "summary": "..."},
      "safety":    {"violence":N,"sexual":N,"substance":N,"language":N,
                     "fear":N,"adult_themes":N,"distress":N,"bias":N}
    },
    ... one entry per input article ...
  ]
}"""


# Per-category style guides injected at the top of the rewriter user
# message. Each category has different reading energy: News stays
# factual + concrete; Science leans on analogies and the wow-moment;
# Fun goes playful with more humor and pop-culture-aware framing.
_REWRITE_STYLE_BY_CATEGORY: dict[str, str] = {
    "News": (
        "CATEGORY: News.\n"
        "Voice: a curious kid reporter explaining a current event to friends.\n"
        "Lead with the WHO + WHAT + WHY-IT-MATTERS in the first paragraph,\n"
        "but use a concrete vivid detail to hook (a specific number, place,\n"
        "or quote). Stay neutral — present what each side says without\n"
        "editorializing. Include real names, dates, and places when they\n"
        "appear in the source.\n"
    ),
    "Science": (
        "CATEGORY: Science.\n"
        "Voice: an excited explainer who just learned something cool and\n"
        "wants the reader to GET IT. Lead with the wow-moment (a surprising\n"
        "fact, a counter-intuitive finding). Convert technical terms into\n"
        "everyday analogies — \"the size of a grain of rice\", \"like a\n"
        "1000-piece jigsaw puzzle\". Explain the concept BEFORE introducing\n"
        "the jargon. End with WHY it matters or WHAT comes next.\n"
    ),
    "Fun": (
        "CATEGORY: Fun.\n"
        "Voice: playful, warm, more humor allowed. Focus on the human or\n"
        "animal moment — the surprise, the twist, the underdog. Use vivid\n"
        "verbs and sensory detail (sights, sounds, textures) instead of\n"
        "abstract description. It's OK to be a bit cheeky as long as it\n"
        "stays kind.\n"
    ),
}


def tri_variant_rewriter_input(
    articles_with_ids: list[tuple[int, dict]],
    category: str | None = None,
) -> str:
    n = len(articles_with_ids)
    lines = [f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."]
    if category and category in _REWRITE_STYLE_BY_CATEGORY:
        lines.append("")
        lines.append(_REWRITE_STYLE_BY_CATEGORY[category].rstrip())
        lines.append("")
    lines.append(
        f"You will receive {n} source article{'s' if n != 1 else ''} "
        f"below — all in the {category} category."
        if category else
        f"You will receive {n} source article{'s' if n != 1 else ''} below."
    )
    lines.append("")
    for src_id, art in articles_with_ids:
        host = urlparse(art.get("link") or "").netloc.replace("www.", "")
        body = art.get("body") or ""
        body_trimmed = " ".join(body.split()[:2500])
        lines.append(f"=== SOURCE [id: {src_id}] ===")
        lines.append(f"Title: {art.get('title','')}")
        lines.append(f"Host: {host}")
        lines.append(f"Date: {art.get('published','')}")
        lines.append("")
        lines.append("Full body:")
        lines.append(body_trimmed)
        lines.append("")
    lines.append(f"Write {n} tri-variant entr{'ies' if n != 1 else 'y'} "
                 f"(easy_en + middle_en + zh) — one per source — per the rules.")
    return "\n".join(lines)


def tri_variant_rewrite(
    articles_with_ids: list[tuple[int, dict]],
    category: str | None = None,
) -> dict:
    return deepseek_call(
        TRI_VARIANT_REWRITER_PROMPT,
        tri_variant_rewriter_input(articles_with_ids, category=category),
        max_tokens=8000, temperature=0.5,
    )


# Stage 3 of the mega pipeline: Python-only safety filter on the rewriter's
# self-scored output. Stricter threshold than the source-vet (any_dim ≥ 3
# instead of ≥ 4) because the rewriter has already softened the source
# language for kids — anything still flagged at 3+ is a real concern.
#
# We only check the middle_en safety scores. The rewriter is told to
# produce easy_en as a simplified subset (shorter sentences, plainer
# words, same facts), so if middle passes, easy is safe by construction.
# zh is for adult consumption (parents reading with kids) and not vetted.
STRICT_REJECT_THRESHOLD = 3


def evaluate_rewriter_safety(article_entry: dict) -> dict:
    """For one rewriter output article, returns:
        {"verdict": "PASS"|"REJECT", "reason": "...", "scores": {...}}
    Verdict is determined by middle_en's safety scores (the single
    `safety` field on the article entry). Strict any_dim ≥ 3 → REJECT.
    """
    scores = article_entry.get("safety") or {}
    if not scores:
        return {"verdict": "REJECT",
                "reason": "no safety scores returned",
                "scores": {}}
    max_dim = max(((scores.get(d, 0) or 0) for d in SAFETY_DIMS), default=0)
    total = sum((scores.get(d, 0) or 0) for d in SAFETY_DIMS)
    if max_dim >= STRICT_REJECT_THRESHOLD:
        return {
            "verdict": "REJECT",
            "reason": f"any_dim ≥ {STRICT_REJECT_THRESHOLD} (max={max_dim}, total={total})",
            "scores": scores,
        }
    return {"verdict": "PASS",
            "reason": f"max_dim={max_dim} total={total}",
            "scores": scores}


def filter_safe_rewrites(rewrite_result: dict) -> tuple[list[dict], list[dict]]:
    """Split rewriter articles into (kept, rejected) by Stage 3 safety
    (middle_en scores). Returns articles annotated with `_safety_eval`."""
    kept: list[dict] = []
    rejected: list[dict] = []
    for art in (rewrite_result.get("articles") or []):
        ev = evaluate_rewriter_safety(art)
        ann = {**art, "_safety_eval": ev}
        if ev["verdict"] == "PASS":
            kept.append(ann)
        else:
            log.warning("  Stage 3 REJECT source_id=%s · %s",
                        art.get("source_id"), ev.get("reason", ""))
            rejected.append(ann)
    return kept, rejected


# ---------------------------------------------------------------------------
# Detail enrichment — 1 call per category, 6 items (3 articles × 2 EN variants)
# References bodies by id instead of re-returning them (saves tokens).
# ---------------------------------------------------------------------------

DETAIL_ENRICH_PROMPT = """You are enriching kids-news articles with DEPTH beyond the body text.
Use careful reasoning. The reader already has the body; you're adding what the
body alone doesn't provide — historical context, real-world pattern, nuance.

You will receive N articles (where N is given in the user message; usually 3,
but could be 1, 2, or 3). Each article has two rewritten English bodies:
  easy_en  — grade 4 / 10-year-old reader (~200 words)
  middle_en — grade 7-8 / 12-14 year old reader (~320 words)

For each of the 2N slots (N articles × {easy, middle}) produce:

  [common to both easy and middle]
  · keywords: 6 {term, explanation} pairs. EVERY term MUST literally appear
    (or as a common inflection — "banned" for "ban", "fined" for "fine") in
    the body of THIS SAME slot — do NOT take terms from a neighbouring
    slot's body. If you cannot find 6 difficulty-appropriate terms in
    THIS slot's body, return fewer (4 or 5) — never pad with terms from
    elsewhere. An empty list is acceptable; a misaligned list is NOT.
    DIFFICULTY FILTER:
      easy slot   → only words ABOVE grade-2 vocabulary (words a 10-year-old
                    might not yet know). Skip everyday words like "school",
                    "happy", "money", "team".
      middle slot → only words ABOVE grade-3 / middle-school baseline
                    vocabulary (words a 13-year-old might not know).
                    Skip words a 7th-grader uses without thinking.
    Examples of the bar to clear:
      easy   ✓ "ceasefire", "negotiation", "endangered", "diplomat"
             ✗ "school", "running", "interesting"
      middle ✓ "unprecedented", "coalition", "sanction", "constitutional"
             ✗ "election", "interesting", "important", "decided"
    Each `explanation` is 1 short sentence in plain words a kid that age
    would understand. Do NOT invent concepts that aren't in the text.
  · questions: 6 MCQ questions, each {question, options:[4], correct_answer}.
    correct_answer MUST match one option character-for-character.

  ———— easy slot (10-year-old reader) ————
  · background_read: array of 2-3 SIMPLE sentences giving RELATED real-world
    context. Add historical facts, related events, or concepts the kid might
    not know.
    NAMED-ENTITY INTROS (REQUIRED): if the article names a famous person,
    organization, or location that a 10-year-old might not recognize,
    include a brief 1-clause intro inline. Examples:
      · "President Donald Trump (the U.S. president since 2025)"
      · "the United Nations (a group where almost all countries meet to
        talk about big world problems)"
      · "Gaza (a small piece of land along the Mediterranean Sea)"
    Skip the intro for entities almost any 10-year-old knows (USA, China,
    Apple, Google).
    Avoid generic filler about the news source itself.
  · Article_Structure: array of 4 strings: WHO / WHAT / WHERE / WHY
    (format: "WHO: ...", "WHAT: ...", etc.) — specific answers drawn from the
    body, not a template.
  · why_it_matters: 1 sentence connecting the story to a 10-year-old's life
    (school / family / community / future).
  · perspectives: 2-3 {perspective, description} POV pairs covering clear
    different stances (positive / critical / neutral).

  ———— middle slot (12-14 year old reader) ————
  · background_read: array of 3-5 richer sentences (150-250 words total).
    REQUIRE real historical facts, prior events, or named organizations a
    12-year-old may not know.
    NAMED-ENTITY INTROS (REQUIRED): for prominent people, organizations,
    or locations the article mentions, include a brief context clause —
    role, what they do, why they matter. Examples:
      · "Volodymyr Zelensky (Ukraine's president, in office since 2019)"
      · "the IMF (the International Monetary Fund — a global lender of
        last resort, owned by 190+ countries)"
      · "the West Bank (a Palestinian territory occupied by Israel since
        1967)"
    Skip intros for entities a typical 7th-grader knows (NASA, NATO,
    California). Aim for 2-4 named-entity intros across the
    background_read paragraphs.
    Define new terms briefly when used. No generic statements about
    "this news source" or "how journalists work".
  · Article_Structure: MIND-TREE showing how THIS article is constructed.
    Array of strings, each a tree node. Use tree characters └─ ├─ and leading
    spaces for hierarchy. Example:
      [
        "LEAD: <hook>",
        "  └─ specific: '<quote/detail>'",
        "KEY EVENT: <what happened>",
        "  ├─ WHO: <specific names>",
        "  ├─ WHEN: <timeline>",
        "  └─ AMOUNT: <numbers>",
        "TENSION / VIEWPOINTS",
        "  ├─ ONE SIDE: <viewpoint A>",
        "  └─ OTHER SIDE: <viewpoint B>",
        "EVIDENCE: <support>",
        "OPEN QUESTION: <unresolved>"
      ]
    Reflect the article's ACTUAL structure — don't force a template.
  · why_it_matters: 1-2 sentences on the stakes for a 12-14 year-old — broader
    societal / systemic / future implications, not just personal relevance.
  · perspectives: 4 {perspective, description} pairs, each a DISTINCT angle:
      - Positive (who benefits, what's gained)
      - Negative / critical (who's harmed, what's concerning)
      - Neutral / analytical (systemic or historical pattern)
      - Forward-looking (what next, what could/should change)
    Each description 2-3 sentences exploring tension or nuance.

ACCURACY: facts in background_read must be real-world accurate. If unsure,
prefer pattern statements over specific claims.

REFERENCE, don't re-return: keys are "<i>_easy" / "<i>_middle" where i is the
0-indexed article position. Each article's body is presented in the user
message under its EXACT slot key (e.g. "SLOT KEY: 0_easy"). Generate fields
for each key STRICTLY from THAT key's body — never pull material from a
neighbouring article. The exact set of keys you should produce is given
in the user message — produce ONLY those keys, no more, no less. Do NOT
echo the body text back.

Return ONLY valid JSON (no markdown fences):
{
  "details": {
    "0_easy":   {"keywords":[...], "questions":[...], "background_read":[...], "Article_Structure":[...], "why_it_matters":"...", "perspectives":[...]},
    "0_middle": {...},
    ... (one entry per requested key)
  }
}"""


import re as _re

KEYWORD_SUFFIX_RE = r"(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers|ion|ions|ensions|ensión|ly)?"

# Suffix rewrite rules: (suffix_to_strip, replacement). For each word we
# generate a candidate stem per matching rule and take the union. Two
# words are considered the "same" when their stem sets intersect.
#
# Why rewrite (not just strip): pure stripping cannot collapse pairs
# like `negotiation` and `negotiating`. Stripping `ation` from one and
# `ing` from the other yields `negoti` vs `negotiat` — no match. The
# rule `("ation", "at")` rewrites `negotiation` -> `negotiat`, which
# matches `negotiating` (`ing` -> empty -> `negotiat`).
#
# Order does not matter for correctness (we union all candidates) but
# rules are kept rough longest-first for readability.
_STEM_RULES = (
    # tion-family — collapse to verb-stem
    ("ation", "at"), ("ations", "at"),
    ("ization", "iz"), ("izations", "iz"),
    ("tion", ""), ("tions", ""),
    ("sion", ""), ("sions", ""),
    # acy / atic family — diplomacy / diplomatic -> diplom
    ("acy", ""), ("atic", ""),
    # ical / ic / ively / ive
    ("ically", ""), ("ical", ""),
    ("ively", ""), ("ive", ""),
    ("ic", ""),
    # noun forms
    ("ities", ""), ("ity", ""),
    ("ness", ""),
    ("ments", ""), ("ment", ""),
    ("ship", ""),
    ("ism", ""), ("ists", ""), ("ist", ""),
    # adjective forms
    ("ous", ""), ("ful", ""), ("less", ""),
    ("able", ""), ("ible", ""),
    # comparative / superlative / adverb
    ("iest", "y"), ("ier", "y"),
    ("est", ""), ("ly", ""),
    # plural / verb forms
    ("ies", "y"), ("ied", "y"), ("ying", "y"),
    ("ing", ""), ("ed", ""),
    ("ers", ""), ("er", ""),
    ("ors", ""), ("or", ""),
    ("es", ""), ("s", ""),
    # bare 'e'-drop — turns "negotiate" into "negotiat" so it lines up
    # with "negotiating" (-> "ing" strip -> "negotiat").
    ("e", ""),
)


def _stem_candidates(word):
    """All plausible stems for one word. Lowercase + apply each rule
    once, accumulating candidates. Rejects candidates shorter than 3
    chars to avoid noise."""
    w = word.lower()
    out = {w}
    if len(w) < 4:
        return out
    for suf, rep in _STEM_RULES:
        if w.endswith(suf):
            base = w[: -len(suf)] + rep
            if len(base) >= 3:
                out.add(base)
    return out


def _body_word_stem_index(body):
    """All stem candidates across every alpha word in body."""
    out = set()
    for tok in _re.findall(r"[A-Za-z][A-Za-z'-]+", body):
        out |= _stem_candidates(tok)
    return out


# Word-boundary chars used to avoid embedded-substring false positives
# (so "gas" does not match inside "Vegas").
_NOT_LETTER = r"(?<![A-Za-z])"
_NOT_LETTER_AFTER = r"(?![A-Za-z])"


def _keyword_in_body_with_index(term, body_lc, body_stems):
    """Match using a precomputed lowercased body + stem index. Use this
    when checking many keywords against the same body — saves rebuilding
    the stem index per keyword."""
    if not term or not body_lc:
        return False
    term = term.strip()
    if not term:
        return False
    term_lc = term.lower()

    # Tier 1: boundary-aware exact match.
    if " " in term_lc:
        if term_lc in body_lc:  # phrases imply natural word boundaries
            return True
    else:
        pat = _NOT_LETTER + _re.escape(term_lc) + _NOT_LETTER_AFTER
        if _re.search(pat, body_lc):
            return True

    # Tier 2: legacy suffix regex — catches simple "policy"/"policies"
    # without involving the stem index.
    escaped = _re.escape(term)
    pattern = rf"\b{escaped}{KEYWORD_SUFFIX_RE}\b"
    if _re.search(pattern, body_lc, flags=_re.IGNORECASE):
        return True

    # Tier 3: every term word must share at least one stem candidate
    # with the body's word-stem index.
    term_words = _re.findall(r"[A-Za-z][A-Za-z'-]+", term)
    if not term_words:
        return False
    return all(bool(_stem_candidates(w) & body_stems) for w in term_words)


def keyword_in_body(term, body):
    """One-shot matcher. For batched calls (filter_keywords),
    use `_body_word_stem_index` once and `_keyword_in_body_with_index`
    per keyword instead."""
    if not term or not body:
        return False
    return _keyword_in_body_with_index(
        term, body.lower(), _body_word_stem_index(body)
    )


def filter_keywords(details: dict, rewrite_result: dict) -> dict:
    """Drop keywords that don't appear in the corresponding body. Logs drops.

    Computes the lowercased body and stem index ONCE per slot then
    reuses them across all keywords for that slot — avoids the N-per-
    keyword recomputation Copilot flagged in the 2026-04-29 review.
    """
    articles_by_id = {a["source_id"]: a for a in rewrite_result.get("articles") or []}
    for slot_key, det in details.items():
        kws = det.get("keywords") or []
        if not kws:
            continue
        try:
            aid_str, lvl = slot_key.rsplit("_", 1)
            aid = int(aid_str)
        except (ValueError, TypeError):
            continue
        art = articles_by_id.get(aid, {})
        variant = art.get(f"{lvl}_en" if lvl in ("easy", "middle") else lvl) or {}
        body = variant.get("body") or ""
        body_lc = body.lower()
        body_stems = _body_word_stem_index(body)
        kept = []
        dropped = []
        for k in kws:
            if _keyword_in_body_with_index(k.get("term", ""), body_lc, body_stems):
                kept.append(k)
            else:
                dropped.append(k.get("term"))
        det["keywords"] = kept
        if dropped:
            log.info("  [%s] dropped hallucinated keywords: %s", slot_key, dropped)
    return details


def _reasoner_call_with_model(model: str, system: str, user: str,
                                max_tokens: int,
                                max_transport_attempts: int,
                                max_content_attempts: int,
                                api_key: str, endpoint: str) -> dict:
    """Inner reasoner retry loop against ONE model. Transport failures
    (network / 429 / 5xx) retry full max_transport_attempts; content
    failures (JSON parse) retry only max_content_attempts. Truncation
    raises immediately so the caller can split-batch."""
    payload = {
        "model": model,
        "thinking": {"type": "enabled"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
    }
    transport_attempts = 0
    content_attempts = 0
    last_err: Exception | None = None
    while True:
        try:
            res = _deepseek_post(payload, timeout=300, api_key=api_key, endpoint=endpoint)
            if res.parsed is not None:
                if res.repair_kind:
                    CALL_STATS["reasoner_repaired"] += 1
                    log.info("reasoner: parse OK after repair on %s (%s, finish=%s)",
                             model, res.repair_kind, res.finish_reason)
                return res.parsed
            if res.finish_reason == "length":
                CALL_STATS["reasoner_truncated"] += 1
                raise RuntimeError(
                    f"reasoner output truncated (max_tokens={max_tokens} hit); "
                    "split-batch fallback in caller will shrink the payload"
                )
            content_attempts += 1
            CALL_STATS["reasoner_content_retries"] += 1
            last_err = res.parse_error or json.JSONDecodeError("repair failed", "", 0)
            # Log raw content snippet so we can see WHY the JSON parse
            # failed — same instrumentation as chat-call path.
            raw = res.raw_content or ""
            head = raw[:300].replace("\n", "\\n")
            tail = raw[-200:].replace("\n", "\\n") if len(raw) > 500 else ""
            log.warning("reasoner content attempt %d/%d on %s: JSON parse failed (finish=%s, len=%d)",
                        content_attempts, max_content_attempts, model,
                        res.finish_reason, len(raw))
            log.warning("  raw[:300] = %r", head)
            if tail:
                log.warning("  raw[-200:] = %r", tail)
            if content_attempts >= max_content_attempts:
                raise RuntimeError(
                    f"reasoner on {model}: {max_content_attempts} content attempts failed"
                ) from last_err
            time.sleep(_retry_sleep_for(last_err, content_attempts))
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            transport_attempts += 1
            CALL_STATS["reasoner_transport_retries"] += 1
            last_err = e
            wait = _retry_sleep_for(e, transport_attempts)
            log.warning("reasoner transport attempt %d/%d on %s failed (%s): waiting %.1fs",
                        transport_attempts, max_transport_attempts, model,
                        type(e).__name__, wait)
            if transport_attempts >= max_transport_attempts:
                raise RuntimeError(
                    f"reasoner on {model}: {max_transport_attempts} transport attempts failed"
                ) from last_err
            time.sleep(wait)


def deepseek_reasoner_call(system: str, user: str, max_tokens: int = 16000,
                           max_transport_attempts: int = 4,
                           max_content_attempts: int = 2) -> dict:
    """Call the active reasoner (thinking mode) provider.

    Same fast-fail fallback as `deepseek_call`: try primary (Pro)
    with content_attempts=1; on JSON parse failure, switch to
    deepseek-v4-flash with the full max_content_attempts retry
    budget. Transport failures retry full max_transport_attempts on
    primary (network is transient).

    Truncation always raises immediately — caller's split-batch
    shrinks the payload."""
    api_key, endpoint, model = _resolve_reasoner_provider()
    CALL_STATS["reasoner_calls"] += 1
    fallback = "deepseek-v4-flash"
    primary_is_flash = "flash" in model.lower()

    if primary_is_flash:
        return _reasoner_call_with_model(model, system, user, max_tokens,
                                            max_transport_attempts,
                                            max_content_attempts,
                                            api_key, endpoint)

    # Primary non-Flash → 1 content attempt, then bail to Flash on
    # content failure. Transport retries still apply on primary
    # (transient network errors aren't model-specific).
    try:
        return _reasoner_call_with_model(model, system, user, max_tokens,
                                            max_transport_attempts,
                                            max_content_attempts=1,
                                            api_key=api_key, endpoint=endpoint)
    except RuntimeError as primary_err:
        # Distinguish content-failure (we want to fall back) from
        # truncation (split-batch is the right answer, not Flash).
        msg = str(primary_err)
        if "truncated" in msg or "split-batch" in msg:
            raise
        log.warning("reasoner primary %s failed once; switching to %s with %d content retries",
                    model, fallback, max_content_attempts)
        try:
            return _reasoner_call_with_model(fallback, system, user, max_tokens,
                                                max_transport_attempts,
                                                max_content_attempts,
                                                api_key, endpoint)
        except RuntimeError as fallback_err:
            raise RuntimeError(
                f"reasoner: primary ({model}, 1 content try) and "
                f"fallback ({fallback}, {max_content_attempts} content tries) both failed"
            ) from fallback_err


def _detail_enrich_input_single_level(rewrite_result: dict, level: str) -> str:
    """Build an input covering only easy OR only middle slots (one slot per
    article). Smaller payload → less chance of malformed JSON under reasoner
    load.

    Slot/body alignment is reinforced by repeating the target slot key
    INSIDE each article block — without this the reasoner has shipped
    keywords from article N's body into slot key (N+1)_<level>.
    """
    assert level in ("easy", "middle")
    arts = rewrite_result.get("articles") or []
    n = len(arts)
    expected_keys = [f"{i}_{level}" for i in range(n)]
    lines = [
        f"{n} article{'s' if n != 1 else ''} below. "
        f"Generate detail fields ONLY for the {level} level.",
        f"REQUIRED output keys (produce ONLY these, in this exact spelling): {expected_keys}",
        "",
        "ALIGNMENT RULE: every field you generate for a given slot key MUST",
        f"come from the body shown under that exact slot key below.  "
        f"Do NOT shift, swap, or reorder. Keywords ESPECIALLY: every term",
        f"in slot K_{level}'s `keywords` MUST appear (or as a common",
        "inflection) in the body labeled K_" + level + ".",
        "",
    ]
    for i, art in enumerate(arts):
        v = art.get(f"{level}_en") or {}
        slot = f"{i}_{level}"
        lines.append(f"=== SLOT KEY: {slot}  (output key in your JSON: \"{slot}\") ===")
        lines.append(f"Headline: {v.get('headline','')}")
        lines.append(f"Body for slot {slot} ({len((v.get('body') or '').split())} words) ↓↓↓")
        lines.append((v.get("body") or ""))
        lines.append(f"↑↑↑ end of body for slot {slot}")
        lines.append("")
    lines.append("")
    lines.append(f"FINAL CHECKLIST before you return — verify each:")
    lines.append(f"  · output keys are EXACTLY {expected_keys}, no extras, no shifts")
    lines.append(f"  · for each slot K_{level}, every `keywords[].term` appears (or in")
    lines.append(f"    common inflected form) in the body labeled K_{level} above")
    lines.append(f"  · `correct_answer` for each question matches one of `options` literally")
    return "\n".join(lines)


def _detail_enrich_input_per_category(
    rewrite_result: dict, category: str, indices: list[int]
) -> str:
    """Build an input covering ONE category × BOTH levels (easy + middle).

    Used by the 3-batch (per-category) refactor. `indices` are the
    positions of this category's articles in rewrite_result["articles"]
    (preserves the global slot numbering — the reasoner sees e.g.
    `0_easy / 0_middle` for News slot 1, even when it's the first article).
    Output covers every (idx, level) pair.
    """
    arts = rewrite_result.get("articles") or []
    expected_keys: list[str] = []
    for i in indices:
        for lvl in ("easy", "middle"):
            expected_keys.append(f"{i}_{lvl}")

    lines = [
        f"{len(indices)} article{'s' if len(indices) != 1 else ''} from "
        f"category **{category}** below. Generate detail fields for "
        f"BOTH easy AND middle levels of each article.",
        f"REQUIRED output keys (produce ONLY these, in this exact spelling): "
        f"{expected_keys}",
        "",
        "ALIGNMENT RULE: every field you generate for a given slot key MUST",
        "come from the body shown under that exact slot key below.",
        "Do NOT shift, swap, or reorder. Keywords ESPECIALLY: every term",
        "in slot K_<level>'s `keywords` MUST appear (or as a common",
        "inflection) in the body labeled K_<level>.",
        "",
    ]
    for i in indices:
        art = arts[i]
        for lvl in ("easy", "middle"):
            v = art.get(f"{lvl}_en") or {}
            slot = f"{i}_{lvl}"
            lines.append(
                f"=== SLOT KEY: {slot}  (output key in your JSON: \"{slot}\") ==="
            )
            lines.append(f"Headline: {v.get('headline','')}")
            lines.append(
                f"Body for slot {slot} "
                f"({len((v.get('body') or '').split())} words) ↓↓↓"
            )
            lines.append((v.get("body") or ""))
            lines.append(f"↑↑↑ end of body for slot {slot}")
            lines.append("")
    lines.append("")
    lines.append("FINAL CHECKLIST before you return — verify each:")
    lines.append(f"  · output keys are EXACTLY {expected_keys}, no extras, no shifts")
    lines.append("  · for each slot K_<level>, every `keywords[].term` appears (or in")
    lines.append("    common inflected form) in the body labeled K_<level> above")
    lines.append("  · `correct_answer` for each question matches one of `options` literally")
    return "\n".join(lines)


def detail_enrich(rewrite_result: dict) -> dict:
    """Detail enrichment via split 3-slot batches (easy-only + middle-only).

    NOTE: this function is already called PER CATEGORY by full_round.py —
    each invocation receives 3 articles for one category. The internal
    split below is per-LEVEL, so total reasoner calls per pipeline run
    are 3 categories × 2 levels = 6 calls of 3 slots each.

    The combined 6-slot single call kept hitting the reasoner's token
    cap on realistic article batches, so we go straight to the two
    split calls. If one half fails after retries we keep the other
    half's slots; the caller decides whether the partial set is
    acceptable.

    Post-filter hallucinated keywords + augment with Python-extracted
    keywords at the end."""
    details: dict = {}
    for level in ("easy", "middle"):
        try:
            # 3 slots per call (one level for one category).
            #
            # 2026-05-02: bumped 12000 → 20000 (admin call, in two
            # steps: 12k → 16k via PR #16 + bug record
            # 2026-05-02-pipeline-enrich-truncation, then 16k → 20k
            # to give extra headroom — News middle's combination of
            # long stories + V4 Pro thinking-mode CoT + structured
            # questions/background_read/Article_Structure can spike).
            # If 20k starts truncating too, the next architectural
            # step is a true "1 slot at a time" fallback below
            # split-batch (deferred — see invariant in bug record).
            res = deepseek_reasoner_call(
                DETAIL_ENRICH_PROMPT,
                _detail_enrich_input_single_level(rewrite_result, level),
                max_tokens=20000,
            )
            for k, v in (res.get("details") or {}).items():
                details[k] = v
            log.info("split-batch %s: %d slots OK", level,
                     len(res.get("details") or {}))
        except RuntimeError as e:
            log.error("split-batch %s failed after retries: %s", level, e)
            # Continue — the other level may still succeed.

    filter_keywords(details, rewrite_result)
    # NOTE: pipeline/keyword_extractor.augment_details_with_keywords used
    # to run here as a safety net, padding each slot with deterministic
    # body-grounded vocab (empty explanations). Pack-time scrub now
    # drops definition-less keywords (a hover-card with no definition
    # is dead UX), so the augment was producing junk that got
    # immediately deleted. Removed 2026-04-26. The file stays in tree
    # in case we wire a secondary LLM pass to backfill definitions
    # for body-extracted vocab — at which point the augment can come
    # back and its terms will pass the scrub.
    return {"details": details}


# ---------------------------------------------------------------------------
# Cross-source duplicate check
# ---------------------------------------------------------------------------

DUP_CHECK_PROMPT = """You are checking a small set of kids news article briefs for
cross-source DUPLICATES.

A "duplicate" = two briefs covering the SAME news event (e.g. "Pope on Iran peace"
appears in both PBS and AJ). Different angles on the same event still count as
duplicates. Different stories that merely share a topic (both about science, etc.)
are NOT duplicates.

Input: N briefs. Each has an id, title, source, and a short excerpt.

Return ONLY valid JSON:
{
  "verdict": "OK" | "DUP_FOUND",
  "duplicate_pairs": [
    {"ids": [i, j], "reason": "why these two cover the same event"}
  ],
  "drop_suggestion": <id of the brief to drop if DUP_FOUND, else null>
}

If verdict is OK, duplicate_pairs should be [] and drop_suggestion null.
If DUP_FOUND, prefer to drop the one with lower priority source (if given) or
the less-engaging one. Only suggest dropping ONE brief even if multiple pairs exist
(we handle one substitution per cycle)."""


def dup_check_input(briefs: list[dict]) -> str:
    """briefs: [{id, title, source_name, source_priority, snippet_or_excerpt}]"""
    lines = ["Check the following briefs for cross-source duplicates:", ""]
    for b in briefs:
        lines.append(f"[id: {b['id']}] {b.get('title', '')}")
        lines.append(f"  source: {b.get('source_name', '')} (priority {b.get('source_priority', '?')})")
        lines.append(f"  excerpt: {(b.get('excerpt') or '')[:400]}")
        lines.append("")
    return "\n".join(lines)


def check_duplicates(briefs: list[dict]) -> dict:
    return deepseek_call(DUP_CHECK_PROMPT, dup_check_input(briefs),
                         max_tokens=500, temperature=0.1)


# ---------------------------------------------------------------------------
# Phase A — per-source mining (unified full+light)
# ---------------------------------------------------------------------------

MAX_PICK_BODY_WORDS = 5000   # reject picks with suspiciously long body (probably aggregate page)


def verify_article_content(art: dict) -> tuple[bool, str | None]:
    """Check body words + image quality. Returns (ok, reject_reason)."""
    wc = art.get("word_count", 0)
    if wc < MIN_PICK_BODY_WORDS:
        return False, f"body {wc}w < {MIN_PICK_BODY_WORDS}w"
    if wc > MAX_PICK_BODY_WORDS:
        return False, f"body {wc}w > {MAX_PICK_BODY_WORDS}w (suspect aggregate page)"
    if is_generic_social_image(art.get("og_image")):
        return False, f"generic social image: {art.get('og_image')}"
    if not art.get("og_image"):
        return False, "no og:image"
    return True, None


def _fetch_and_enrich(entry: dict) -> dict:
    """Fetch HTML, extract body+og:image, populate word_count."""
    from .cleaner import extract_article_from_html
    url = entry.get("link") or ""
    html_text = fetch_html(url)
    if not html_text:
        entry["body"] = ""
        entry["paragraphs"] = []
        entry["og_image"] = None
        entry["word_count"] = 0
        return entry
    extracted = extract_article_from_html(url, html_text)
    entry["body"] = extracted.get("cleaned_body") or ""
    entry["paragraphs"] = extracted.get("paragraphs") or []
    entry["og_image"] = extracted.get("og_image")
    entry["word_count"] = len(entry["body"].split()) if entry["body"] else 0
    return entry


def run_source_phase_a(source, html_tag_stripper=None) -> dict | None:
    """Run Phase A for one source. Returns a dict like:
        {
          "source": source,
          "winner": <art dict with body+og_image+word_count populated>,
          "winner_pick_slot": "choice_1" | "choice_2" | "alternate_0" | ...,
          "batch_vet": <raw vet response>,
          "kept_briefs": <list of briefs sent to vet>,
          "attempts": [{pick_slot, id, reject_reason or None}],
        }
    or None if no viable winner after trying choice_1, choice_2, then alternates.

    `source` must have attributes: name, rss_url, flow, max_to_vet, min_body_words.
    """
    from .cleaner import extract_article_from_html
    import re as _re

    log.info("[%s] Phase A: flow=%s", source.name, source.flow)
    rss_entries = fetch_rss_entries(source.rss_url, max_entries=25)
    log.info("[%s]  RSS entries: %d", source.name, len(rss_entries))

    if source.flow == "full":
        processed = [process_entry(e, min_words=source.min_body_words) for e in rss_entries]
        kept = [p for p in processed if not p.get("skip_reason")]
        if source.max_to_vet and len(kept) > source.max_to_vet:
            kept = kept[: source.max_to_vet]
        if len(kept) < 2:
            log.warning("[%s]  only %d kept — insufficient for choice_1+choice_2", source.name, len(kept))
            return None
        briefs = kept
    else:
        # Light flow: skip video URLs, strip HTML from descriptions
        video_re = _re.compile(r"/(?:videos?|watch|live|podcast)/", _re.I)
        html_tag_re = _re.compile(r"<[^>]+>")
        briefs = []
        for e in rss_entries:
            url = e.get("link") or ""
            if video_re.search(url):
                continue
            desc_clean = html_tag_re.sub("", e.get("summary") or "").strip()
            briefs.append({**e, "summary": desc_clean, "highlights": [desc_clean[:400]] if desc_clean else []})
            if len(briefs) >= source.max_to_vet:
                break

        if len(briefs) < 2:
            log.warning("[%s]  only %d briefs — insufficient", source.name, len(briefs))
            return None

    log.info("[%s]  vetter input: %d briefs (reasoner)", source.name, len(briefs))
    # max_tokens 2026-05-02: 8000 → 12000 (admin call, mirrors the
    # detail_enrich bump to 20k earlier today). PBS NewsHour
    # 6-briefs vet hit 8000 in run 25259782432; 12k gives 50% margin.
    # Note: this call has no split-batch fallback — truncation here
    # propagates as a RuntimeError. If 12k starts truncating too,
    # add a per-brief fallback similar to detail_enrich's pattern.
    batch_vet = deepseek_reasoner_call(build_vet_prompt(2),
                                        vet_curator_input(briefs, 2),
                                        max_tokens=12000)

    # Re-apply strict thresholds authoritatively
    for v in batch_vet.get("vet") or []:
        safety = v.get("safety") or {}
        dims = [safety.get(d, 0) or 0 for d in SAFETY_DIMS]
        safety["total"] = sum(dims)
        safety["verdict"] = apply_vet_thresholds(safety)
    # Drop picks that became REJECT
    vet_by_id = {v["id"]: v for v in batch_vet.get("vet") or []}
    picks = [p for p in (batch_vet.get("picks") or [])
             if not (vet_by_id.get(p.get("id"), {}).get("safety", {}).get("verdict") == "REJECT")]
    alternates = [a for a in (batch_vet.get("alternates") or [])
                  if not (vet_by_id.get(a.get("id"), {}).get("safety", {}).get("verdict") == "REJECT")]

    # Build candidate order: choice_1, choice_2, alternate_0, alternate_1, ...
    candidate_ids: list[tuple[str, int]] = []
    for i, p in enumerate(picks[:2]):
        candidate_ids.append((f"choice_{i+1}", p.get("id")))
    for i, a in enumerate(alternates):
        candidate_ids.append((f"alternate_{i}", a.get("id")))

    # Verify up to MAX_CANDIDATES_PER_SOURCE candidates — each must pass body
    # + image checks. Downstream (past-dedup + cross-source-dedup) picks the
    # best surviving candidate per source instead of cheaply taking choice_1.
    MAX_CANDIDATES_PER_SOURCE = 4
    candidates: list[dict] = []
    attempts: list[dict] = []
    for slot, cid in candidate_ids:
        if len(candidates) >= MAX_CANDIDATES_PER_SOURCE:
            break
        if cid is None or cid >= len(briefs):
            continue
        art = dict(briefs[cid])
        if source.flow == "light" or not art.get("body"):
            log.info("[%s]  fetching [%s id=%d] %s", source.name, slot, cid,
                     art.get("link", "")[:80])
            art = _fetch_and_enrich(art)
        ok, reason = verify_article_content(art)
        attempts.append({"slot": slot, "id": cid, "title": art.get("title"),
                         "word_count": art.get("word_count"), "ok": ok, "reason": reason})
        if ok:
            art["_vet_info"] = vet_by_id.get(cid)
            candidates.append({"winner": art, "slot": slot})
            log.info("[%s]  ✓ [%s id=%d] %dw", source.name, slot, cid,
                     art.get("word_count", 0))
        else:
            log.info("[%s]  ✗ [%s id=%d] %s — %s", source.name, slot, cid,
                     art.get("title", "")[:40], reason)

    if not candidates:
        log.warning("[%s]  no viable candidate after %d attempts", source.name,
                    len(attempts))
        return None

    log.info("[%s]  → %d candidates ready", source.name, len(candidates))

    # Back-compat fields for callers that still read .winner / .winner_slot.
    top = candidates[0]
    return {
        "source": source,
        "candidates": candidates,       # NEW: ranked list (up to 4)
        "winner": top["winner"],        # legacy: first candidate
        "winner_slot": top["slot"],     # legacy: first candidate's slot
        "batch_vet": batch_vet,
        "kept_briefs": briefs,
        "attempts": attempts,
    }


# ---------------------------------------------------------------------------
# HTML render
# ---------------------------------------------------------------------------

def verdict_class(v: str, kind: str = "safety") -> str:
    if kind == "safety":
        return {"SAFE": "v-safe", "CAUTION": "v-caution", "REJECT": "v-reject"}.get(v, "")
    return {"ENGAGING": "v-engaging", "MEH": "v-meh", "BORING": "v-boring"}.get(v, "")


def render_html(source_label: str, rss_url: str,
                all_entries: list[dict], kept: list[dict], rejected: list[dict],
                batch_vet: dict, kids_articles_by_id: dict, target_words: int,
                min_words: int) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def esc(s):
        return html.escape(str(s) if s is not None else "")

    vet_list = batch_vet.get("vet") or []
    clusters = batch_vet.get("clusters") or []
    picks = batch_vet.get("picks") or []
    picked_ids = {p.get("id") for p in picks}
    cluster_by_id = {c.get("id"): c for c in clusters}
    article_to_cluster = {v.get("id"): v.get("cluster_id") for v in vet_list}

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(source_label)} → 12yo — {today}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#222;line-height:1.5;}}
  h1{{font-size:24px;margin:8px 0;}}
  h2{{font-size:17px;margin:28px 0 10px;border-bottom:2px solid #eee;padding-bottom:6px;color:#444;}}
  .meta{{color:#777;font-size:13px;margin-bottom:18px;}}
  .stats{{background:#f6f6f6;border-radius:6px;padding:10px 14px;margin:12px 0;font-size:13px;color:#555;}}
  .stats b{{color:#222;}}
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
<h1>{esc(source_label)} → 12-year-old kids news — {today}</h1>
<div class="meta">
  RSS: <a href="{esc(rss_url)}" target="_blank">{esc(rss_url)}</a> · Filter: body ≥ {min_words}w + image + not /video/ · 2 DeepSeek calls total.
</div>

<div class="threshold">
  <b>Vet thresholds (locked 2026-04-23):</b>
  <b class="v-reject pill">REJECT</b> if any dim ≥ 4 or total > 6 ·
  <b class="v-caution pill">CAUTION</b> if total 5-6 (all dims ≤ 3) ·
  <b class="v-safe pill">SAFE</b> if total 0-4 (all dims ≤ 3)
</div>

<div class="stats">
  <b>RSS entries:</b> {len(all_entries)} ·
  <b>Kept (to vetter):</b> {len(kept)} ·
  <b>Rejected at filter:</b> {len(rejected)} ·
  <b>Clusters:</b> {len(clusters)} (HOT: {sum(1 for c in clusters if c.get("is_hot"))}) ·
  <b>Picks:</b> {len(picks)} ·
  <b>Kids articles:</b> {len(kids_articles_by_id)}
</div>

<h2>Topic clusters</h2>"""]

    hot_clusters = [c for c in clusters if c.get("is_hot")]
    other_clusters = [c for c in clusters if not c.get("is_hot")]
    for c in hot_clusters + other_clusters:
        badge = '<span class="hot">🔥 HOT</span>' if c.get("is_hot") else ""
        member_titles = []
        for mid in c.get("members", []):
            if mid < len(kept):
                member_titles.append(f"[{mid}] {kept[mid].get('title','')[:70]}")
        members_list = "<br>".join(esc(t) for t in member_titles[:10])
        parts.append(f"""
<div class="cluster-box">
  <b>{esc(c.get('theme','?'))}</b> {badge} — <b>{c.get('size', 0)}</b> articles
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
        if aid >= len(kept):
            continue
        art = kept[aid]
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
  <td><a href="{esc(art.get('link',''))}" target="_blank">{esc(title[:70])}</a>{flags_html}</td>""")
        for dim in SAFETY_DIMS:
            parts.append(f'<td class="n">{safety.get(dim, "?")}</td>')
        parts.append(f"""<td class="tot">{safety.get("total", "?")}</td>
  <td><span class="pill {verdict_class(safety.get('verdict',''), 'safety')}">{esc(safety.get('verdict',''))}</span></td>
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
        if aid >= len(kept):
            continue
        art = kept[aid]
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
  <td><span class="pill {verdict_class(interest.get('verdict',''), 'interest')}">{esc(interest.get('verdict',''))}</span></td>
</tr>""")
    parts.append("""</tbody></table>""")

    # PICKS
    parts.append("""
<h2>Final picks</h2>""")
    for p in picks:
        pid = p.get("id")
        if pid is None or pid >= len(kept):
            continue
        art = kept[pid]
        cluster_id = article_to_cluster.get(pid, "")
        cluster_info = cluster_by_id.get(cluster_id, {})
        hot_badge = f" [🔥 cluster: {cluster_info.get('theme','')} — {cluster_info.get('size',0)} articles]" if cluster_info.get("is_hot") else ""
        parts.append(f"""
<div class="reason">
  <b>Pick id {pid}:</b> <a href="{esc(art.get('link',''))}" target="_blank">{esc(art.get('title',''))}</a>{esc(hot_badge)}<br>
  <b>Reason:</b> {esc(p.get('reason',''))}
</div>""")

    # KIDS ARTICLES
    parts.append(f"""
<h2>Generated kids articles ({target_words}-word, 12-year-old level)</h2>""")
    for pid, ka in kids_articles_by_id.items():
        if pid >= len(kept):
            continue
        src = kept[pid]
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
  <div class="ksrc">📰 Source: <a href="{esc(src_url)}" target="_blank">{esc(src.get('title',''))}</a> · {esc(src_host)} · <span style="color:#888;">generated {wc} words</span></div>
  {f'<img src="{esc(img)}" alt=""/>' if img else ''}
  <div class="kheadline">{esc(headline)}</div>
  <div class="kbody">
{body_paragraphs}
  </div>
  <div class="kwim"><b>Why it matters:</b> {esc(wim)}</div>
  <details><summary>Full original article (source body)</summary><pre>{esc(src.get('body',''))}</pre></details>
</div>""")
    parts.append("""
</body>
</html>""")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Top-level run function — called by news_aj_full.py / news_pbs_full.py
# ---------------------------------------------------------------------------

def run_pipeline(*, rss_url: str, source_label: str,
                 output_slug: str,
                 max_rss: int = MAX_RSS_DEFAULT,
                 max_kept: int = 0,     # 0 = no cap, send all kept to vetter
                 pick_count: int = 2,
                 min_words: int = MIN_WORDS_DEFAULT,
                 target_words: int = 400) -> None:
    log.info("[%s] Step 1: fetch RSS %s", source_label, rss_url)
    rss_entries = fetch_rss_entries(rss_url, max_entries=max_rss)
    log.info("  %d entries", len(rss_entries))

    log.info("[%s] Step 2: scrape + filter (≥%dw, has image, not /video/)", source_label, min_words)
    all_processed = [process_entry(e, min_words=min_words) for e in rss_entries]
    kept = [p for p in all_processed if not p.get("skip_reason")]
    rejected = [p for p in all_processed if p.get("skip_reason")]
    log.info("  kept=%d, rejected=%d", len(kept), len(rejected))

    # Cap kept list BEFORE sending to vetter (user-defined per source)
    if max_kept and len(kept) > max_kept:
        log.info("  capping kept at %d for vetter (was %d)", max_kept, len(kept))
        kept = kept[:max_kept]

    if len(kept) < pick_count:
        log.error("Only %d kept — need ≥ %d", len(kept), pick_count)
        return

    log.info("[%s] Step 3: batched vet+cluster+pick (1 call, %d in)", source_label, len(kept))
    batch_vet = vet_and_curate(kept, pick_count)
    picks = batch_vet.get("picks") or []
    clusters = batch_vet.get("clusters") or []
    log.info("  clusters: %d (hot: %d)", len(clusters),
             sum(1 for c in clusters if c.get("is_hot")))
    log.info("  picks: %s", [p.get("id") for p in picks])
    for p in picks:
        pid = p.get("id")
        if pid is not None and pid < len(kept):
            log.info("    ★ [%s] %s", pid, kept[pid].get("title",""))

    if len(picks) < pick_count:
        log.warning("Curator returned only %d picks (wanted %d)", len(picks), pick_count)
    if not picks:
        log.error("No picks returned — aborting")
        return

    log.info("[%s] Step 4: batched rewrite (1 call, %d in)", source_label, len(picks))
    picks_with_arts = [(p.get("id"), kept[p.get("id")]) for p in picks
                       if p.get("id") is not None and p.get("id") < len(kept)]
    rewrite_result = rewrite_batch(picks_with_arts, target_words)
    kids_articles_by_id: dict[int, dict] = {}
    for a in rewrite_result.get("articles") or []:
        sid = a.get("source_id")
        if sid is not None:
            wc = len((a.get("body") or "").split())
            log.info("  ✓ id=%d: %s (%d words)", sid, a.get("headline","")[:60], wc)
            kids_articles_by_id[sid] = a

    # Output
    out_dir = (_REPO_ROOT / "website/test_output") / \
              datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{output_slug}.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rss": rss_url,
        "source_label": source_label,
        "counts": {"rss": len(rss_entries), "kept": len(kept), "rejected": len(rejected),
                   "clusters": len(clusters), "picks": len(picks),
                   "kids_articles": len(kids_articles_by_id)},
        "kept": [{"id": i, "title": k["title"], "link": k["link"], "word_count": k["word_count"]}
                 for i, k in enumerate(kept)],
        "rejected": [{"title": r["title"], "reason": r["skip_reason"]} for r in rejected],
        "batch_vet": batch_vet,
        "kids_articles": kids_articles_by_id,
    }, indent=2, ensure_ascii=False))

    html_path = (_REPO_ROOT / f"website/{output_slug}.html")
    html_path.write_text(render_html(source_label, rss_url,
                                      all_processed, kept, rejected,
                                      batch_vet, kids_articles_by_id,
                                      target_words, min_words))
    log.info("HTML: %s", html_path)
    log.info("View: http://localhost:18100/%s.html", output_slug)
