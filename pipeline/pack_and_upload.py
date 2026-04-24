"""Pack `website/` into a zip and upload it to Supabase Storage as both
`<YYYY-MM-DD>.zip` (immutable archive) and `latest.zip` (what the deploy repo's
GitHub Action fetches). Also writes a `latest-manifest.json` (+ dated copy)
with the version + content hash + story IDs so anyone inspecting the bucket
knows what's inside without downloading.

Validates today's content bundle BEFORE packing. If any listing or detail file
is missing or incomplete, refuses to upload — the live site keeps yesterday's
zip until the pipeline produces a fully-formed bundle.

After a successful upload, runs retention: keeps `latest.*` + the last
`RETENTION_DAYS` dated archives; deletes older dated zips + manifests."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
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
RETENTION_DAYS = 30  # dated archives older than this get deleted

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


CATS = ("news", "science", "fun")
# (field, min_count) — what a detail payload MUST contain to count as complete.
DETAIL_MIN = [
    ("keywords", 3),
    ("questions", 3),
    ("background_read", 1),
    ("Article_Structure", 3),
]


def validate_bundle(today: str) -> None:
    """Fail (SystemExit 1) if today's bundle is incomplete. Check:
      · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
      · 18 detail payloads (9 stories × easy/middle), each with non-empty
        keywords/questions/background_read/Article_Structure
      · 9 article images on disk (one per story id)
    """
    errs: list[str] = []

    # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
    # cross-source dup drops when all backups are exhausted). <2 is fatal.
    payloads = WEB / "payloads"
    short_cats: set[str] = set()  # cats that shipped <3
    for cat in CATS:
        for lvl in ("easy", "middle", "cn"):
            p = payloads / f"articles_{cat}_{lvl}.json"
            if not p.is_file():
                errs.append(f"missing listing: {p.name}")
                continue
            try:
                doc = json.loads(p.read_text())
                arts = doc.get("articles") or []
                if len(arts) < 2:
                    errs.append(f"{p.name}: {len(arts)} articles (need ≥2)")
                elif len(arts) < 3:
                    short_cats.add(f"{cat}/{lvl}")
                for a in arts:
                    if not (a.get("title") and a.get("summary") and a.get("id")):
                        errs.append(f"{p.name}: article {a.get('id','?')} missing title/summary/id")
            except Exception as e:  # noqa: BLE001
                errs.append(f"{p.name}: parse error {e}")
    if short_cats:
        log.warning("Shipping with <3 articles in: %s", sorted(short_cats))

    # Detail payloads (easy + middle only; cn has no detail page) — iterate
    # actual story IDs from the middle listing so 2-article cats validate
    # cleanly.
    details = WEB / "article_payloads"
    all_story_ids: list[str] = []
    for cat in CATS:
        p = payloads / f"articles_{cat}_middle.json"
        if p.is_file():
            try:
                arts = json.loads(p.read_text()).get("articles") or []
                all_story_ids.extend(a.get("id") for a in arts if a.get("id"))
            except Exception:
                pass
    for story_id in all_story_ids:
        story_dir = details / f"payload_{story_id}"
        if not story_dir.is_dir():
            errs.append(f"missing detail dir: payload_{story_id}")
            continue
        for lvl in ("easy", "middle"):
            p = story_dir / f"{lvl}.json"
            if not p.is_file():
                errs.append(f"missing detail: {story_id}/{lvl}.json")
                continue
            try:
                d = json.loads(p.read_text())
                if not (d.get("summary") and len((d.get("summary") or "").split()) >= 50):
                    errs.append(f"{story_id}/{lvl}: summary missing or <50 words")
                for field, min_n in DETAIL_MIN:
                    if len(d.get(field) or []) < min_n:
                        errs.append(
                            f"{story_id}/{lvl}: {field} has "
                            f"{len(d.get(field) or [])} (need ≥{min_n})"
                        )
            except Exception as e:  # noqa: BLE001
                errs.append(f"{story_id}/{lvl}: parse error {e}")

    # Per-story images (same image used across easy/middle for a story)
    images_dir = WEB / "article_images"
    needed_images: set[str] = set()
    for cat in CATS:
        # Pull image_urls from today's listings — whichever level works
        for lvl in ("middle", "easy"):
            p = payloads / f"articles_{cat}_{lvl}.json"
            if not p.is_file():
                continue
            try:
                doc = json.loads(p.read_text())
                for a in doc.get("articles") or []:
                    url = a.get("image_url") or ""
                    if url:
                        needed_images.add(Path(url).name)
                break
            except Exception:
                continue
    for name in needed_images:
        if not (images_dir / name).is_file():
            errs.append(f"missing image: article_images/{name}")

    if errs:
        log.error("Bundle validation FAILED — refusing to pack/upload:")
        for e in errs:
            log.error("  · %s", e)
        raise SystemExit(1)
    log.info("Bundle validation OK: 9 listings · 18 details · %d images",
             len(needed_images))


def build_zip() -> bytes:
    buf = BytesIO()
    files = collect_files()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p, arc in files:
            zf.write(p, arcname=arc)
    log.info("Packed %d files (%d bytes)", len(files), buf.tell())
    return buf.getvalue()


def build_manifest(today: str, body: bytes) -> dict:
    """Summarize what this zip contains — version + content hash + story IDs.
    Consumers can compare manifest sha256 without downloading the zip."""
    stories: list[dict] = []
    for cat in CATS:
        p = WEB / "payloads" / f"articles_{cat}_middle.json"
        if not p.is_file():
            continue
        try:
            for a in (json.loads(p.read_text()).get("articles") or []):
                stories.append({
                    "id": a.get("id"),
                    "category": a.get("category"),
                    "title": a.get("title"),
                    "mined_at": a.get("mined_at"),
                    "source": a.get("source"),
                    "source_published_at": a.get("source_published_at"),
                })
        except Exception:
            pass
    return {
        "version": today,
        "packed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": os.environ.get("GITHUB_SHA") or "",
        "zip_bytes": len(body),
        "zip_sha256": hashlib.sha256(body).hexdigest(),
        "story_count": len(stories),
        "stories": stories,
    }


DATED_ZIP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.zip$")
DATED_MANIFEST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-manifest\.json$")
DATED_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def upload_dated_flat_files(sb, date_str: str, bundle: bytes | None = None) -> int:
    """Upload each file under the website bundle to `<date>/<relpath>` in the
    bucket so the UI can fetch past days' content directly (no zip parsing
    in the browser). `bundle` is an optional zip body — if given, files are
    extracted from it; otherwise read from local disk. Returns file count."""
    uploaded = 0
    if bundle is not None:
        zf = zipfile.ZipFile(BytesIO(bundle))
        members = [n for n in zf.namelist()
                   if n.endswith(".json") or n.endswith(".webp")]
        for name in members:
            body = zf.read(name)
            ctype = "application/json" if name.endswith(".json") else "image/webp"
            sb.storage.from_(BUCKET).upload(
                path=f"{date_str}/{name}",
                file=body,
                file_options={"content-type": ctype, "upsert": "true"},
            )
            uploaded += 1
    else:
        for p, arc in collect_files():
            if not (arc.endswith(".json") or arc.endswith(".webp")):
                continue  # skip HTML/JSX shell from dated flat copy
            ctype = "application/json" if arc.endswith(".json") else "image/webp"
            sb.storage.from_(BUCKET).upload(
                path=f"{date_str}/{arc}",
                file=p.read_bytes(),
                file_options={"content-type": ctype, "upsert": "true"},
            )
            uploaded += 1
    log.info("dated-flat: uploaded %d files under %s/", uploaded, date_str)
    return uploaded


def update_archive_index(sb, dates: list[str]) -> None:
    """Merge `dates` into `archive-index.json` (descending, deduped, cap 30)."""
    try:
        body = sb.storage.from_(BUCKET).download("archive-index.json")
        idx = json.loads(body.decode() if isinstance(body, bytes) else body)
    except Exception:
        idx = {"dates": []}
    existing = set(idx.get("dates") or [])
    existing.update(dates)
    all_dates = sorted(existing, reverse=True)[:RETENTION_DAYS]
    idx = {"dates": all_dates,
           "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    sb.storage.from_(BUCKET).upload(
        path="archive-index.json",
        file=json.dumps(idx, ensure_ascii=False, indent=2).encode(),
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    log.info("archive-index updated: %d dates (newest=%s)",
             len(all_dates), all_dates[0] if all_dates else "-")


def backfill_missing_archive_dirs(sb, current_index: list[str]) -> list[str]:
    """For any YYYY-MM-DD.zip in the bucket whose date isn't in the archive
    index AND doesn't yet have its flat dir, extract the zip and upload
    flat files. Returns list of backfilled dates."""
    current_set = set(current_index)
    objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
    candidates = []
    for o in objs or []:
        m = DATED_ZIP_RE.match(o.get("name") or "")
        if m and m.group(1) not in current_set:
            candidates.append(m.group(1))
    backfilled: list[str] = []
    for d in sorted(candidates):
        try:
            body = sb.storage.from_(BUCKET).download(f"{d}.zip")
            body = bytes(body) if not isinstance(body, bytes) else body
            upload_dated_flat_files(sb, d, bundle=body)
            backfilled.append(d)
        except Exception as e:  # noqa: BLE001
            log.warning("backfill %s failed: %s", d, e)
    return backfilled


def cleanup_retention(sb, keep_days: int) -> None:
    """Delete dated archives older than `keep_days`. Keeps `latest.*` always.
    Also removes all files under `<date>/` prefix for expired dates."""
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=keep_days)
    expired: set[str] = set()
    objs = sb.storage.from_(BUCKET).list("", {"limit": 1000})
    to_delete: list[str] = []
    for o in objs or []:
        name = o.get("name") or ""
        for rx in (DATED_ZIP_RE, DATED_MANIFEST_RE, DATED_DIR_RE):
            m = rx.match(name)
            if not m:
                continue
            try:
                day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            if day < cutoff:
                if rx is DATED_DIR_RE:
                    expired.add(name)
                else:
                    to_delete.append(name)
    # For each expired dir, list its files + delete them
    for d in expired:
        try:
            subs = sb.storage.from_(BUCKET).list(d, {"limit": 1000})
            for s in subs or []:
                to_delete.append(f"{d}/{s.get('name')}")
        except Exception as e:  # noqa: BLE001
            log.warning("retention: listing %s/ failed: %s", d, e)
    if not to_delete:
        log.info("retention: 0 old files (keep %d days)", keep_days)
        return
    # Supabase remove() takes a list of paths.
    sb.storage.from_(BUCKET).remove(to_delete)
    log.info("retention: deleted %d files older than %s",
             len(to_delete), cutoff.isoformat())


def local_freshest_mined_at() -> str | None:
    """ISO-8601 of the most recent mined_at across all today's listings."""
    stamps: list[str] = []
    for cat in CATS:
        p = WEB / "payloads" / f"articles_{cat}_middle.json"
        if not p.is_file():
            continue
        try:
            for a in json.loads(p.read_text()).get("articles") or []:
                if a.get("mined_at"):
                    stamps.append(a["mined_at"])
        except Exception:
            continue
    return max(stamps) if stamps else None


