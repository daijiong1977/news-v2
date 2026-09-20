"""Stage 1.2 of the mega pipeline: cheap pre-filter between the forbidden-word
filter and the body probe, so the probe's per-category cap (10) is spent on
candidates that could actually ship.

Rules. Each was validated on 35 days of checkpoints (975 candidates,
2026-08-15..09-19) before being allowed to drop anything; the numbers are in
the PR description and reproducible with jev-probes/race/validate_prefilter_v2.py.

  · livestream / live-blog titles      Python regex, no model
  · shopping guides, deals, reviews    Jev noul
  · stories centred on people killed   Jev score over situational harm levels
  · UK-domestic stories                Jev noul — the audience is US kids

Jev (TypeSafe's "System One" model) returns typed probabilities, no text. The
questions follow docs.typesafe.ai, and the reasons matter when editing them:
  - Score levels describe SITUATIONS, not degrees. Each level is judged on its
    own; the model never sees level numbers or neighbouring levels, so
    "Mild"/"Moderate"/"Severe" carry no meaning.
  - one dimension per Score; Noul gets true/false criteria to pin the boundary.
  - it reads literally: ask exactly what you mean ("harm to people"), not a
    word that smuggles in other things ("suitable" also scored relevance).
  - scores are for threshold checks only; never add them up or interpolate.

Milder safety calls stay with the curator and the Stage 3 vet: a headline
cannot tell "heavy but worth covering" from "not for kids".

FAIL-OPEN. Jev is an optional third party. No key, SDK missing, outage,
timeouts or a high error rate all mean: keep every brief, log why, carry on.
The regex rule still applies because it needs nothing external.

    JEV_PREFILTER=on      (default) drop on the rules above
    JEV_PREFILTER=shadow  score + log what would drop, keep everything
    JEV_PREFILTER=off     skip Jev entirely (regex rule still runs)
"""
from __future__ import annotations

import logging
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("jev-prefilter")

# Thresholds live here, next to the questions they belong to, so a reviewer can
# read the whole decision surface in one screen.
SHOPPING_MIN = 0.90
HARM_MIN = 3.0              # level 3 = "centres on people being killed"; 2.75 also caught 9/11 remembrance
UK_DOMESTIC_MIN = 0.90      # clear-cut only; borderline ones stay for the curator to weigh
MIN_KEEP_PER_CAT = 8        # Jev rules never shrink a category below this
MAX_ERROR_RATE = 0.30       # above this the whole Jev pass is discarded
TIME_BUDGET_S = 60.0
CALL_TIMEOUT_S = 10.0
WORKERS = 4                 # ~16 req/s, under the 1,200 req/min limit

LIVE_RE = re.compile(r"^\s*(watch|listen)\s+live\b|\blive\s+(updates?|blog)\b", re.I)

SHOPPING_Q = "It is a shopping guide, sale, deal, or a consumer product review"
HARM_Q = "How much harm to people does this story describe?"
HARM_LEVELS = [
    "No one is harmed: science, sport, culture, technology, everyday news",
    "A serious subject such as politics, protest, the economy or a court ruling, with no one hurt",
    "An accident, disaster, illness or armed conflict is reported, and harm is mentioned without detail",
    "The story centers on people being killed, attacked, abused or put on trial for killing",
    "The story dwells on the killing of children, sexual violence, suicide, torture or graphic injury",
]
UK_Q = "Is this story mainly about the domestic affairs of the United Kingdom?"
UK_CRITERIA = {
    "true": "UK party politics, UK government policy, a local UK incident or UK weather, or the royal household",
    "false": "A world event that a UK outlet happens to report, any sports story, any science story, "
             "or a story with no particular tie to the UK",
}


def _mode() -> str:
    m = (os.environ.get("JEV_PREFILTER") or "on").strip().lower()
    return m if m in {"on", "shadow", "off"} else "on"


