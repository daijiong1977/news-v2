# Shadow quote punctuation and Science publisher fetch starvation

## Symptom
2026-10-01 website-1 generated nine accepted stories but publication_bundle build
rejected c044: a verbatim quote ended with a comma instead of the source's period.
Three Science stories were all ScienceDaily, despite alternative publishers in the catalog.

## Root cause
website_release.evidence_gate compared quoted text including terminal punctuation.
BatchEditor.pool exhausted twelve Science fetch attempts in catalog order: four
Live Science attempts returned ValueError with zero words. Smithsonian c047 was
later in the catalog and was not fetched. Logs do not preserve the ValueError
message, so the precise network/extraction failure cannot be established.

## Fix
Only terminal quotation punctuation is ignored. Words, interior punctuation and
numeric support still undergo the existing checks. Science fresh pools give the
first candidate from each independent publisher an early fetch opportunity, then
retain ranked order for remaining candidates. Source identities use publisher_key,
not feed names. Frozen batches, accepted articles and request hashes are not edited.

## Invariant
Typography must not masquerade as unsupported facts. Publisher diversity must be
given a bounded fetch opportunity, not guaranteed by admitting unsuitable text.
Do not regenerate accepted content or remove the twelve-fetch budget to recover.

## Pinning tests and observed evidence
- test_quote_terminal_punctuation_is_not_a_fact_change (failed before fix).
- test_science_other_publishers_get_fetch_chance_before_repeated_failed_host
  (failed before fix).
- Existing full batch/resume tests preserve no-second-write behavior.
- All eighteen English bodies in logs commit bb03ce270c1e7312cb9200f07f590fedd417771f
  pass the fixed evidence_gate offline. This is not proof of actual publication.

## Resume this completed generation
Pull the runtime branch; do not rerun prepare or modify frozen answers. Continue
publication_bundle build/check, website_release build/check, and website_delivery
handoff --push using the existing website-1 directory and the website release
runbook. Today's single-publisher Science is a disclosed warning, not a reason
to regenerate. Latest-only website trial is authorized; DB/archive writes remain
out of scope. Upload logs and return Actions/public verification results.
