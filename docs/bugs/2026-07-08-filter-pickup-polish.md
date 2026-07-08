# 2026-07-08 — filter-pickup-polish

**Severity:** medium
**Area:** pipeline (filters + pickup + dead code)
**Status:** fixed
**Keywords:** forbidden_filter, asl, cd9, og:image, unreachable-branch, cadence, burst, clamp, scraper, html_list, title, active_weekdays, is_backup, dead-code

## Symptom

P2-tier findings from the 2026-07-07 review sweep:

1. `\basl\b` / `\bcd9\b` in the forbidden list hard-killed legitimate kid
   headlines ("ASL interpreter program"; the band CD9) — they're chat-slang
   detectors meaningless in news copy.
2. `verify_article_content` checked `is_generic_social_image()` before the
   missing-image check, but `is_generic_social_image(None)` is True — so the
   "no og:image" branch was unreachable and absent images were reported as
   "generic social image: None" (lying telemetry).
3. `compute_cadence_days` used median consecutive-gap: a burst publisher
   (9 posts in an hour, then 2 weeks quiet) calibrated to cadence=1 —
   eligible daily with nothing fresh; `--apply` could also swing any
   source's cadence arbitrarily far in one run.
4. DOGOnews html_list briefs had empty titles (image-only card links have
   no anchor text), so the curator — which ranks on title+summary — ranked
   them last forever.
5. `active_weekdays` and `is_backup` were dead columns: loaded, documented,
   and ignored ("adding a backup source" was a no-op).
6. Dead code: `try_next_pick_for_source` triplicated across the three
   aggregate modules with copy-paste drift and zero callers;
   `pick_winners_with_dedup`, `checkpoints.has`, `checkpoints.should_skip`
   uncalled.

NOT changed (deliberate): the gambling pattern group over-filters idioms
("betting big on solar"), but the code carries an explicit editorial-decision
comment accepting that trade-off — respected, not overridden.

## Fix

PR: fix/p2-filter-polish.

- `forbidden_filter.py` — dropped `asl`/`cd9` (kept `gnoc`); comment marks
  the gambling group as a documented editorial choice.
- `news_rss_core.verify_article_content` — missing-image check now precedes
  the generic-image check (honest reasons; branch reachable). Rejection
  policy itself unchanged — placeholder-image degrade needs frontend work,
  deferred.
- `cadence_calibrate.py` — estimator floored by span/(n-1) (burst rhythm);
  `_clamp_step` limits per-run movement to ±2 days.
- `scraper.py::_derive_title` — anchor text → img alt → aria-label →
  humanized URL slug.
- `db_config.load_sources` — honors `active_weekdays` (Mon=0 gate) and
  sorts backups after primaries in both pools, so backups fill only when
  primaries can't cover `n`.
- Deleted (grep-confirmed zero callers): `try_next_pick_for_source` ×3,
  `pick_winners_with_dedup`, `checkpoints.has`, `checkpoints.should_skip`
  (net −97 lines).

## Invariant

1. Image-quality checks must test missing-ness before pattern-matching a
   URL that can be None.
2. `cadence_days` may move at most ±2 per calibration run.
3. A brief emitted by html_list discovery must carry a non-empty title
   whenever any of (anchor text, img alt, aria-label, URL slug) exists.
4. `active_weekdays` and `is_backup` are honored by load_sources — schema
   columns must not silently be no-ops.

## Pinning test

`python -m pipeline.test_filter_polish` (10 tests). All other suites green
(safety 5, P1 5, mega 6, quiz 5, WAF 3).

## Related

- `docs/bugs/2026-07-08-mega-path-regressions.md` — the DOGOnews empty-title
  follow-up came from there.
- Deferred: forbidden list → DB config table (dynamic-config rule); og:image
  placeholder degrade (needs frontend); legacy `main()` retirement decision.