def _build_client():
    """Returns (client, questions) or (None, reason). Never raises."""
    if not os.environ.get("TYPESAFE_API_KEY"):
        return None, "TYPESAFE_API_KEY not set"
    try:
        from typesafe_sdk import Noul, Score, TypeSafeClient
    except Exception as e:  # noqa: BLE001 — optional dependency
        return None, f"typesafe_sdk unavailable: {e}"
    try:
        questions = {
            "shopping": Noul(instructions=SHOPPING_Q),
            "harm": Score(instructions=HARM_Q, criteria=HARM_LEVELS),
            "uk_domestic": Noul(instructions=UK_Q, criteria=UK_CRITERIA),
        }
        # The SDK and its HTTP layer log every request at INFO — ~120 lines a run.
        for noisy in ("typesafe_sdk", "httpx2", "httpx", "httpcore2", "httpcore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        return (TypeSafeClient(timeout=CALL_TIMEOUT_S), questions), None
    except Exception as e:  # noqa: BLE001
        return None, f"client init failed: {e}"


def _score_one(client, questions, brief: dict) -> dict:
    ans = client.system_one(
        state={
            "category": brief.get("_category") or "",
            "title": brief.get("title") or "",
            "snippet": re.sub(r"<[^>]+>", " ", brief.get("summary") or "")[:600],
            "source": brief.get("_source_name") or "",
        },
        questions=questions,
    ).answers
    shopping, harm, uk = float(ans["shopping"].noul), float(ans["harm"].score), float(ans["uk_domestic"].noul)
    # Out-of-range or NaN answers count as a failed call. NaN would also be
    # unstorable in jsonb and silently void every later checkpoint of the run.
    top = len(HARM_LEVELS) - 1
    if not (all(math.isfinite(v) for v in (shopping, harm, uk))
            and 0 <= shopping <= 1 and 0 <= uk <= 1 and 0 <= harm <= top):
        raise ValueError(f"jev returned out-of-range answers: shopping={shopping} harm={harm} uk={uk}")
    return {"shopping": round(shopping, 3), "harm": round(harm, 2), "uk_domestic": round(uk, 3)}


def _jev_reason(j: dict) -> str | None:
    if j["shopping"] >= SHOPPING_MIN:
        return f"shopping={j['shopping']:.2f}"
    if j["harm"] >= HARM_MIN:
        return f"harm={j['harm']:.2f}"
    if j["uk_domestic"] >= UK_DOMESTIC_MIN:
        return f"uk_domestic={j['uk_domestic']:.2f}"
    return None


def _clearcut(j: dict) -> float:
    """How far past its threshold a flagged brief is, 0-1. Orders the drops when
    the floor lets only some of them go."""
    return max(j["shopping"], j["harm"] / (len(HARM_LEVELS) - 1), j["uk_domestic"])


def _score_all(briefs: list[dict], client=None, questions=None) -> tuple[bool, str]:
    """Annotates each brief with `_jev` in place. Returns (usable, note).
    usable=False means the Jev pass must be ignored entirely."""
    if client is None:
        built, why = _build_client()
        if built is None:
            return False, why
        client, questions = built
    t0 = time.monotonic()
    errors = 0
    ex = ThreadPoolExecutor(max_workers=WORKERS)
    try:
        futs = {ex.submit(_score_one, client, questions, b): b for b in briefs}
        try:
            for fut in as_completed(futs, timeout=TIME_BUDGET_S):
                try:
                    futs[fut]["_jev"] = fut.result()
                except Exception as e:  # noqa: BLE001 — one bad call keeps its brief
                    errors += 1
                    log.warning("  jev call failed (%s): %s",
                                (futs[fut].get("title") or "")[:60], e)
        except TimeoutError:
            return False, f"time budget {TIME_BUDGET_S:.0f}s exceeded"
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001
                pass
    if briefs and errors / len(briefs) > MAX_ERROR_RATE:
        return False, f"{errors}/{len(briefs)} calls failed"
    return True, f"{len(briefs) - errors}/{len(briefs)} scored in {time.monotonic() - t0:.1f}s"


def prefilter_briefs(briefs_by_cat: dict[str, list[dict]], *, client=None,
                     questions=None) -> tuple[dict[str, list[dict]], dict]:
    """Returns (kept_by_cat, report). Never raises; on any Jev trouble the
    Jev rules are skipped and only the livestream regex applies.

    `client`/`questions` are injection points for tests."""
    mode = _mode()
    report: dict = {"mode": mode, "jev": "skipped", "dropped": [], "would_drop": [],
                    "restored": 0}

    out: dict[str, list[dict]] = {}
    for cat, briefs in briefs_by_cat.items():
        kept = []
        for b in briefs:
            if LIVE_RE.search(b.get("title") or ""):
                report["dropped"].append({"cat": cat, "title": b.get("title"), "why": "livestream"})
            else:
                kept.append(b)
        out[cat] = kept

    if mode == "off":
        return out, report

    try:
        flat = [b for briefs in out.values() for b in briefs]
        for b in flat:
            b.pop("_jev", None)
        usable, note = _score_all(flat, client, questions) if flat else (False, "no briefs")
    except Exception as e:  # noqa: BLE001 — belt and braces: never break the run
        usable, note = False, f"unexpected error: {e}"
    report["jev"] = note if usable else f"IGNORED ({note})"
    if not usable:
        log.warning("  jev pass ignored — %s. Keeping all briefs.", note)
        for b in (b for briefs in out.values() for b in briefs):
            b.pop("_jev", None)
        return out, report

    for cat, briefs in out.items():
        flagged = [(b, _jev_reason(b["_jev"])) for b in briefs if b.get("_jev")]
        flagged = [(b, why) for b, why in flagged if why]
        if mode == "shadow":
            report["would_drop"] += [{"cat": cat, "title": b.get("title"), "why": why} for b, why in flagged]
            continue
        # Starvation guard: drop the most clear-cut first, stop at the floor.
        flagged.sort(key=lambda t: -_clearcut(t[0]["_jev"]))
        room = max(0, len(briefs) - MIN_KEEP_PER_CAT)
        drop_ids = {id(b) for b, _ in flagged[:room]}
        report["restored"] += len(flagged) - len(drop_ids)
        report["dropped"] += [{"cat": cat, "title": b.get("title"), "why": why}
                              for b, why in flagged if id(b) in drop_ids]
        out[cat] = [b for b in briefs if id(b) not in drop_ids]
    return out, report
