"""Compare tri-variant rewrite: deepseek-chat (current) vs deepseek-reasoner (thinking).

Uses the same TRI_VARIANT_REWRITER_PROMPT for both. Runs on the 3 current News
stories' source bodies. Writes outputs to middle.rewrite-thinking.json and
easy.rewrite-thinking.json alongside existing. Prints side-by-side samples.

Run: python -m pipeline.test_thinking_rewrite
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from supabase import create_client

from .cleaner import extract_article_from_html
from .news_rss_core import TRI_VARIANT_REWRITER_PROMPT, tri_variant_rewriter_input

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rewrite-test")

for _line in open("/Users/jiong/myprojects/news-v2/.env"):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]
ENDPOINT = "https://api.deepseek.com/chat/completions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def fetch_body(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.ok:
            ex = extract_article_from_html(url, r.text)
            return ex.get("cleaned_body") or ""
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
    return ""


def reasoner_rewrite(articles_with_ids: list) -> dict:
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": TRI_VARIANT_REWRITER_PROMPT},
            {"role": "user", "content": tri_variant_rewriter_input(articles_with_ids)},
        ],
        "max_tokens": 12000,
    }
    r = requests.post(ENDPOINT, json=payload,
                      headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
                      timeout=300)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    content = re.sub(r"^```json\s*", "", content.strip())
    content = re.sub(r"\s*```\s*$", "", content)
    return json.loads(content)


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    res = sb.table("redesign_stories").select("*").eq("published_date", today)\
        .eq("category", "News").order("story_slot").execute()
    stories = res.data
    log.info("Loaded %d News stories from DB", len(stories))

    log.info("Re-fetching source bodies ...")
    arts = []
    for i, s in enumerate(stories):
        body = fetch_body(s["source_url"])
        arts.append((i, {
            "title": s.get("source_title") or "",
            "link": s.get("source_url") or "",
            "published": "",
            "body": body,
        }))
        log.info("  [News #%d] %d source words · %s", i + 1, len(body.split()),
                 s.get("source_title", "")[:55])

    log.info("Calling deepseek-reasoner tri-variant rewrite (~2-3 min) ...")
    res_thinking = reasoner_rewrite(arts)
    out_articles = res_thinking.get("articles") or []
    log.info("Got %d rewritten articles", len(out_articles))

    # Save side-by-side
    details_dir = Path("/Users/jiong/myprojects/news-v2/website/article_payloads")
    for i, a in enumerate(out_articles):
        sid = a.get("source_id", i)
        slot = sid + 1
        easy = a.get("easy_en") or {}
        middle = a.get("middle_en") or {}
        zh = a.get("zh") or {}
        story_dir = details_dir / f"payload_{today}-news-{slot}"
        (story_dir / "easy.rewrite-thinking.json").write_text(
            json.dumps(easy, ensure_ascii=False, indent=2))
        (story_dir / "middle.rewrite-thinking.json").write_text(
            json.dumps(middle, ensure_ascii=False, indent=2))
        (story_dir / "zh.rewrite-thinking.json").write_text(
            json.dumps(zh, ensure_ascii=False, indent=2))
        log.info("  #%d: easy=%dw · middle=%dw · zh=%d字",
                 slot,
                 len((easy.get("body") or "").split()),
                 len((middle.get("body") or "").split()),
                 len(zh.get("summary") or ""))

    # Print side-by-side for the first story
    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE: News #1 easy_en")
    print("=" * 80)
    existing_easy = json.loads(
        (details_dir / f"payload_{today}-news-1" / "easy.json").read_text()
    )
    new_easy = out_articles[0].get("easy_en") or {}
    print(f"\n--- CURRENT (deepseek-chat) ---  {len((existing_easy.get('summary') or '').split())} words")
    print(f"Headline: {existing_easy.get('title', '')}")
    print(f"\n{existing_easy.get('summary', '')}")
    print(f"\nWhy matters: {existing_easy.get('why_it_matters', '')}")
    print(f"\n--- NEW (deepseek-reasoner) ---  {len((new_easy.get('body') or '').split())} words")
    print(f"Headline: {new_easy.get('headline', '')}")
    print(f"\n{new_easy.get('body', '')}")
    print(f"\nWhy matters: {new_easy.get('why_it_matters', '')}")

    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE: News #1 middle_en")
    print("=" * 80)
    existing_middle = json.loads(
        (details_dir / f"payload_{today}-news-1" / "middle.json").read_text()
    )
    new_middle = out_articles[0].get("middle_en") or {}
    print(f"\n--- CURRENT (deepseek-chat) ---  {len((existing_middle.get('summary') or '').split())} words")
    print(f"Headline: {existing_middle.get('title', '')}")
    print(f"\n{existing_middle.get('summary', '')}")
    print(f"\n--- NEW (deepseek-reasoner) ---  {len((new_middle.get('body') or '').split())} words")
    print(f"Headline: {new_middle.get('headline', '')}")
    print(f"\n{new_middle.get('body', '')}")


if __name__ == "__main__":
    main()
