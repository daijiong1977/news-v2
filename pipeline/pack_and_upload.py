"""Pack `website/` into a zip and upload it to Supabase Storage as both
`<YYYY-MM-DD>.zip` (immutable archive) and `latest.zip` (what the deploy repo's
GitHub Action fetches)."""
from __future__ import annotations

import logging
import os
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pack")

_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        k, v = _line.strip().split("=", 1)
        os.environ[k] = v

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "website"
BUCKET = "redesign-daily-content"

# Allowlist of top-level files/dirs that ship to production.
INCLUDE_FILES = {"index.html", "article.jsx", "home.jsx", "components.jsx",
                 "data.jsx", "user-panel.jsx"}
INCLUDE_DIRS = {"payloads", "article_payloads", "article_images", "assets"}


def collect_files() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for name in INCLUDE_FILES:
        p = WEB / name
        if p.is_file():
            out.append((p, name))
    for d in INCLUDE_DIRS:
        base = WEB / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                out.append((p, str(p.relative_to(WEB))))
    return out


def build_zip() -> bytes:
    buf = BytesIO()
    files = collect_files()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p, arc in files:
            zf.write(p, arcname=arc)
    log.info("Packed %d files (%d bytes)", len(files), buf.tell())
    return buf.getvalue()


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = build_zip()
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    for key in (f"{today}.zip", "latest.zip"):
        # Upsert: Supabase storage upload returns error if object exists unless upsert set.
        res = sb.storage.from_(BUCKET).upload(
            path=key,
            file=body,
            file_options={"content-type": "application/zip", "upsert": "true"},
        )
        log.info("uploaded %s → %s", key, getattr(res, "path", key))

    pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
    log.info("public URL: %s", pub)


if __name__ == "__main__":
    main()
