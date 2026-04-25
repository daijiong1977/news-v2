"""Test DeepSeek reasoner (thinking mode) on the 3 existing News articles.

Produces enhanced background_read + Article_Structure (mind-tree) + perspectives
using deepseek-reasoner. Writes outputs to payload_*/middle.enhanced.json
alongside existing middle.json for side-by-side comparison.

Run: python -m pipeline.test_thinking_enrich
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import requests
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("thinking-test")

_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
ENDPOINT = "https://api.deepseek.com/chat/completions"

ENHANCED_PROMPT = """You are enriching a kids news article for a 12-year-old middle-schooler.
Use careful reasoning: the reader already has the article body; you are adding
DEPTH that the article alone doesn't provide.

You will receive 3 middle-school articles (bodies already rewritten at grade 7-8 level).
For EACH article's `middle_en` body, produce:

1. `background_read` — array of 3-5 sentences. REQUIREMENTS:
   · Add context that is NOT already in the article.
   · Include specific historical facts, related events, or concepts
     a 12-year-old might not know. Define new terms briefly when used.
   · NO generic filler like "this is from PBS" or "journalists talk to people".
   · NO repeating what the article already says.
   · Example for a story about election betting: "Prediction markets have existed
     since the 1990s. The famous Iowa Electronic Markets let traders bet on
     presidential outcomes. In 2022, the CFTC first approved Kalshi for election
     contracts after years of debate about whether this counted as gambling."

2. `Article_Structure` — a MIND-TREE showing how THIS article is constructed.
   Array of strings, each representing a tree node. Use indentation via leading
   spaces + tree characters (└─, ├─). Example:
   [
     "LEAD: surprising fact or hook",
     "  └─ specifically: '<quote or detail from article>'",
     "KEY EVENT: what happened",
     "  ├─ WHO: specific people",
     "  ├─ WHEN: date / timeline",
     "  └─ HOW MUCH: quantities, amounts",
     "TENSION: conflict or question",
     "  ├─ ONE SIDE: viewpoint A",
     "  └─ OTHER SIDE: viewpoint B",
     "EVIDENCE: what backs it up",
     "  └─ QUOTE: direct speech from the article",
     "OPEN QUESTION: what remains unresolved"
   ]
   Reflect the ACTUAL structure of this article; don't force a template.

3. `perspectives` — array of 4 {perspective, description} objects. Each must be
   a DISTINCT angle:
   · One POSITIVE view: who benefits, what's gained
   · One NEGATIVE / CRITICAL view: who's harmed, what's concerning
   · One NEUTRAL / ANALYTICAL view: systemic observation, historical pattern
   · One FORWARD-LOOKING view: what could / should happen next; what to do
   Each `description` 2-3 sentences exploring tension or nuance —
   not a summary of the article.

IMPORTANT: keywords and questions are unchanged — DO NOT return them.

ACCURACY: facts you add in `background_read` must be real-world accurate.
If you aren't sure, prefer general pattern statements over specific claims.

Return ONLY valid JSON (no markdown fences):
{
  "0_middle": {"background_read":[...], "Article_Structure":[...], "perspectives":[...]},
  "1_middle": {"background_read":[...], "Article_Structure":[...], "perspectives":[...]},
  "2_middle": {"background_read":[...], "Article_Structure":[...], "perspectives":[...]}
}"""


def build_user_message(articles: list[dict]) -> str:
    lines = ["3 articles below. Enhance detail fields for the middle_en variant.", ""]
    for i, a in enumerate(articles):
        lines.append(f"=== Article [id: {i}_middle] ===")
        lines.append(f"Headline: {a['headline']}")
        lines.append(f"Body ({len(a['body'].split())} words):")
        lines.append(a["body"])
        lines.append("")
    return "\n".join(lines)


def call_reasoner(user_msg: str) -> tuple[str, str]:
    """Call deepseek-reasoner. Returns (reasoning, content)."""
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": ENHANCED_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 8000,
    }
    r = requests.post(ENDPOINT, json=payload,
                      headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
                      timeout=300)
    r.raise_for_status()
    data = r.json()
    choice = data["choices"][0]["message"]
    return choice.get("reasoning_content", ""), choice.get("content", "")


def main() -> None:
    details_dir = (_REPO_ROOT / "website/article_payloads")
    # Load the 3 News middle articles
    articles = []
    for slot in (1, 2, 3):
        f = details_dir / f"payload_2026-04-24-news-{slot}" / "middle.json"
        data = json.loads(f.read_text())
        articles.append({
            "slot": slot,
            "headline": data.get("title", ""),
            "body": data.get("summary", ""),
        })
        log.info("News #%d middle: %d words · %s", slot,
                 len(articles[-1]["body"].split()),
                 articles[-1]["headline"][:60])

    log.info("Calling deepseek-reasoner (thinking mode) — may take 60-120s ...")
    reasoning, content = call_reasoner(build_user_message(articles))

    # Strip fences if any
    content = re.sub(r"^```json\s*", "", content.strip())
    content = re.sub(r"\s*```\s*$", "", content)

    log.info("Reasoning length: %d chars", len(reasoning))
    log.info("Content length: %d chars", len(content))

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s\nContent: %s", e, content[:500])
        return

    # Write side-by-side
    for slot in (1, 2, 3):
        key = f"{slot-1}_middle"
        det = result.get(key) or {}
        if not det:
            log.warning("No detail for %s", key)
            continue
        out = details_dir / f"payload_2026-04-24-news-{slot}" / "middle.enhanced.json"
        out.write_text(json.dumps(det, ensure_ascii=False, indent=2))
        log.info("  wrote %s — bg=%d, structure=%d, perspectives=%d",
                 out.name,
                 len(det.get("background_read") or []),
                 len(det.get("Article_Structure") or []),
                 len(det.get("perspectives") or []))

    # Save the reasoning trace for debug
    reasoning_path = Path("/tmp/thinking_reasoning.txt")
    reasoning_path.write_text(reasoning)
    log.info("Reasoning saved to %s", reasoning_path)

    print("\n=== SAMPLE News #1 middle.enhanced.json ===")
    print(json.dumps(result.get("0_middle") or {}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
