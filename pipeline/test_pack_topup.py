"""Tests for pack-time carry-over top-up (2026-07-08).

Owner design: a category must always ship 3 articles —
  1. dig deeper across sources (Stage-3 deep backfill, #41), and
  2. if still short at pack time, carry stories over from the previous
     live bundle until the category has 3 again.

`_derive_pack_plan` decides per category: publish fresh / top up / keep
old. `_topup_thin_categories` appends previous-bundle stories (listings +
detail payloads + images + PDFs) to a short category. Pure file ops — no
LLM calls, no gate changes.

Run: python -m pipeline.test_pack_topup   (also works under pytest)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline import pack_and_upload as pk


# ── 1. pack plan ──

def test_plan_all_full_needs_nothing():
    fresh, short, keep = pk._derive_pack_plan(
        {"news": 3, "science": 3, "fun": 3})
    assert fresh == {"news", "science", "fun"}
    assert short == set() and keep == set()


def test_plan_short_and_empty_categories():
    fresh, short, keep = pk._derive_pack_plan(
        {"news": 1, "science": 3, "fun": 0})
    assert fresh == {"news", "science"}
    assert short == {"news"}          # 1-2 fresh → top up to 3
    assert keep == {"fun"}            # 0 fresh → keep previous live content


def test_plan_env_restricts_fresh_set():
    # Partial run: only News is fresh even if stale local listings exist.
    fresh, short, keep = pk._derive_pack_plan(
        {"news": 2, "science": 3}, merge_env_cats={"news"})
    assert fresh == {"news"} and short == {"news"}
    assert keep == {"science", "fun"}


# ── 2. carry-over top-up ──

def _listing(ids_imgs):
    return json.dumps({"articles": [
        {"id": i, "title": f"t-{i}", "summary": "s",
         "image_url": f"article_images/{img}"} for i, img in ids_imgs]})


def _seed(root: Path, cat: str, ids_imgs) -> None:
    (root / "payloads").mkdir(parents=True, exist_ok=True)
    for lvl in ("easy", "middle", "cn"):
        (root / "payloads" / f"articles_{cat}_{lvl}.json").write_text(
            _listing(ids_imgs))
    for sid, img in ids_imgs:
        d = root / "article_payloads" / f"payload_{sid}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "middle.json").write_text("{}")
        (root / "article_images").mkdir(parents=True, exist_ok=True)
        (root / "article_images" / img).write_bytes(b"x")
        (root / "article_pdfs").mkdir(parents=True, exist_ok=True)
        (root / "article_pdfs" / f"{sid}-middle.pdf").write_bytes(b"p")


def test_topup_fills_short_category_from_old_bundle():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        final, old = Path(t1), Path(t2)
        _seed(final, "news", [("today-1", "new1.webp")])            # 1 fresh
        _seed(old, "news", [("yday-1", "o1.webp"), ("yday-2", "o2.webp"),
                            ("yday-3", "o3.webp")])
        carried = pk._topup_thin_categories(final, old)
        assert carried == {"news": ["yday-1", "yday-2"]}
        for lvl in ("easy", "middle", "cn"):
            doc = json.loads(
                (final / "payloads" / f"articles_news_{lvl}.json").read_text())
            assert [a["id"] for a in doc["articles"]] == \
                ["today-1", "yday-1", "yday-2"]     # fresh first, then carried
        # Carried artifacts copied over.
        assert (final / "article_payloads" / "payload_yday-1" / "middle.json").is_file()
        assert (final / "article_images" / "o2.webp").is_file()
        assert (final / "article_pdfs" / "yday-1-middle.pdf").is_file()
        # Not-carried old story stays out.
        assert not (final / "article_payloads" / "payload_yday-3").exists()


def test_topup_skips_full_and_empty_categories():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        final, old = Path(t1), Path(t2)
        _seed(final, "science", [("s1", "s1.webp"), ("s2", "s2.webp"),
                                 ("s3", "s3.webp")])                # full
        _seed(old, "science", [("os1", "os1.webp")])
        _seed(old, "fun", [("of1", "of1.webp")])                    # no fresh fun
        carried = pk._topup_thin_categories(final, old)
        assert carried == {}
        doc = json.loads(
            (final / "payloads" / "articles_science_middle.json").read_text())
        assert len(doc["articles"]) == 3 and doc["articles"][0]["id"] == "s1"


def test_topup_never_duplicates_ids():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        final, old = Path(t1), Path(t2)
        # Fresh already contains one of the old ids (same-slot overwrite).
        _seed(final, "news", [("shared-1", "n1.webp"), ("today-2", "n2.webp")])
        _seed(old, "news", [("shared-1", "o1.webp"), ("yday-2", "o2.webp")])
        carried = pk._topup_thin_categories(final, old)
        assert carried == {"news": ["yday-2"]}
        doc = json.loads(
            (final / "payloads" / "articles_news_middle.json").read_text())
        ids = [a["id"] for a in doc["articles"]]
        assert ids == ["shared-1", "today-2", "yday-2"]
        assert len(ids) == len(set(ids))


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
