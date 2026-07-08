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
import shutil
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

# Allowlist of files/dirs that ship to production. Split into SHELL
# (HTML/JSX/CSS — the app surface) and CONTENT (payloads + images —
# the daily-mined data). In republish-only mode, SHELL comes from the
# news-v2 git repo while CONTENT is taken from the *existing*
# latest.zip on Supabase Storage — so a republish refreshes the app
# code without clobbering today's freshly-mined articles.
SHELL_FILES = {"index.html", "article.jsx", "home.jsx", "components.jsx",
               "data.jsx", "user-panel.jsx", "admin.html",
               "parent.html", "parent.jsx", "kidsync.js",
               "tokens.css", "fonts.css", "autofix.html"}
SHELL_DIRS = {"assets", "components"}
CONTENT_DIRS = {"payloads", "article_payloads", "article_images", "article_pdfs"}

# Backward-compat aliases (other callers may import these).
INCLUDE_FILES = SHELL_FILES
INCLUDE_DIRS = SHELL_DIRS | CONTENT_DIRS


def collect_files(content_root: Path | None = None) -> list[tuple[Path, str]]:
    """Pack list. SHELL always comes from WEB; CONTENT comes from
    `content_root` if given (republish mode), else WEB."""
    out: list[tuple[Path, str]] = []
    for name in SHELL_FILES:
        p = WEB / name
        if p.is_file():
            out.append((p, name))
    for d in SHELL_DIRS:
        base = WEB / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                out.append((p, str(p.relative_to(WEB))))
    croot = content_root if content_root is not None else WEB
    for d in CONTENT_DIRS:
        base = croot / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                out.append((p, str(p.relative_to(croot))))
    return out


CATS = ("news", "science", "fun")
# (field, min_count) — what a detail payload MUST contain to count as complete.
# NOTE: keywords intentionally NOT required. They depend on the body's
# vocabulary richness (future: Google-10k frequency-rank filter, rank >2000
# for easy / >3000 for middle); plain-language bodies legitimately yield 0
# qualifying terms. Don't block the bundle on that.
DETAIL_MIN = [
    ("questions", 3),
    ("background_read", 1),
    ("Article_Structure", 3),
]


def validate_bundle(today: str, content_root: Path | None = None) -> None:
    """Fail (SystemExit 1) if today's bundle is incomplete. Check:
      · 9 listing files (3 cats × easy/middle/cn), each with exactly 3 articles
      · 18 detail payloads (9 stories × easy/middle), each with non-empty
        keywords/questions/background_read/Article_Structure
      · 9 article images on disk (one per story id)
    `content_root` overrides where content is read from (merge mode);
    default is the local website dir.
    """
    root = content_root or WEB
    errs: list[str] = []

    # Listing files — 2 or 3 per cat/lvl acceptable (ideal=3; 2 after
    # cross-source dup drops when all backups are exhausted). <2 is fatal.
    payloads = root / "payloads"
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
    details = root / "article_payloads"
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
    images_dir = root / "article_images"
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


# Use the same matcher as filter_keywords (news_rss_core) so a keyword
# rescued upstream by stem-aware matching does not get re-dropped at
# pack-time by an outdated suffix-only regex. Centralizing also means
# any future tweak (e.g. new morphological rule, denylist) propagates
# to both call sites automatically. (Copilot review 2026-04-29.)
from .news_rss_core import (
    _body_word_stem_index as _kw_body_stem_index,
    _keyword_in_body_with_index as _kw_match_with_index,
)


def _keyword_in_body(term: str, body: str) -> bool:
    """Stem-aware keyword match — shared with the upstream filter."""
    if not term or not body:
        return False
    return _kw_match_with_index(term, body.lower(), _kw_body_stem_index(body))


