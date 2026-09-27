"""A validated editorial date for scheduled runs and manual reruns."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone


def pipeline_run_date(now_utc: date | None = None) -> str:
    """UTC today by default; an override may name a recent past edition.

    A manual rerun after UTC midnight may still belong to the prior New York
    editorial day. Limit overrides to the past week to prevent accidental
    future-dated or far-old publication.
    """
    today_utc = now_utc or datetime.now(timezone.utc).date()
    raw = (os.environ.get("PIPELINE_RUN_DATE") or "").strip()
    if not raw:
        return today_utc.isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError("PIPELINE_RUN_DATE must be YYYY-MM-DD")
    requested = date.fromisoformat(raw)
    age = (today_utc - requested).days
    if not 0 <= age <= 7:
        raise ValueError("PIPELINE_RUN_DATE must be within the past seven UTC days")
    return raw
