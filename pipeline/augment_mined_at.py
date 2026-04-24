"""Augment existing payload JSON files with `mined_at` (+ source_published_at
+ source_name + source_url) pulled from the redesign_stories DB rows.

One-shot helper used when rolling out mined_at support to already-generated
payloads. Safe to re-run: only writes when a field would actually change."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("augment")

_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        k, v = _line.strip().split("=", 1)
        os.environ[k] = v

WEB = Path(__file__).resolve().parent.parent / "website"


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    rows = sb.table("redesign_stories").select(
        "payload_story_id, created_at, source_published_at, source_name, source_url, category"
    ).eq("published_date", today).execute().data or []
    by_id = {r["payload_story_id"]: r for r in rows if r.get("payload_story_id")}
    log.info("Loaded %d stories from DB for %s", len(by_id), today)

    patched = 0

    # Listings
    for cat in ("news", "science", "fun"):
        for lvl in ("easy", "middle", "cn"):
            p = WEB / "payloads" / f"articles_{cat}_{lvl}.json"
            if not p.is_file():
                continue
            doc = json.loads(p.read_text())
            changed = False
            for a in doc.get("articles") or []:
                r = by_id.get(a.get("id"))
                if not r:
                    continue
                for dst, src in (("mined_at", "created_at"),
                                 ("source_published_at", "source_published_at")):
                    v = r.get(src)
                    if v and a.get(dst) != v:
                        a[dst] = v
                        changed = True
            if changed:
                p.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
                patched += 1

    # Detail payloads (easy + middle)
    for story_id, r in by_id.items():
        story_dir = WEB / "article_payloads" / f"payload_{story_id}"
        if not story_dir.is_dir():
            continue
        for lvl in ("easy", "middle"):
            p = story_dir / f"{lvl}.json"
            if not p.is_file():
                continue
            d = json.loads(p.read_text())
            changed = False
            patch = {
                "mined_at": r.get("created_at") or "",
                "source_published_at": r.get("source_published_at") or "",
                "source_name": r.get("source_name") or "",
                "source_url": r.get("source_url") or "",
            }
            for k, v in patch.items():
                if v and d.get(k) != v:
                    d[k] = v
                    changed = True
            if changed:
                p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
                patched += 1

    log.info("Patched %d files with mined_at + source metadata", patched)


if __name__ == "__main__":
    main()