def _scrub_detail_payload_bytes(b: bytes) -> bytes:
    """Filter keywords down to the ones that are useful to a kid:
      1. Term must appear (suffix-aware) in the body — no hallucinations.
      2. Term must have a non-empty `explanation` — without a definition
         there's nothing to show on hover/click, so the highlight is
         dead weight (and often a noise word like "Imagine"/"you're"
         from the Python deterministic-extract fallback).

    Returns re-serialized JSON bytes. Never throws — on any parse
    problem we return the input unchanged."""
    try:
        d = json.loads(b)
    except Exception:
        return b
    if not isinstance(d, dict):
        return b
    body = d.get("summary") or ""
    kws = d.get("keywords") or []
    if not isinstance(kws, list):
        return b
    # Build the stem index once per article so each keyword check is
    # an O(stem-set-size) lookup instead of re-tokenising the body.
    body_lc = body.lower()
    body_stems = _kw_body_stem_index(body) if body else set()
    kept, dropped_no_match, dropped_no_def = [], [], []
    for k in kws:
        if not isinstance(k, dict):
            continue
        term = (k.get("term") or "").strip()
        defn = (k.get("explanation") or "").strip()
        if not _kw_match_with_index(term, body_lc, body_stems):
            dropped_no_match.append(term)
            continue
        if not defn:
            dropped_no_def.append(term)
            continue
        kept.append(k)
    if dropped_no_match:
        log.warning("    scrub: dropped %d hallucinated keywords (kept %d): %s",
                    len(dropped_no_match), len(kept), dropped_no_match[:8])
    if dropped_no_def:
        log.warning("    scrub: dropped %d definition-less keywords (kept %d): %s",
                    len(dropped_no_def), len(kept), dropped_no_def[:8])
    d["keywords"] = kept
    return json.dumps(d, ensure_ascii=False).encode()


def build_zip(content_root: Path | None = None) -> bytes:
    buf = BytesIO()
    files = collect_files(content_root=content_root)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p, arc in files:
            # Detail payload? Scrub keywords against the body before
            # the bytes go into the zip. Belt-and-suspenders against
            # any upstream filter_keywords miss.
            if arc.startswith("article_payloads/") and arc.endswith((".json",)) and (
                arc.endswith("/easy.json") or arc.endswith("/middle.json")
            ):
                raw = p.read_bytes()
                cleaned = _scrub_detail_payload_bytes(raw)
                zf.writestr(arc, cleaned)
            else:
                zf.write(p, arcname=arc)
    log.info("Packed %d files (%d bytes)", len(files), buf.tell())
    return buf.getvalue()


def build_manifest(today: str, body: bytes,
                   content_root: Path | None = None) -> dict:
    """Summarize what this zip contains — version + content hash + story IDs.
    Consumers can compare manifest sha256 without downloading the zip."""
    root = content_root or WEB
    stories: list[dict] = []
    for cat in CATS:
        p = root / "payloads" / f"articles_{cat}_middle.json"
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


def _overlay_fresh_categories(old_root: Path, fresh_root: Path,
                              cats: set[str]) -> None:
    """Splice freshly-generated categories into an extracted copy of the
    live bundle (partial-run merge). For each cat in `cats` (lowercase,
    e.g. 'news'): replace its 3 listing files, remove artifacts of the
    replaced story ids (detail dirs / images / PDFs), copy the fresh
    ones in. Everything else in old_root is untouched. A missing fresh
    listing aborts — never publish a bundle with a category-shaped hole."""

    def _ids_imgs(p: Path) -> tuple[set[str], set[str]]:
        ids: set[str] = set()
        imgs: set[str] = set()
        try:
            for a in (json.loads(p.read_text()).get("articles") or []):
                if a.get("id"):
                    ids.add(str(a["id"]))
                if a.get("image_url"):
                    imgs.add(Path(a["image_url"]).name)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"merge: unreadable listing {p}: {e}")
        return ids, imgs

    for cat in sorted(cats):
        old_ids: set[str] = set()
        old_imgs: set[str] = set()
        new_ids: set[str] = set()
        new_imgs: set[str] = set()
        for lvl in ("easy", "middle", "cn"):
            rel = f"payloads/articles_{cat}_{lvl}.json"
            fresh_p = fresh_root / rel
            if not fresh_p.is_file():
                raise SystemExit(f"merge: fresh listing missing: {rel}")
            old_p = old_root / rel
            if old_p.is_file():
                ids, imgs = _ids_imgs(old_p)
                old_ids |= ids
                old_imgs |= imgs
            ids, imgs = _ids_imgs(fresh_p)
            new_ids |= ids
            new_imgs |= imgs
            old_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fresh_p, old_p)
        # Drop artifacts of replaced stories that are NOT re-shipped
        # (same-slot ids overwrite in place below).
        for sid in old_ids - new_ids:
            shutil.rmtree(old_root / "article_payloads" / f"payload_{sid}",
                          ignore_errors=True)
            for pdf in (old_root / "article_pdfs").glob(f"{sid}-*.pdf"):
                pdf.unlink()
        for img in old_imgs - new_imgs:
            old_img = old_root / "article_images" / img
            if old_img.is_file():
                old_img.unlink()
        # Copy the fresh artifacts in.
        for sid in new_ids:
            src = fresh_root / "article_payloads" / f"payload_{sid}"
            if src.is_dir():
                dst = old_root / "article_payloads" / f"payload_{sid}"
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            for pdf in (fresh_root / "article_pdfs").glob(f"{sid}-*.pdf"):
                dst_dir = old_root / "article_pdfs"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf, dst_dir / pdf.name)
        for img in new_imgs:
            src = fresh_root / "article_images" / img
            if src.is_file():
                dst_dir = old_root / "article_images"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst_dir / img)
        log.info("merge: [%s] %d fresh stories in, %d replaced out",
                 cat, len(new_ids), len(old_ids - new_ids))


