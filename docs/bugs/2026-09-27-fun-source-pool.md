# 2026-09-27 — Fun first-round source-pool trial

**Severity:** low  
**Area:** pipeline  
**Status:** proposed  
**Keywords:** Fun, sources, source diversity, Jev, first round, RSS

## Symptom and evidence

The September 25 Fun edition had two distinct source names among three
articles. The first-round probe had seven Fun sources, but only two survived
into the curator's top five. Stage 3 could not select a third source from
those already rewritten. A separate quality PR addresses the post-vet spare
path; this trial widens the supply *before* Jev's ranking.

The source registry is admin-editable. On September 27 it had 14 enabled Fun
feeds, but `full_round` loaded only eight. The latest completed run scored
60 total briefs across three sections in Jev ranking in 6.8 seconds. Its
metadata fetch, prefilter, body probe and ranking together took 23.2 seconds;
the 6-to-curator and 4-to-rewrite caps remain unchanged.

## Change and invariant

`pipeline/full_round.py` raises only Fun's initial source limit from eight to
ten. News and Science remain at eight; News currently has only four enabled
feeds, so raising its limit would not add candidates. The existing five-day
freshness, seven-day cross-section duplicate filter, forbidden filter,
category routing, Jev ranking, body/image verification, and independent
full-text child-safety review remain in place. A wider pool must never
bypass any of them.

## Read-only trial and limitations

Using the September 27 source rotation, the additional feeds were Rolling
Stone Music and /Film. Both returned four fresh entries. After the metadata
forbidden filter and 350–1200-word body probe, two Rolling Stone and three
/Film entries remained; this is candidate supply, **not** a finding that any
article is appropriate for children. Several titles concern adult movies or
other mature themes. The local environment had no `TYPESAFE_API_KEY`, so the
Jev prefilter and ranking fell back rather than providing live scores. No
curator, rewrite, safety-vet, publication, or storage write was performed.

All four enabled News feeds (BBC World, Al Jazeera All, PBS NewsHour, NPR
World) returned ten recent RSS entries each in a separate read-only check.
September 27 probe outcomes were BBC 4/6, PBS 9/10, NPR 6/9 and Al Jazeera
1/8 length-valid; the four feeds are technically reachable, but the Al
Jazeera feed is often short and conflict-heavy. Feed health does not imply
that each article is safe or editorially suitable.

## Verification and rollback

- Unit pin: `pipeline/test_source_funnel.py::test_phase_a_source_limit_expands_fun_only`.
- After merge, compare Fun's phase-A contributing sources, probe survivors,
  Jev score/floor, curator sources, final independently vetted source count,
  elapsed time and Jev failure/timeout rate over several scheduled runs.
- If the extra candidates do not improve the final edition, set the Fun limit
  back to eight via a PR. Do not loosen category or child-safety gates to
  make the 3/3 source metric green.
