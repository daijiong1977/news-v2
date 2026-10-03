# 2026-10-01 — shadow website release

**Severity:** high
**Area:** shadow pipeline / website delivery
**Status:** fixed (offline; CI permissions and real deployment pending)
**Keywords:** batch-invalid, resend, JSX, reader, latest-only, rollback, CI

## Symptom

Cloud reproduced a rejected eight-candidate batch repeatedly sent to DeepSeek (45 offline
iterations); the reader shell omitted JSX, which would leave the official page blank.
Website-only latest upload/backup/dispatch adapters were missing.

## Root cause

agent_shadow_batch.pool marked failed batches considered=[]; extend thus believed the
same cached candidates remained available. Valid batches intentionally retain unselected
candidates, but a rejected group must not use that same rule. publication_bundle shell
suffix allowlist did not include .jsx. Existing upload paths target pending/shadow Vercel,
not the agreed phase-one website consumer.

## Fix

PR https://github.com/daijiong1977/news-v2/pull/86; Bot PR1 exports this source commit.

- agent_shadow_batch.py: rejected group consumes its originals; valid unselected IDs remain.
- publication_bundle.py: JSX export and final original-evidence mechanical gate.
- website_release.py: separate clean reader + legacy manifest, exact backup pair, persistent
  attempting/readback state, latest-only publish/rollback, fixed-domain public hashes.
- website_delivery.py / agent/github/publish-reader.yml: Bot artifact pushes; credentials
  held by CI; independent backup artifact uploaded before remote mutation.
- website_ledger.py: private effective history for next-run same-category seven-day dedup.
- reader-shell/config: exact 22-file snapshot from kidsnews-v2 b9592e0, not dirty checkout.

## Invariant

Rejected candidate set cannot be resubmitted; complete official template is pinned.
No production DB/date archive/pending writes. Upload is already a publication action.
Backup must survive runner loss before upload; no blind rerun after uncertain PUT/dispatch.
Only public file matches count as success; only verified releases enter effective history.

## Pinning test

Python3.10: `python -m pytest -q pipeline/test_website_release.py` (13 regressions),
full selected shadow suite 250 tests; `actionlint agent/github/publish-reader.yml`.
Real CI secrets/dispatch/storage/public deployment and rollback remain untested.

## Related

docs/KIDSNEWS-WEBSITE-ONLY-REVIEW-2026-10-01.md; docs/KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md.
docs/bugs/2026-10-01-shadow-http-resume.md; 2026-09-22-new-website-page-not-shipped-allowlist.md.