def _derive_pack_plan(local_counts: dict[str, int],
                      merge_env_cats: set[str] | None = None,
                      ) -> tuple[set[str], set[str], set[str]]:
    """Decide per category what to publish, from local listing article
    counts (middle level). Returns (fresh, short, keep_old):
      fresh:    cats publishing local content (≥1 article; restricted to
                merge_env_cats when a partial run set them)
      short:    fresh cats with <3 articles → top up from previous bundle
      keep_old: cats keeping the previous live content entirely
    Owner rule (2026-07-08): a category should always ship 3 — dig other
    sources first (Stage-3 backfill), then carry over from the previous
    bundle; only a 0-fresh category keeps old content wholesale."""
    pool = set(merge_env_cats) if merge_env_cats else set(local_counts)
    fresh = {c for c in pool if local_counts.get(c, 0) >= 1}
    short = {c for c in fresh if local_counts.get(c, 0) < 3}
    keep_old = set(CATS) - fresh
    return fresh, short, keep_old


def _topup_thin_categories(final_root: Path, old_root: Path,
                           target: int = 3) -> dict[str, list[str]]:
    """Append carried-over stories from the previous live bundle to any
    category whose listings have 1..target-1 articles, until `target`.
    Copies the carried stories' detail payloads / images / PDFs. Pure
    file ops — no LLM, no gate changes. Returns {cat: [carried ids]}."""
    carried: dict[str, list[str]] = {}
    for cat in CATS:
        mid = final_root / "payloads" / f"articles_{cat}_middle.json"
        old_mid = old_root / "payloads" / f"articles_{cat}_middle.json"
        if not (mid.is_file() and old_mid.is_file()):
            continue
        try:
            fresh_arts = json.loads(mid.read_text()).get("articles") or []
            old_arts = json.loads(old_mid.read_text()).get("articles") or []
        except Exception as e:  # noqa: BLE001
            log.warning("topup: [%s] unreadable listing (%s) — skipped", cat, e)
            continue
        if not fresh_arts or len(fresh_arts) >= target:
            continue
        fresh_ids = {a.get("id") for a in fresh_arts}
        cand_ids = [a.get("id") for a in old_arts
                    if a.get("id") and a["id"] not in fresh_ids]
        cand_ids = cand_ids[: target - len(fresh_arts)]
        if not cand_ids:
            continue
        # Splice into every level's listing (old bundle has all levels).
        for lvl in ("easy", "middle", "cn"):
            fp = final_root / "payloads" / f"articles_{cat}_{lvl}.json"
            op = old_root / "payloads" / f"articles_{cat}_{lvl}.json"
            if not (fp.is_file() and op.is_file()):
                continue
            fdoc = json.loads(fp.read_text())
            by_id = {a.get("id"): a
                     for a in json.loads(op.read_text()).get("articles") or []}
            arts = fdoc.get("articles") or []
            for cid in cand_ids:
                if cid in by_id and all(a.get("id") != cid for a in arts):
                    arts.append(by_id[cid])
            fdoc["articles"] = arts[:target]
            fp.write_text(json.dumps(fdoc, ensure_ascii=False))
        # Carry the artifacts.
        img_names: set[str] = set()
        for a in old_arts:
            if a.get("id") in cand_ids and a.get("image_url"):
                img_names.add(Path(a["image_url"]).name)
        for cid in cand_ids:
            src = old_root / "article_payloads" / f"payload_{cid}"
            if src.is_dir():
                dst = final_root / "article_payloads" / f"payload_{cid}"
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            for pdf in (old_root / "article_pdfs").glob(f"{cid}-*.pdf"):
                dst_dir = final_root / "article_pdfs"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf, dst_dir / pdf.name)
        for img in img_names:
            src = old_root / "article_images" / img
            if src.is_file():
                dst_dir = final_root / "article_images"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst_dir / img)
        carried[cat] = cand_ids
        log.info("topup: [%s] carried %s over from previous bundle", cat, cand_ids)
    return carried


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


