"""High-confidence section routing is reversible and never a safety gate."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import editorial_routing as routing


class FakeJev:
    def __init__(self, answers):
        self.answers = answers

    def system_one(self, state, questions):
        target, confidence = self.answers[state["headline"]]
        return SimpleNamespace(answers={"section": SimpleNamespace(
            choice=target, confidence=confidence)})


def _pool():
    return {"News": [{"title": "Fat Bear Week"}, {"title": "A storm"}],
            "Science": [{"title": "A moon discovery"}],
            "Fun": [{"title": "A song"}]}


ANSWERS = {"Fat Bear Week": ("Fun", 0.99),
           "A storm": ("Fun", 0.65),
           "A moon discovery": ("Science", 0.99),
           "A song": ("Fun", 0.99)}


def test_only_confident_misfiled_story_moves():
    pool = _pool()
    out, report = routing.route_briefs(pool, client=FakeJev(ANSWERS), route_mode="on")
    assert [b["title"] for b in out["News"]] == ["A storm"]
    assert [b["title"] for b in out["Fun"]] == ["Fat Bear Week", "A song"]
    assert out["Fun"][0]["_category"] == "Fun"
    assert report["scored"] == 4
    assert report["uncertain"] == 1
    assert len(report["moved"]) == 1


def test_shadow_and_off_do_not_move():
    pool = _pool()
    shadow, report = routing.route_briefs(pool, client=FakeJev(ANSWERS), route_mode="shadow")
    assert [b["title"] for b in shadow["News"]] == ["Fat Bear Week", "A storm"]
    assert "_category" not in shadow["News"][0]
    assert len(report["moved"]) == 1
    off, report = routing.route_briefs(pool, route_mode="off")
    assert off is pool
    assert report["scored"] == 0


def test_failed_one_brief_keeps_its_original_section():
    pool = _pool()
    answers = {key: val for key, val in ANSWERS.items() if key != "A storm"}
    out, report = routing.route_briefs(pool, client=FakeJev(answers), route_mode="on")
    assert report["failed"] == 1
    assert [b["title"] for b in out["News"]] == ["A storm"]