def check_not_overwriting_newer(sb) -> None:
    """Refuse to upload if the bucket already has a manifest whose packed_at
    (or freshest story mined_at) is newer than our local content. Prevents a
    local `pack_and_upload` from silently replacing CI-generated output."""
    try:
        body = sb.storage.from_(BUCKET).download("latest-manifest.json")
        remote = json.loads(body.decode() if isinstance(body, bytes) else body)
    except Exception:
        return  # nothing remote yet — safe to upload
    remote_stamps = [s.get("mined_at") for s in (remote.get("stories") or [])
                     if s.get("mined_at")]
    remote_freshest = max(remote_stamps) if remote_stamps else remote.get("packed_at")
    local_freshest = local_freshest_mined_at()
    if not (remote_freshest and local_freshest):
        return
    if local_freshest < remote_freshest:
        msg = (f"REFUSE: remote manifest is newer than local. "
               f"remote freshest={remote_freshest} · local freshest={local_freshest}. "
               "If you really want to overwrite, set ALLOW_STALE_UPLOAD=1.")
        if os.environ.get("ALLOW_STALE_UPLOAD") != "1":
            log.error(msg)
            raise SystemExit(1)
        log.warning("ALLOW_STALE_UPLOAD=1 set — proceeding despite: %s", msg)


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    validate_bundle(today)
    body = build_zip()
    manifest = build_manifest(today, body)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    check_not_overwriting_newer(sb)

    # Write zip in two locations: dated archive (immutable history) + latest.
    for key in (f"{today}.zip", "latest.zip"):
        sb.storage.from_(BUCKET).upload(
            path=key,
            file=body,
            file_options={"content-type": "application/zip", "upsert": "true"},
        )
        log.info("uploaded %s", key)

    # Same for the manifest — dated archive + latest pointer.
    for key in (f"{today}-manifest.json", "latest-manifest.json"):
        sb.storage.from_(BUCKET).upload(
            path=key,
            file=manifest_bytes,
            file_options={"content-type": "application/json", "upsert": "true"},
        )
        log.info("uploaded %s", key)

    log.info("manifest: version=%s · zip_bytes=%d · zip_sha256=%s · stories=%d",
             manifest["version"], manifest["zip_bytes"],
             manifest["zip_sha256"][:12], manifest["story_count"])

    # Flat per-day files — the UI fetches these when user picks a past date.
    try:
        upload_dated_flat_files(sb, today)
    except Exception as e:  # noqa: BLE001
        log.warning("dated-flat upload failed (non-fatal): %s", e)

    # Read existing archive-index, backfill any dated zip that doesn't yet
    # have a flat dir, then update archive-index with both backfilled +
    # today's date.
    try:
        body = sb.storage.from_(BUCKET).download("archive-index.json")
        existing_idx = json.loads(body.decode() if isinstance(body, bytes) else body)
        existing_dates = existing_idx.get("dates") or []
    except Exception:
        existing_dates = []
    try:
        backfilled = backfill_missing_archive_dirs(sb, existing_dates)
        if backfilled:
            log.info("archive backfill: %s", backfilled)
        update_archive_index(sb, [today] + backfilled)
    except Exception as e:  # noqa: BLE001
        log.warning("archive-index update failed (non-fatal): %s", e)

    # Retention sweep: delete dated archives older than RETENTION_DAYS.
    try:
        cleanup_retention(sb, RETENTION_DAYS)
    except Exception as e:  # noqa: BLE001
        log.warning("retention sweep failed (non-fatal): %s", e)

    pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
    log.info("public URL: %s", pub)


if __name__ == "__main__":
    main()
