"""Image optimize — v1-style unified WebP (1024×768, <60 KB).

Uses Pillow for decode+resize; libwebp's `cwebp` CLI for WebP encoding
(Pillow's WebP is unavailable on Python 3.14 on this machine).
libwebp's `dwebp` decodes source WebPs (Pillow also lacks WebP decode here).
"""
from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from PIL import Image

log = logging.getLogger("image")

MAX_DIMS = (1024, 768)
TARGET_BYTES = 60_000
DOWNLOAD_TIMEOUT = 15
# PATH first (Linux CI / apt install), Homebrew fallback (local macOS).
CWEBP = shutil.which("cwebp") or "/opt/homebrew/bin/cwebp"
DWEBP = shutil.which("dwebp") or "/opt/homebrew/bin/dwebp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def download_image(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=DOWNLOAD_TIMEOUT, headers=HEADERS, allow_redirects=True)
        if r.status_code >= 400:
            log.warning("image download %s -> %d", url, r.status_code)
            return None
        ct = r.headers.get("Content-Type", "").lower()
        if not (ct.startswith("image/") or ct == ""):
            log.warning("image download %s -> non-image content-type: %s", url, ct)
            return None
        return r.content
    except requests.RequestException as e:
        log.warning("image download failed %s: %s", url, e)
        return None


def fit_within(img: Image.Image, max_dims: tuple[int, int]) -> Image.Image:
    w, h = img.size
    scale = min(max_dims[0] / w, max_dims[1] / h, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


def _decode_webp_bytes(raw: bytes) -> Image.Image:
    """Convert WebP bytes → PNG via dwebp → Pillow Image (PNG decode supported)."""
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as fin, \
         tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fout:
        fin.write(raw)
        fin.flush()
        subprocess.run([DWEBP, fin.name, "-o", fout.name],
                       check=True, capture_output=True)
        return Image.open(fout.name).copy()


def _open_image(raw: bytes) -> Image.Image:
    """Open any supported image format into a Pillow Image."""
    try:
        return Image.open(io.BytesIO(raw))
    except Exception:
        # Fallback: maybe WebP (Pillow can't decode) — try dwebp
        return _decode_webp_bytes(raw)


def _encode_webp_via_cli(img: Image.Image, target_bytes: int) -> tuple[bytes, int]:
    """Save image as temp PNG, call cwebp with -size target, return (bytes, quality_used)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in, \
         tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp_out:
        img.save(tmp_in.name, format="PNG")
        # cwebp -size target in bytes; -m 6 = slower, better compression
        result = subprocess.run(
            [CWEBP, "-quiet", "-m", "6", "-size", str(target_bytes),
             tmp_in.name, "-o", tmp_out.name],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"cwebp failed: {result.stderr.decode()[:200]}")
        out_bytes = Path(tmp_out.name).read_bytes()
    return out_bytes, 85   # cwebp -size picks quality internally; we log 85 as sentinel


def optimize_bytes(raw: bytes,
                   max_dims: tuple[int, int] = MAX_DIMS,
                   target_bytes: int = TARGET_BYTES) -> tuple[bytes, dict]:
    """Return (webp_bytes, info) or raise."""
    img = _open_image(raw)
    # Flatten transparency to white
    if img.mode in ("RGBA", "LA", "P"):
        rgb = Image.new("RGB", img.size, (255, 255, 255))
        rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = rgb
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img = fit_within(img, max_dims)
    final_w, final_h = img.size

    webp_bytes, quality = _encode_webp_via_cli(img, target_bytes)

    info = {
        "final_bytes": len(webp_bytes),
        "final_quality": quality,
        "dims": (final_w, final_h),
        "hit_target": len(webp_bytes) <= target_bytes,
    }
    return webp_bytes, info


def fetch_and_optimize(source_url: str, out_path: Path) -> dict | None:
    """Download + optimize → save to out_path. Returns info dict or None on failure."""
    raw = download_image(source_url)
    if not raw:
        return None
    try:
        webp_bytes, info = optimize_bytes(raw)
    except Exception as e:
        log.warning("optimize failed for %s: %s", source_url, e)
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(webp_bytes)
    info["source_url"] = source_url
    info["original_bytes"] = len(raw)
    info["local_path"] = str(out_path)
    return info
