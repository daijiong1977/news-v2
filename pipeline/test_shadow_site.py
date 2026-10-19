import json
from pathlib import Path

import pytest

from pipeline.shadow_site import export


def fixture_site(root):
    (root / "payloads").mkdir(parents=True)
    for cat in ("news", "science", "fun"):
        sid = f"2026-09-30-{cat}-1"
        detail = root / "article_payloads" / f"payload_{sid}"
        detail.mkdir(parents=True)
        for level in ("easy", "middle", "cn"):
            (root / "payloads" / f"articles_{cat}_{level}.json").write_text(json.dumps({"articles": [
                {"id": sid, "title": "Test title", "summary": "Test summary", "source": "Test publisher"}]}))
            if level != "cn":
                (detail / f"{level}.json").write_text(json.dumps({"summary": "Test body"}))


def test_export_only_reader_files_and_mark_unverified(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    fixture_site(source)
    (source / "admin.html").write_text("not part of the shadow reader")
    report = export(source, output, "2026-09-30", "test-agent")
    assert report["counts"] == {"news": 1, "science": 1, "fun": 1}
    assert report["review"] == "unverified"
    assert not report["production_published"]
    assert not (output / "admin.html").exists()
    assert (output / "article_payloads/payload_2026-09-30-news-1/easy.json").exists()
    with pytest.raises(ValueError, match="new directory"):
        export(source, output, "2026-09-30", "test-agent")


def test_wrong_date_and_path_escape_rejected_before_export(tmp_path):
    source = tmp_path / "source"
    fixture_site(source)
    with pytest.raises(ValueError, match="wrong date"):
        export(source, tmp_path / "bad-date", "2026-10-01", "test-agent")
    path = source / "payloads/articles_news_easy.json"
    listing = json.loads(path.read_text())
    listing["articles"][0]["image_url"] = "/article_images/../../secret.png"
    path.write_text(json.dumps(listing))
    with pytest.raises(ValueError, match="image must be local"):
        export(source, tmp_path / "bad-image", "2026-09-30", "test-agent")
    assert not (tmp_path / "bad-image").exists()


def test_empty_categories_allowed_and_levels_must_agree(tmp_path):
    source = tmp_path / "source"
    fixture_site(source)
    for level in ("easy", "middle", "cn"):
        (source / "payloads" / f"articles_fun_{level}.json").write_text('{"articles": []}')
    assert export(source, tmp_path / "valid", "2026-09-30", "test-agent")["counts"]["fun"] == 0
    (source / "payloads/articles_news_cn.json").write_text('{"articles": []}')
    with pytest.raises(ValueError, match="mismatched"):
        export(source, tmp_path / "bad", "2026-09-30", "test-agent")
