# 2026-10-03 — Fun old lead event

Severity: medium; Area: source-first collection; Status: fixed on feature branch.

## Symptom and cause

The October 3 reader published a DOGOnews article whose September 30 URL
described a table gathering held on September 12. Its RSS publication date was
blank. The body opened "On September 12, 2026". The existing parser recognized
that date, but `rejection()` deliberately applied the lead-event age gate only
to News. Fun checked page age (seven calendar days) and explicit expiration.

## Fix

For new `category-source-date-v3` journals, Fun rejects a clearly dated lead
event more than seven America/New_York calendar days old, before downloading
its photo or sending it to an AI. A later historical date does not trigger this
gate. Science remains exempt. Existing v2 journals continue their frozen policy
on resume. No published article or database row was changed by this code fix.

## Verification

`pipeline/test_source_freshness.py` covers the real DOGO headline/body and
photo-before-AI exclusion, seven-day boundary, later background date, Science
exemption, and v2 compatibility. Related source-first tests run on Python 3.10.