def restore_latest_from(sb, date_str: str) -> None:
    """One-shot recovery: copy <date>.zip → latest.zip (and the manifest).
    Used when a botched republish or interrupted pipeline left
    latest.zip pointing at content older than the most recent good
    pipeline output. Idempotent."""
    log.info("restore: pulling %s.zip from %s", date_str, BUCKET)
    zip_blob = sb.storage.from_(BUCKET).download(f"{date_str}.zip")
    try:
        manifest_blob = sb.storage.from_(BUCKET).download(f"{date_str}-manifest.json")
    except Exception:
        manifest_blob = None
    sb.storage.from_(BUCKET).upload(
        path="latest.zip", file=zip_blob,
        file_options={"content-type": "application/zip", "upsert": "true"},
    )
    log.info("restore: uploaded latest.zip <= %s.zip (%d bytes)", date_str, len(zip_blob))
    if manifest_blob:
        sb.storage.from_(BUCKET).upload(
            path="latest-manifest.json", file=manifest_blob,
            file_options={"content-type": "application/json", "upsert": "true"},
        )
        log.info("restore: uploaded latest-manifest.json <= %s-manifest.json", date_str)


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Restore mode: short-circuit; just copy a known-good dated zip
    # to latest.zip and exit. No build, no validation.
    restore_date = os.environ.get("PACK_RESTORE_FROM_DATE", "").strip()
    if restore_date:
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        restore_latest_from(sb, restore_date)
        return

    # Republish mode: refresh latest.zip with the CURRENT shell files
    # (HTML/JSX/CSS) from this repo while PRESERVING today's article
    # content from the existing latest.zip on Supabase. Without this
    # preservation step, a republish would clobber freshly-mined
    # articles with whatever stale payloads happen to be committed in
    # git. Skips: bundle validation (today's content lives in remote
    # zip, not local), "remote is newer" guard (same article content),
    # and dated-flat-files / archive-index / retention sweep (those
    # are content-driven, not shell-driven).
    republish = os.environ.get("PACK_REPUBLISH_ONLY") == "1"
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    # Merge / top-up planning: fresh categories publish from local disk;
    # a short category (1-2 articles) is topped up to 3 with carried-over
    # stories from the previous live bundle; a 0-fresh category keeps the
    # previous live content entirely. Full validation still gates the
    # publish — a bad merge refuses to upload and the site keeps its
    # current bundle.
    merge_env = (os.environ.get("PACK_MERGE_CATEGORIES") or "").strip()
    merge_cats = {c.strip().lower() for c in merge_env.split(",") if c.strip()}
    if merge_cats:
        if republish:
            raise SystemExit("PACK_MERGE_CATEGORIES and PACK_REPUBLISH_ONLY "
                             "are mutually exclusive")
        unknown = merge_cats - set(CATS)
        if unknown:
            raise SystemExit(f"PACK_MERGE_CATEGORIES unknown: {sorted(unknown)}")

    content_root: Path | None = None   # None → pack straight from WEB
    if not republish:
        local_counts: dict[str, int] = {}
        for cat in CATS:
            p = WEB / "payloads" / f"articles_{cat}_middle.json"
            if p.is_file():
                try:
                    local_counts[cat] = len(
                        json.loads(p.read_text()).get("articles") or [])
                except Exception:  # noqa: BLE001
                    local_counts[cat] = 0
        fresh, short, keep_old = _derive_pack_plan(local_counts,
                                                   merge_cats or None)
        if not fresh:
            raise SystemExit("no fresh category content on disk — "
                             "nothing to publish")
        if keep_old or short:
            import tempfile
            old_root = Path(tempfile.mkdtemp(prefix="pack_old_"))
            try:
                blob = sb.storage.from_(BUCKET).download("latest.zip")
            except Exception as e:  # noqa: BLE001
                if keep_old or any(local_counts.get(c, 0) < 2 for c in fresh):
                    # Can't ship a bundle with a category-shaped hole.
                    raise SystemExit(
                        f"pack needs the live latest.zip for merge/top-up: {e}")
                log.warning("top-up skipped — no previous bundle (%s); "
                            "shipping %s with <3 articles", e, sorted(short))
            else:
                with zipfile.ZipFile(BytesIO(blob)) as zf:
                    for info in zf.infolist():
                        top = info.filename.split("/", 1)[0]
                        if top in CONTENT_DIRS:
                            zf.extract(info, old_root)
                # Final bundle starts as the old content; fresh categories
                # overlay it; short ones borrow back from old_root.
                merge_root = Path(tempfile.mkdtemp(prefix="pack_merge_"))
                for d in CONTENT_DIRS:
                    if (old_root / d).is_dir():
                        shutil.copytree(old_root / d, merge_root / d)
                _overlay_fresh_categories(merge_root, WEB, fresh)
                carried = _topup_thin_categories(merge_root, old_root)
                if keep_old:
                    log.warning("pack: %s keep previous live content",
                                sorted(keep_old))
                if carried:
                    log.warning("pack: topped up %s with carried-over stories",
                                {c: len(v) for c, v in carried.items()})
                content_root = merge_root

    if republish:
        # Pull current latest.zip and extract CONTENT_DIRS to a temp dir
        # so build_zip() can read content from there + shell from WEB.
        import tempfile
        tmp = tempfile.mkdtemp(prefix="pack_republish_")
        content_root = Path(tmp)
        try:
            blob = sb.storage.from_(BUCKET).download("latest.zip")
            with zipfile.ZipFile(BytesIO(blob)) as zf:
                # Only extract CONTENT_DIRS — shell files in the existing
                # zip are stale by definition (that's why we're republishing).
                for info in zf.infolist():
                    top = info.filename.split("/", 1)[0]
                    if top in CONTENT_DIRS:
                        zf.extract(info, tmp)
            log.info("republish: extracted content from existing latest.zip into %s", tmp)
        except Exception as e:
            # No remote latest.zip yet (first deploy) → fall back to local.
            log.warning("republish: could not pull existing latest.zip (%s); falling back to local content", e)
            content_root = None
        body = build_zip(content_root=content_root)
    else:
        validate_bundle(today, content_root=content_root)
        body = build_zip(content_root=content_root)

    manifest = build_manifest(today, body,
                              content_root=None if republish else content_root)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    if not republish:
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

    if republish:
        # Republish: skip dated-flat-files + archive-index updates +
        # retention sweep — none of those change when only static assets
        # are refreshed. Same article content, just new HTML/JSX/CSS.
        pub = f"{os.environ['SUPABASE_URL']}/storage/v1/object/public/{BUCKET}/latest.zip"
        log.info("republish: skipped dated-flat / archive-index / retention. public URL: %s", pub)
        return

    # Flat per-day files — the UI fetches these when user picks a past date.
    # Only add `today` to archive-index AFTER all flat files are confirmed
    # present, so DatePopover never advertises a date whose payloads 404.
    today_flat_ok = False
    try:
        # Extract from the just-built zip so dated flats always match the
        # published bundle exactly (incl. merged/topped-up categories and
        # scrubbed detail payloads).
        n = upload_dated_flat_files(sb, today, bundle=body)
        today_flat_ok = n > 0
    except Exception as e:  # noqa: BLE001
        log.warning("dated-flat upload failed (non-fatal for today's deploy): %s", e)

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
        new_dates: list[str] = []
        if today_flat_ok:
            new_dates.append(today)
        new_dates.extend(backfilled)  # backfill function only returns successes
        if new_dates:
            update_archive_index(sb, new_dates)
        else:
            log.info("archive-index: no new dates to register")
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
