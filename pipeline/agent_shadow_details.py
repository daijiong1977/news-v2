"""Reader enrichment and local images; no model API or database writes."""
from pathlib import Path
import time


def validate_details(value, entries):
    from .news_rss_core import keyword_in_body
    expected = {f"{i}_{level}" for i in entries for level in ("easy", "middle")}
    slots = value.get("details", {})
    if not isinstance(slots, dict) or set(slots) != expected:
        return ["details keys must match exactly: " + ", ".join(sorted(expected))]
    errors = []
    for key, detail in slots.items():
        if not isinstance(detail, dict):
            errors.append(f"{key}: detail object required")
            continue
        i, level = key.split("_")
        body = entries[int(i)][f"{level}_en"]["body"]
        keywords = detail.get("keywords")
        if not isinstance(keywords, list) or len(keywords) > 6:
            errors.append(f"{key}: zero to six keywords required")
        else:
            for kw in keywords:
                if (not isinstance(kw, dict) or not isinstance(kw.get("term"), str)
                        or not kw["term"].strip() or not keyword_in_body(kw["term"], body)
                        or not isinstance(kw.get("explanation"), str) or not kw["explanation"].strip()):
                    errors.append(f"{key}: keyword must occur in this slot's body with an explanation")
        questions = detail.get("questions")
        if not isinstance(questions, list) or len(questions) != 6:
            errors.append(f"{key}: six questions required")
        else:
            for q in questions:
                if (not isinstance(q, dict) or not isinstance(q.get("question"), str)
                        or not q["question"].strip() or not isinstance(q.get("options"), list)
                        or len(q["options"]) != 4 or len(set(q["options"])) != 4
                        or any(not isinstance(o, str) or not o.strip() for o in q["options"])
                        or q.get("correct_answer") not in q["options"]):
                    errors.append(f"{key}: question needs four distinct string options and a matching answer")
        for field in ("background_read", "Article_Structure"):
            values = detail.get(field)
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                errors.append(f"{key}: {field} needs nonempty strings")
        if not isinstance(detail.get("why_it_matters"), str) or not detail["why_it_matters"].strip():
            errors.append(f"{key}: why_it_matters required")
        perspectives = detail.get("perspectives")
        if not isinstance(perspectives, list) or not perspectives or any(
                not isinstance(p, dict) or any(not isinstance(p.get(k), str) or not p[k].strip()
                for k in ("perspective", "description")) for p in perspectives):
            errors.append(f"{key}: perspectives need perspective/description strings")
    return errors


def enrich_and_review(root, final, variants, ask, boundary, stepwise):
    from .agent_shadow import read, write
    from .news_rss_core import (DETAIL_ENRICH_PROMPT, _detail_enrich_input_per_category,
                               SAFETY_VET_PROMPT, SAFETY_DIMS, evaluate_rewriter_safety)
    result = {}
    for cat, stories in final.items():
        result[cat] = {}
        for i, story in enumerate(stories):
            sid = story["winner"]["id"]
            entry = variants[cat][i]
            # Per story keeps the independent review small and prevents slot shifts.
            details = ask(root, f"details-{cat}-{sid}", DETAIL_ENRICH_PROMPT,
                          _detail_enrich_input_per_category({"articles": [entry]}, cat, [0]),
                          lambda v: validate_details(v, {0: entry}))["details"]
            boundary(root, f"details-{cat}-{sid}", stepwise)
            def check(v):
                scores = v.get("scores", {}).get("0", {})
                return [] if (type(v.get("facts_supported")) is bool and all(
                    type(scores.get(d)) in (int, float) and 0 <= scores[d] <= 5 for d in SAFETY_DIMS)) else [
                        "Return eight scores for 0, 0..5, and facts_supported boolean"]
            review = ask(root, f"review-details-{cat}-{sid}", SAFETY_VET_PROMPT +
                         '\nReview ALL enrichment, quizzes, explanations and viewpoints, not just the body. '
                         'Check quiz answers and source support. Set facts_supported false for invented '
                         'viewpoints or unsupported specifics. Return facts_supported boolean too.',
                         {"source": story["winner"]["body"], "article": entry, "details": details}, check)
            safe = evaluate_rewriter_safety({"safety": review["scores"]["0"]}, category=cat)
            path = root / "detail-reviews.json"
            report = read(path) if path.exists() else {}
            passed = safe["verdict"] == "PASS" and review["facts_supported"]
            report[f"{cat}-{sid}"] = {"passed": passed, "safety": safe, "facts_supported": review["facts_supported"]}
            write(path, report)
            boundary(root, f"review-details-{cat}-{sid}", stepwise)
            # Fail closed on extra material; a safe body can still ship without enrichment.
            if passed:
                for level in ("easy", "middle"):
                    result[cat][f"{i}_{level}"] = details[f"0_{level}"]
    return result


def images(root, final, boundary, stepwise):
    from .agent_shadow import read, write
    from .image_optimize import fetch_and_optimize
    path = root / "image-results.json"
    cache = read(path) if path.exists() else {}
    for cat, stories in final.items():
        for story in stories:
            sid = story["winner"]["id"]
            relative = f"article_images/{cat.lower()}-{sid}.webp"
            if sid not in cache:
                started = time.monotonic()
                result = fetch_and_optimize(story["winner"].get("og_image", ""), root / "reader" / relative)
                cache[sid] = {"ok": bool(result), "info": result,
                              "seconds": round(time.monotonic() - started, 3)}
                write(path, cache)
                boundary(root, f"image-{sid}", stepwise, started)
            story["_image_local"] = relative if cache[sid]["ok"] else ""
