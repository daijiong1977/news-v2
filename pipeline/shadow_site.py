"""Export generated reader payloads to an isolated static shadow deployment.

No database writes, emails, latest.zip upload, or production deploy. Run with:
python -m pipeline.shadow_site --content-dir DIR --date YYYY-MM-DD --provider NAME --output NEW_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "shadow" / "site"
CATEGORIES = ("news", "science", "fun")
LEVELS = ("easy", "middle", "cn")


def export(content_dir: Path, output: Path, run_date: str, provider: str) -> dict:
    date.fromisoformat(run_date)
    if not provider.strip():
        raise ValueError("provider is required")
    source = content_dir.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError("output must be a new directory; existing content is never overwritten")
    files = {}
    counts = {}

    def add(relative: str) -> bytes:
        target = (source / relative).resolve()
        if not target.is_relative_to(source) or not target.is_file():
            raise ValueError(f"missing or unsafe file: {relative}")
        data = target.read_bytes()
        files[relative] = data
        return data

    for cat in CATEGORIES:
        previous_ids = None
        for lvl in LEVELS:
            listing = json.loads(add(f"payloads/articles_{cat}_{lvl}.json"))
            items = listing["articles"]
            if not isinstance(items, list) or len(items) > 3:
                raise ValueError(f"{cat}/{lvl}: expected zero to three articles")
            ids = []
            for item in items:
                story_id = item["id"]
                if not re.fullmatch(re.escape(run_date) + f"-{cat}-[1-9][0-9]*", story_id):
                    raise ValueError(f"wrong date/category or unsafe story id: {story_id}")
                if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("title", "summary", "source")):
                    raise ValueError(f"{story_id}: title, summary and source are required")
                ids.append(story_id)
                image = item.get("image_url") or ""
                if image:
                    if not re.fullmatch(r"/article_images/[A-Za-z0-9_.-]+\.(webp|png|jpg|jpeg)", image):
                        raise ValueError(f"{story_id}: image must be local to the exported site")
                    add(image.lstrip("/"))
                if lvl != "cn":
                    detail = json.loads(add(f"article_payloads/payload_{story_id}/{lvl}.json"))
                    if not isinstance(detail.get("summary"), str) or not detail["summary"].strip():
                        raise ValueError(f"{story_id}/{lvl}: full body missing")
            if len(set(ids)) != len(ids) or (previous_ids is not None and set(ids) != previous_ids):
                raise ValueError(f"{cat}: duplicate or mismatched IDs across reading levels")
            previous_ids = set(ids)
        counts[cat] = len(previous_ids)
    content_hash = hashlib.sha256()
    for name, data in sorted(files.items()):
        content_hash.update(name.encode() + b"\0" + data + b"\0")
    manifest = {"schema_version": 1, "status": "shadow_review", "date": run_date,
                "provider": provider, "counts": counts, "content_hash": content_hash.hexdigest(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "review": "unverified", "production_published": False}
    output.mkdir(parents=True)
    for name in ("index.html", "app.js", "style.css", "vercel.json", "robots.txt"):
        shutil.copyfile(TEMPLATE / name, output / name)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "shadow-run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, **export(args.content_dir, args.output, args.date, args.provider)}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
