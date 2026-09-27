"""Manual reruns preserve the intended local editorial date after UTC midnight."""
from datetime import date

import pytest

from pipeline.run_date import pipeline_run_date


def test_default_is_current_utc_date(monkeypatch):
    monkeypatch.delenv("PIPELINE_RUN_DATE", raising=False)
    assert pipeline_run_date(date(2026, 9, 27)) == "2026-09-27"


def test_previous_local_evening_can_be_rerun(monkeypatch):
    monkeypatch.setenv("PIPELINE_RUN_DATE", "2026-09-26")
    assert pipeline_run_date(date(2026, 9, 27)) == "2026-09-26"


@pytest.mark.parametrize("value", ["2026-09-28", "2026-09-19", "2026/09/26",
                                    "2026-09-31", "20260926"])
def test_rejects_future_old_or_malformed_date(monkeypatch, value):
    monkeypatch.setenv("PIPELINE_RUN_DATE", value)
    with pytest.raises(ValueError):
        pipeline_run_date(date(2026, 9, 27))
