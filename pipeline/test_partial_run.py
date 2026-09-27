"""Tests for the partial-run (single-category) feature (2026-07-08).

Owner ask: "单独直接跑 news" — re-run ONE category (e.g. News) without
touching the other categories' live content. Design:
  · PIPELINE_CATEGORIES=News scopes the mega funnel to that category
    (checkpoints disabled so the day's full-run trail isn't clobbered).
  · emit_v1_shape only writes listings for categories it was given —
    previously it emitted EMPTY listings for absent categories, which a
    naive merge would have shipped over good live content.
  · pack_and_upload merge mode (PACK_MERGE_CATEGORIES=news): pull the
    live latest.zip, splice ONLY the fresh categories' files in, then run
    the normal ≥2-per-cat validation — a bad merge refuses to publish and
    the site keeps its current content.

Run: python -m pipeline.test_partial_run   (also works under pytest)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline import full_round as fr
from pipeline import pack_and_upload as pk


# ── 1. category filter ──

def test_filter_categories_case_insensitive_subset():
    avail = ["News", "Science", "Fun"]
    assert fr._filter_categories(avail, "news") == ["News"]
    assert fr._filter_categories(avail, "News,fun") == ["News", "Fun"]


def test_filter_categories_unknown_raises():
    try:
        fr._filter_categories(["News", "Science", "Fun"], "Sports")
    except SystemExit as e:
        assert "Sports" in str(e)
    else:
        raise AssertionError("unknown category must SystemExit")


# ── 2. emit only writes categories it was given ──

def test_emit_skips_absent_categories():
    with tempfile.TemporaryDirectory() as td:
        web = Path(td)
        fr.emit_v1_shape({"News": []}, {"News": {}}, {"News": {}},
                         "2026-07-08", web)
        assert (web / "payloads" / "articles_news_easy.json").is_file()
        # The old hardcoded loop wrote EMPTY science/fun listings here —
        # which the pack merge would then ship over good live content.
        assert not (web / "payloads" / "articles_science_easy.json").exists()
        assert not (web / "payloads" / "articles_fun_middle.json").exists()


# ── 3. bundle merge: splice fresh category into extracted live bundle ──

def _listing(ids_imgs: list[tuple[str, str]]) -> str:
    return json.dumps({"articles": [
        {"id": i, "title": f"t-{i}", "summary": "s",
         "image_url": f"article_images/{img}"} for i, img in ids_imgs]})


def _seed(root: Path, cat: str, ids_imgs: list[tuple[str, str]]) -> None:
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


def test_overlay_replaces_only_named_category():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        old, fresh = Path(t1), Path(t2)
        _seed(old, "news", [("n_old1", "old1.webp"), ("n_old2", "old2.webp")])
        _seed(old, "science", [("s1", "s1.webp")])
        _seed(fresh, "news", [("n_new1", "new1.webp")])

        pk._overlay_fresh_categories(old, fresh, {"news"})

        # News listing replaced with the fresh one.
        doc = json.loads((old / "payloads" / "articles_news_middle.json").read_text())
        assert [a["id"] for a in doc["articles"]] == ["n_new1"]
        # Old News artifacts removed …
        assert not (old / "article_payloads" / "payload_n_old1").exists()
        assert not (old / "article_images" / "old2.webp").exists()
        assert not (old / "article_pdfs" / "n_old1-middle.pdf").exists()
        # … fresh News artifacts spliced in …
        assert (old / "article_payloads" / "payload_n_new1" / "middle.json").is_file()
        assert (old / "article_images" / "new1.webp").is_file()
        assert (old / "article_pdfs" / "n_new1-middle.pdf").is_file()
        # … and Science untouched.
        assert (old / "article_payloads" / "payload_s1").is_dir()
        assert (old / "article_images" / "s1.webp").is_file()
        doc_s = json.loads((old / "payloads" / "articles_science_easy.json").read_text())
        assert [a["id"] for a in doc_s["articles"]] == ["s1"]


def test_overlay_missing_fresh_listing_aborts():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        old, fresh = Path(t1), Path(t2)
        _seed(old, "news", [("n1", "n1.webp")])
        # fresh root has NO news listings → must refuse (never publish a
        # bundle with a hole where a category used to be).
        try:
            pk._overlay_fresh_categories(old, fresh, {"news"})
        except SystemExit:
            pass
        else:
            raise AssertionError("missing fresh listing must SystemExit")


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
