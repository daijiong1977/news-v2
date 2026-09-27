"""Read-only live probe of DeepSeek word-count repair on published articles.

Fetches public payloads and source text, calls the same repair and independent
safety functions as the pipeline, and prints counts only. Never uploads,
persists, or replaces published content.

Example:
  python -m scripts.probe_wordcount_repair --env-file /path/to/.env \
    2026-09-25-fun-2 2026-09-26-science-3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.request import urlopen


def _payload(base: str, sid: str, level: str) -> dict:
    date = sid[:10]
    url = (f"{base}/storage/v1/object/public/redesign-daily-content/"
           f"{date}/article_payloads/payload_{sid}/{level}.json")
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Local env file; values are never printed")
    parser.add_argument("story_ids", nargs="+", help="Published story IDs to probe")
    args = parser.parse_args()

    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("SUPABASE_URL"):
        parser.error("DEEPSEEK_API_KEY and SUPABASE_URL must be available")

    from pipeline import news_rss_core as core
    from pipeline.forbidden_filter import is_forbidden

    base = os.environ["SUPABASE_URL"].rstrip("/")
    failed = False
    for sid in args.story_ids:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-(news|science|fun)-\d+", sid):
            parser.error(f"invalid story ID: {sid}")
        try:
            middle = _payload(base, sid, "middle")
            easy = _payload(base, sid, "easy")
            original = middle.get("summary") or ""
            before = len(original.split())
            source_body = ""
            if before < core.WC_BANDS["middle"][0]:
                source_url = middle.get("source_url") or ""
                if source_url:
                    source_body = core.process_entry({"link": source_url}, min_words=0).get("body") or ""
                if len(source_body.split()) < 250:
                    print(json.dumps({"id": sid, "before": before,
                                      "skipped": "source body unavailable for safe expansion"}))
                    failed = True
                    continue

            result = {"articles": [{"source_id": 0,
                                    "middle_en": {"body": original},
                                    "easy_en": {}}]}
            attempts: list[dict] = []
            original_call = core.deepseek_call

            def traced_call(system, user, **kwargs):
                start = time.monotonic()
                output = original_call(system, user, **kwargs)
                returned_body = ((output or {}).get("body") or "")
                attempts.append({"words": len(returned_body.split()),
                                 "identical_to_original": returned_body.strip() == original.strip(),
                                 "seconds": round(time.monotonic() - start, 2)})
                return output

            core.deepseek_call = traced_call
            start = time.monotonic()
            try:
                core.repair_wordcounts(result, {0: {"body": source_body}})
            finally:
                core.deepseek_call = original_call
            revised = result["articles"][0]["middle_en"]["body"]
            after = len(revised.split())
            in_ideal = core.WC_BANDS["middle"][0] <= after <= core.WC_BANDS["middle"][1]
            in_qa = core._wc_within_qa("middle", after)
            safety = "not run"
            if revised != original and in_qa:
                bad, _ = is_forbidden(revised)
                if bad:
                    safety = "REJECT: forbidden term"
                else:
                    reviewed = core.independent_safety_vet([{
                        "source_id": 0,
                        "middle_en": {"body": revised},
                        "easy_en": {"body": easy.get("summary") or ""},
                    }])
                    safety = (core.evaluate_rewriter_safety({"safety": reviewed[0]})["verdict"]
                              if 0 in reviewed else "NO INDEPENDENT VERDICT")
            print(json.dumps({"id": sid, "before": before,
                              "source_words": len(source_body.split()),
                              "attempts": attempts, "after": after,
                              "in_ideal": in_ideal, "in_qa": in_qa,
                              "independent_safety": safety,
                              "total_seconds_including_safety": round(time.monotonic() - start, 2)}))
            failed = failed or not in_qa or safety not in ("PASS", "not run")
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"id": sid, "error": str(exc)}))
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
