"""Write JSON + download images for each candidate."""
from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 10
DOWNLOAD_MAX_BYTES = 15_000_000
MIN_DOWNLOAD_BYTES = 5000  # spec says > 5KB


def _guess_ext(url: str, content_type: str | None) -> str:
    path = urlparse(url).path
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif"):
        if path.lower().endswith(ext):
            return ext
    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        guessed = mimetypes.guess_extension(ct)
        if guessed in (".jpg", ".jpeg", ".png", ".webp"):
            return guessed
        if ct == "image/jpeg":
            return ".jpg"
        if ct == "image/png":
            return ".png"
        if ct == "image/webp":
            return ".webp"
    return ".jpg"


def download_image(url: str, dest_dir: Path, candidate_id: str) -> str | None:
    """Downloads an image, returns relative path (e.g. 'images/<id>.jpg') or None."""
    try:
        r = requests.get(
            url,
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
            headers={"User-Agent": "kidsnews-v2-pipeline/0.1"},
            allow_redirects=True,
        )
        if r.status_code >= 400:
            log.warning("image download %s → %d", url, r.status_code)
            return None
        ct = r.headers.get("Content-Type", "")
        if not ct.lower().startswith("image/"):
            log.warning("image download %s → not image (%s)", url, ct)
            return None
        ext = _guess_ext(url, ct)
        dest_dir.mkdir(parents=True, exist_ok=True)
        fp = dest_dir / f"{candidate_id}{ext}"
        total = 0
        with open(fp, "wb") as f:
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > DOWNLOAD_MAX_BYTES:
                    break
                f.write(chunk)
        if total < MIN_DOWNLOAD_BYTES:
            log.warning("image download %s too small (%d bytes); discarding", url, total)
            try:
                fp.unlink()
            except OSError:
                pass
            return None
        return f"images/{fp.name}"
    except requests.RequestException as e:
        log.warning("image download %s failed: %s", url, e)
        return None


def write_category_json(out_dir: Path, category: str, payload: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = {"News": "news.json", "Science": "science.json", "Fun": "fun.json"}[category]
    fp = out_dir / fname
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return fp


def write_run_summary(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / "run_summary.json"
    fp.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return fp


def sanitize_candidate_for_output(cand: dict) -> dict:
    """Drop internal-only fields before serializing."""
    out = {}
    keep = {
        "id", "discovery_lane", "discovery_group",
        "source_name", "source_url", "title", "snippet",
        "raw_content", "read_method", "image_url", "image_filter_passed",
        "image_match_source",
        "vetter_score", "vetter_verdict", "vetter_flags", "vetter_payload",
        "vetter_notes", "discovered_rank", "vetted_rank",
        "selected_for_publish",
        "interest_scores", "interest_peak", "interest_verdict",
        "tavily_score",
        "curator_reason", "is_hot_duplicate", "curator_source_group",
        "alternate_promoted", "safety_vet_dropped",
    }
    for k in keep:
        out[k] = cand.get(k)
    return out
