# 2026-10-03 — source-first three-day freshness

Severity: high; Area: shadow pipeline; Status: fixed; Keywords: stale, event date, DOGOnews

## Symptom / cause

October 3 reader included a Romanian table event from September 12.
DOGOnews URL says September 30, feed publication date is missing. Old collector
used five days and allowed unknown dates. Publication time is not event time.

## Fix and invariant

New source-collection journals freeze `three-day-source-and-explicit-lead-v1`.
Python rejects publication dates older than three America/New_York calendar days,
future publications, and explicit old `On Month D, YYYY` opening events. Feed,
dated URL, original Article JSON-LD datePublished and published-time meta are
checked; dateModified cannot rescue an old original. Unknown dates after fetching
the body are rejected unless the opening supplies a current event date.

Old feed dates stop before body/image; old lead events stop before image/AI.
Rejection is candidate exclusion, not deletion from live DB or archives.
Existing completed/frozen journals are not re-filtered. No production full_round
or news_rss_core logic changes. Original metadata added only in shadow fetcher.

This is not general event-date understanding: relative dates, implicit dates,
and articles with only later-paragraph event dates are not semantically inferred.
Historical scientific background is not rejected merely for mentioning years.

## Tests

`pipeline/test_source_freshness.py`: boundary/timezone, actual Romanian lead,
unknown/future, historical background, datePublished versus dateModified,
no-photo/no-body rejection, frozen resume. All offline Python3.10.
