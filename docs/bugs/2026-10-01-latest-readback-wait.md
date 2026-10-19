# latest pair upload readback wait

## Symptom
CI run 36945154027 stopped with Latest readback mismatch. Read-only inspection
confirmed latest.zip equals reader.zip (4c3b2db504afa8158f4b1106fb74e2088dfa4688042ea066bee258c4f47d0696)
while latest-manifest.json remains the morning version. The public three easy
section listings still match the independent backup, not the new reader.

## Root cause
LatestRelease._replace immediately read an uploaded object once, rejecting stale
bytes. State shows latest.zip attempting; manifest upload and dispatch never ran.
Cache propagation is a plausible explanation, not conclusively proven. Supabase
documents up to 60 seconds for CDN invalidation.

## Fix
Readback waits in five-second intervals, at most fifteen waits (75 seconds),
after PUT and when resuming attempting/complete markers. Only GET is repeated.
Unmatched content after the bound still stops, preserving state and backup;
there is no auto PUT retry, no state reset and no removal of hash checks.

## Invariant
Resume the existing reader artifact using the original CI backup/state. Verify
the already-uploaded ZIP, upload only the missing manifest, then dispatch after
both objects verify. Never regenerate articles, re-backup the half-written pair,
or bypass a competing-writer/uncertain-upload guard.

## Pinning tests
- test_latest_waits_for_stale_reads_without_reupload[False/True]
- test_latest_readback_timeout_keeps_attempt_marker_and_never_resends
All three failed before the change and passed afterwards. Offline mocks only.

## Recovery
Use website_delivery handoff --operation resume --backup-run-id 36945154027
with the existing reader-artifact in website-1 and a new website-release branch.
New CI downloads the original backup/state, performs bounded read verification,
completes the missing upload and follows existing dispatch/public-hash/ledger
steps. Actual website verification is still required; DB/archive remain untouched.
