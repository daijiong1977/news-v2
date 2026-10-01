"""Persisted per-section editor. Top-ups never replay accepted stories or settled sections."""
import re
import time
from .agent_shadow_profiles import is_hybrid, is_batch, uses_native_details


def validate_rewrite(value, cat, word_count):
    from .agent_shadow_lengths import rewrite_band
    entries = value.get("articles", [])
    if len(entries) != 1 or entries[0].get("source_id") != 0:
        return ["Return exactly one article with source_id 0"]
    entry, errors = entries[0], []
    for level in ("easy_en", "middle_en"):
        if any(not isinstance(entry.get(level, {}).get(k), str) or not entry[level][k].strip()
               for k in ("headline", "body", "card_summary")):
            errors.append(f"{level}: headline, body, card_summary required")
    if any(not isinstance(entry.get("zh", {}).get(k), str) or not entry["zh"][k].strip()
           for k in ("headline", "summary")):
        errors.append("zh headline and summary required")
    if errors:
        return errors
    for level in ('easy', 'middle'):
        lo, hi = rewrite_band(level, cat, word_count)
        count = len(entry[f'{level}_en']['body'].split())
        if not lo <= count <= hi:
            errors.append(f'{level}: {count}w outside {lo}-{hi}')
    return errors


def edit(root, snapshot, ranked, ask, boundary, stepwise, *, policy=None):
    from .agent_shadow import read, write, body_pool, AnswerRejected, pin_task_answers, CATS
    from .news_rss_core import (TRI_VARIANT_REWRITER_PROMPT, tri_variant_rewriter_input,
                               SAFETY_VET_PROMPT, SAFETY_DIMS, evaluate_rewriter_safety)
    from .news_sources import NewsSource
    from .editorial_policy import publisher_key
    state_path, refill_path = root / "editor-state.json", root / "backfill.json"
    state = read(state_path) if state_path.exists() else {
        cat: {"accepted": [], "outcomes": [], "order": [], "pool_ids": [], "pick_done": False} for cat in CATS}
    targets = read(refill_path).get("targets") if refill_path.exists() else {cat: (8 if is_batch(snapshot) else 3 if policy else 6) for cat in CATS}
    if not targets:
        raise ValueError("legacy global backfill state cannot be resumed; use a fresh run directory")
    hybrid = is_hybrid(snapshot)
    if hybrid:
        from .agent_shadow_modifier import english_errors
        # Resume the already accepted mixed-language draft without changing its pinned answer.
        for cat, section in state.items():
            retained = []
            for accepted in section["accepted"]:
                if english_errors(accepted["entry"]):
                    sid = accepted['candidate']['id']
                    section['outcomes'].append({'id': sid, 'category': cat,
                        'status': 'needs_modifier', 'facts_supported': False, 'event_clear': True})
                else:
                    retained.append(accepted)
            section['accepted'] = retained
    write(refill_path, {"targets": targets})
    def save():
        write(state_path, state)
        write(root / "review-results.json", {"outcomes": [o for c in CATS for o in state[c]["outcomes"]],
                                             "warnings": [], "review_method": "第二模型修稿并自检；无第三轮审核" if hybrid else ("第二遍审核；模型见 provider-audit（原生默认同模型）" if policy else "同模型第二遍审核")})
    def source_of(item):
        return NewsSource(**snapshot["sources"][item["article"]["source"]])
    def publishers(section):
        return {publisher_key(source_of(a["candidate"])) for a in section["accepted"]}
    def needs(cat, section):
        if len(section['accepted']) < 3:
            return True
        tried = {o['id'] for o in section['outcomes']}
        remaining = [b for b in ranked[cat] if b['id'] not in tried
                     and b['history_status'] == 'clear' and b['history_confidence'] >= .7
                     and b['initial_risk'] < 4]
        if policy and cat == 'News' and not any(a['candidate']['importance'] >= 3 for a in section['accepted']):
            return any(b['importance'] >= 3 for b in remaining)
        if cat == 'Science' and len(publishers(section)) < 2:
            index = {b['id']: b for b in snapshot['candidates']}
            return any(publisher_key(NewsSource(**snapshot['sources'][index[b['id']]['source']]))
                       not in publishers(section) for b in remaining if b['id'] in index)
        return False
    save()
    active = snapshot.get("active_categories", CATS)
    for cat in active:
        section = state[cat]
        while needs(cat, section):
            target = targets[cat]
            pool_path = root / f"pool-{cat}-{target}.json"
            started = time.monotonic()
            if not pool_path.exists():
                write(pool_path, policy.pool(cat, target) if policy else body_pool(root, snapshot, {cat: ranked[cat]}, min_good=target)[cat])
            boundary(root, f"originals-{cat}-{target}", stepwise, started)
            pool = read(pool_path)
            index = {b["id"]: b for b in pool}
            # Initial six are frozen; top-up ranks ONLY newly opened eligible candidates.
            new = [b for b in pool if b["id"] not in section["pool_ids"]]
            if not section["pick_done"] or new:
                key = (f"selections-{cat}-{target}" if policy else
                       f"pick-{cat}" if not section["pick_done"] else f"pick-{cat}-refill-{target}")
                six = new[:6]
                ids = {b["id"] for b in six}
                if policy:
                    section["order"].extend(b["id"] for b in new)
                elif six:
                    def check_pick(value):
                        order = value.get("order", [])
                        return [] if (isinstance(order, list) and len(order) == len(ids) and set(order) == ids) else [
                            "order must list every supplied ID exactly once"]
                    prompt = ('Pick the best three, then rank reserves. Return JSON {"order":["c001"]} '
                              'listing EVERY supplied ID exactly once. Prefer diverse topics and publishers. '
                              'Reserve one important News (importance>=3) if supplied. Science needs two publishers. '
                              'For refill, these are ONLY new candidates; existing accepted articles stay fixed. No browsing.')
                    order = ask(root, key, prompt,
                        [{"id": b["id"], "title": b["article"]["title"], "excerpt": b["article"]["body"][:1800],
                          "source": b["article"]["source"], "topic": b["topic"], "importance": b["importance"]} for b in six], check_pick)["order"]
                    section["order"].extend(order + [b["id"] for b in new[6:]])
                section["pool_ids"].extend(b["id"] for b in new)
                section["pick_done"] = True
                save()
                boundary(root, key, stepwise)
            last_outcomes = {o['id']: o for o in section['outcomes']}
            processed = {sid for sid, o in last_outcomes.items() if not (hybrid and
                o.get('status') in ('review_rejected', 'needs_modifier') and o.get('facts_supported') is False
                and o.get('event_clear', True) and not o.get('modifier_attempted'))}
            eligible = [index[sid] for sid in section["order"] if sid in index and sid not in processed]
            while eligible and needs(cat, section):
                used = publishers(section)
                if policy and cat == "News" and len(section["accepted"]) >= 3:
                    eligible = [b for b in eligible if b["importance"] >= 3]
                    if not eligible:
                        break
                if cat == "Science" and len(section["accepted"]) >= 3 and len(used) < 2:
                    # Already-safe first three are not rewritten while seeking a second publisher.
                    eligible = [b for b in eligible if publisher_key(source_of(b)) not in used]
                    if not eligible:
                        break
                topics = {a["candidate"]["topic"] for a in section["accepted"]}
                def priority(b):
                    return (cat == "News" and not any(a["candidate"]["importance"] >= 3 for a in section["accepted"]) and b["importance"] >= 3,
                            cat == "Science" and len(used) < 2 and publisher_key(source_of(b)) not in used,
                            b["topic"] not in topics)
                b = max(eligible, key=priority)
                eligible.remove(b)
                art, sid = b["article"], b["id"]
                user = re.sub(r"^Today: .*", f"Today: {snapshot['date']}.", tri_variant_rewriter_input([(0, art)], category=cat))
                rewrite_key = f"rewrite-{cat}-{sid}"
                try:
                    from .agent_shadow_lengths import rewrite_rules
                    entry = ask(root, rewrite_key, TRI_VARIANT_REWRITER_PROMPT + rewrite_rules(cat, art['word_count']), user,
                                lambda value: validate_rewrite(value, cat, art["word_count"]))["articles"][0]
                except AnswerRejected as exc:
                    pin_task_answers(root, rewrite_key)
                    section["outcomes"].append({"id": sid, "category": cat, "status": "rewrite_invalid", "reason": str(exc)})
                    save()
                    boundary(root, f"rewrite-invalid-{cat}-{sid}", stepwise)
                    continue
                audit_path = root / 'provider-audit.json'
                if audit_path.exists() and any(token.startswith(rewrite_key + ':') and r.get('fallback') == 'native'
                    for token, r in read(audit_path).get('requests', {}).items()):
                    b['writer_provider'] = 'native'
                boundary(root, rewrite_key, stepwise)
                def check_review(value):
                    scores = value.get("scores", {}).get("0", {})
                    return [] if (type(value.get("facts_supported")) is bool and (not policy or type(value.get("event_clear")) is bool) and all(
                        type(scores.get(d)) in (int, float) and 0 <= scores[d] <= 5 for d in SAFETY_DIMS)) else [
                            "Return all eight scores for 0 (0..5), and facts_supported boolean"]
                key = f"review-{cat}-{sid}"
                modifier_attempted = False
                try:
                    review_prompt = (SAFETY_VET_PROMPT +
                        '\nUse a new session or sub-Agent, only this request. Do not read tasks/rewrite-*/answer.json. '
                        'This is 同模型第二遍审核, not an independent model. Compare final text with the source; '
                        'add facts_supported true/false. Do not invent viewpoints.' +
                        (' Also return event_clear boolean. Compare this event against ONLY the supplied same-category history and accepted events; uncertain or duplicate => false.' if policy else ''))
                    material = {"source": art["body"], "article": {k: entry[k] for k in ("source_id", "easy_en", "middle_en", "zh")},
                         **({"history": snapshot["history"][cat], "accepted_events": [
                             {"title": a["candidate"]["article"]["title"], "source_excerpt": a["candidate"]["article"]["body"][:1200]}
                             for a in section["accepted"]]} if policy else {})}
                    previous = last_outcomes.get(sid, {})
                    recovering = hybrid and previous.get('status') in ('review_rejected', 'needs_modifier') and not previous.get('modifier_attempted')
                    if hybrid and (snapshot.get('review_mode') == 'modifier' or recovering):
                        review = None
                    else:
                        review = ask(root, key, review_prompt, material, check_review)
                    if hybrid and (review is None or
                        (review.get('event_clear', True) and (not review['facts_supported'] or english_errors(entry)))):
                        from .agent_shadow_modifier import modify
                        modifier_attempted = True
                        key = f'review-modify-{cat}-{sid}'
                        issues = {'review': review or previous, 'language': english_errors(entry)}
                        key, entry, review = modify(root, cat, sid, art, entry, issues,
                            snapshot['history'][cat], material.get('accepted_events', []), ask, check_review)
                    safety = evaluate_rewriter_safety({"safety": review["scores"]["0"]}, category=cat)
                    passed = safety["verdict"] == "PASS" and review["facts_supported"] and (not policy or review["event_clear"])
                    outcome = {"id": sid, "category": cat, "status": "accepted" if passed else "review_rejected",
                               'writer_provider': b.get('writer_provider', 'deepseek' if hybrid else 'native'),
                               'review_method': '同模型写稿并自检' if b.get('writer_provider') == 'native' or not hybrid else '第二模型修稿并自检；无第三轮审核',
                               "safety": safety, "facts_supported": review["facts_supported"],
                               **({'modifier_attempted': modifier_attempted, 'notes': review.get('notes', '')}
                                  if hybrid else {}),
                               **({"event_clear": review["event_clear"]} if policy else {})}
                except AnswerRejected as exc:
                    pin_task_answers(root, key)
                    passed = False
                    outcome = {"id": sid, "category": cat, "status": "review_invalid", "reason": str(exc),
                               **({'modifier_attempted': modifier_attempted} if hybrid else {})}
                section["outcomes"].append(outcome)
                if passed:
                    section["accepted"].append({"candidate": b, "entry": entry})
                save()
                boundary(root, key, stepwise)
            if policy and needs(cat, section):
                expanded = policy.extend(cat, target, section)
                if expanded is not None:
                    targets[cat] = expanded
                    write(refill_path, {"targets": targets})
                    boundary(root, f"refill-{cat}-{expanded}", stepwise)
                    continue
            if not policy and needs(cat, section) and target < 30 and len(pool) >= target:
                targets[cat] = min(30, target + 6)
                write(refill_path, {"targets": targets})
                boundary(root, f"refill-{cat}-{targets[cat]}", stepwise)
                continue
            break
    final, variants, warnings = {}, {}, []
    for cat, section in state.items():
        accepted = section["accepted"]
        chosen = accepted[:3]
        if policy and cat == "News" and len(chosen) == 3 and not any(a["candidate"]["importance"] >= 3 for a in chosen):
            important = next((a for a in accepted[3:] if a["candidate"]["importance"] >= 3), None)
            if important:
                chosen = chosen[:2] + [important]
        if cat == "Science" and len(chosen) == 3:
            used = {publisher_key(source_of(a["candidate"])) for a in chosen}
            if len(used) < 2:
                other = next((a for a in accepted[3:] if publisher_key(source_of(a["candidate"])) not in used), None)
                if other:
                    chosen = chosen[:2] + [other]
        variants[cat] = {i: a["entry"] for i, a in enumerate(chosen)}
        final[cat] = [{"winner": a["candidate"]["article"], "source": source_of(a["candidate"]),
                       "_image_local": "", "_topic": a["candidate"]["topic"],
                       "_importance": a["candidate"]["importance"]} for a in chosen]
        if cat not in active:
            continue
        if cat == "News" and not any(s["_importance"] >= 3 for s in final[cat]):
            warnings.append("News has no qualified high-importance story")
        minimum = 2 if cat == "Science" or (cat == 'News' and uses_native_details(snapshot)) else 3
        if len({publisher_key(s["source"]) for s in final[cat]}) < minimum:
            warnings.append(f"{cat} has fewer than {minimum} independent publishers")
    return final, variants, [o for c in CATS for o in state[c]["outcomes"]], warnings
