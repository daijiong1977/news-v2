"""One-shot: for each current listing payload, generate a 6-9 sentence
card_summary (≤120 words) from the full body via DeepSeek, and overwrite the
`summary` field in-place. Chinese listings are left untouched (already a
summary)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .news_rss_core import deepseek_call
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")

_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        k, v = _line.strip().split("=", 1)
        os.environ[k] = v

ROOT = (_REPO_ROOT / "website/payloads")

CARD_PROMPT = """You write blurbs that appear on news home-page cards for kids.
Given ONE kid-friendly news article body, write a 6-9 sentence card summary.
Rules:
  · MAX 120 words total (count silently; do not exceed)
  · Open with a hook, then cover WHO / WHAT / WHERE / WHY
  · Include 1-3 concrete details (names, numbers, places) from the body
  · Voice: curious kid reporter — NOT a dry wire-service summary
  · Plain English at the article's grade level
  · NEVER invent facts — only use what's in the body
  · End with punctuation

OUTPUT — valid JSON only (no markdown): {"card_summary": "..."}"""


def one(body: str, title: str) -> str:
    user = f"TITLE: {title}\n\nBODY:\n{body}\n\nReturn JSON with card_summary."
    out = deepseek_call(CARD_PROMPT, user, max_tokens=500, temperature=0.4)
    return (out.get("card_summary") or "").strip()


def main() -> None:
    # Only English variants have full-body summary problem; cn is already short.
    targets = []
    for cat in ("news", "science", "fun"):
        for lvl in ("easy", "middle"):
            p = ROOT / f"articles_{cat}_{lvl}.json"
            if p.exists():
                targets.append(p)
    log.info("Backfilling %d files", len(targets))

    for p in targets:
        doc = json.loads(p.read_text())
        arts = doc.get("articles") or []
        for a in arts:
            body = a.get("summary") or ""
            # Heuristic: if already ≤130 words, skip
            if len(body.split()) <= 130:
                log.info("  skip (already short): %s", a.get("id"))
                continue
            cs = one(body, a.get("title") or "")
            if cs:
                words = cs.split()
                if len(words) > 120:
                    cs = " ".join(words[:120]).rstrip(",;:") + "…"
                a["summary"] = cs
                log.info("  %s → %d words", a.get("id"), len(cs.split()))
            else:
                log.warning("  EMPTY response for %s — keeping original", a.get("id"))
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        log.info("wrote %s", p.name)


if __name__ == "__main__":
    main()
