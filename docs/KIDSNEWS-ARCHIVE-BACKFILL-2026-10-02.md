# 2026-10-02: verified website edition → dated archive and database

## Authorization and backup scope

The user authorized overwriting the October 2 edition, with a backup first. After clarifying that the existing API keys cannot produce a full PostgreSQL dump, the user explicitly selected option 2: business-table data plus the Storage bytes affected by this operation. This is **not a full database backup**: Auth, internal schemas, database roles, and unrelated Storage bytes are excluded.

The backup is private on the Mac, not in either Git repository:

`/Users/jiong/.local/share/kidsnews-backups/20261003T034148Z-archive-lfknsvavhiqrsasdfyrs/`

Its UTC directory date is October 3; the edition and local ET operation date are October 2. Directory mode is 0700; files are created under umask 0077. Never attach its business-table JSON to a PR or publish it. The 96 public business tables contain 19,840 rows captured in one read-only SELECT/MVCC snapshot. The schema-reference JSON is diagnostic metadata, not a complete schema/role restore dump. All 105 scoped Storage objects were downloaded and hashed; their metadata/version list was unchanged across backup.

## Exact pinned edition

- Release repository: `daijiong1977/grokbot-kidsnews`.
- Release branch: `codex/website-release-2026-10-02-twelve-five-three-1`.
- Release commit: `39281da206f7a99ce8a2fbbacda1b8d08b9e468f`.
- Public reader ZIP SHA256: `886a24e25df3e2c7876dbefd1b94bbbe700466298c044c146f8214d32c77a450`.
- Existing manifest's build source: `7a0ff13e9d7d5297a87b60904f4894080b1ae000`; do not confuse it with the release-artifact commit or current development HEAD.
- Supabase project: `lfknsvavhiqrsasdfyrs`; bucket: `redesign-daily-content`.

The ZIP matches Storage latest and the current website's three middle listings. It contains 9 listing JSON files, 18 Easy/Middle detail JSON files, and 9 source photos. All referenced photos decode with Pillow and meet the existing 20,000-byte floor. No new images were generated. There are no PDFs in this edition. “Payload” means the JSON listing/detail assets here, not a PDF or a new details table.

## Applied scope

| Area | Change |
| --- | --- |
| `redesign_runs` | Insert one completed run: `db789aaa-1b8f-5836-a48a-821c5815ec3e`. Model usage is unknown, not fabricated. |
| `redesign_stories` | Update the 9 existing October 2 slots, preserving both UUID primary keys and payload story IDs. Replace source/image/safety/topic metadata; clear stale old-edition ranking fields. |
| `redesign_search_index` | Replace only October 2 rows: 18 → 27, with Easy, Middle, Chinese (`zh`) for each story. Preserve existing English search-row UUIDs. Existing trigger recomputes search vectors. |
| `redesign_source_configs` | Update only `last_used_at` and `next_pickup_at` for IDs `2, 5, 121, 337, 362`, monotonically using the pinned packed timestamp. No source category, enable flag, URL, or cadence is changed. |
| Dated flat archive | Upload the 9 listings, 18 details, 9 photos under `2026-10-02/` in the existing layout. |
| Dated ZIP/manifest | Replace `2026-10-02.zip` with the same public reader ZIP and its matching dated manifest. Never upload internal publication records as the public reader. |

Untouched: `latest.zip`, `latest-manifest.json`, `archive-index.json` (October 2 already listed), unreferenced legacy dated files, other dates, old runs, user reading/quiz/reaction data, all other tables/projects, GitHub Actions, deployment, mail, and scheduled finalizers. Existing same-day reading state may still refer to old content under reused slot IDs; it was deliberately not reset.

## Paired update / recovery artifacts

Private `operation/` contains:

- `before.json` / `after.json`: exact target row sets.
- `apply.sql` / `rollback.sql`: paired SQL generated before any upload.
- `storage-plan.json`: the 38 exact writes and their SHA256s.
- `journal.json`: attempted and verified uploads, DB attempt/commit, final result.
- `rollback.py`: read-only by default; `--execute` restores this operation only.

SQL runs in a short transaction with lock and statement timeouts, locks the four target tables, and checks row before-images before modifying anything. It also validates post-images before COMMIT. A conflicting newer edit aborts rather than being overwritten. Search comparisons exclude trigger-managed `doc_tsv` / `updated_at`; content and all other fields remain guarded. Rollback briefly disables only the search-vector trigger **inside its locked transaction**, restores the original vectors and timestamps, and reenables it before commit. Errors roll the trigger alteration back as well. It does not replace the trigger function.

Storage cannot share an atomic transaction with PostgreSQL. The journal records every attempted write before sending it. Recovery preflights all attempted objects: each must still match either its backed-up bytes or this operation's uploaded bytes. A third-party change requires manual review. Restore old bytes for replaced objects; remove only newly added objects from this exact plan. Do not restore latest, delete a date directory, or clear all rows from a shared table. Newly added images remain recoverable from the pinned reader ZIP in the backup.

Run the private recovery script using a Python environment with `python-dotenv` installed. First run without flags to inspect; only add `--execute` when rollback is explicitly requested. Do not rerun `apply.sql` blindly after a timeout: first inspect the saved run ID and journal. Never delete state to make a retry look new.

## Verification and activation boundary

Offline PostgreSQL/PGlite 0.3.14: 9 assertions passed, including update→exact rollback, story UUID preservation, regenerated vectors, and refusal to overwrite intervening changes. Python utility files compiled under 3.10. Live verification: 9 dated stories, 27 search rows, one new run; all 38 Storage writes matched on authenticated and public readback. Latest ZIP and archive index hashes were unchanged. Website middle listings still match the pinned ZIP and homepage returns HTTP 200.

The whole 96-table backup has **not** been restored into a separate server; only the scoped SQL rollback has been exercised offline. No live rollback was performed just to test it.

This is a completed **manual dated backfill**, not an enabled automatic Bot/Edge consumer. The old scheduled-finalizer migration/function remains unactivated; it must not be reused blindly because its internal ZIP, validator, latest handling, and rollback contract differ from the current public reader. Recurring integration needs a separately reviewed feature PR and concurrency/recovery tests. No main branch, schema migration, or function deployment is part of this operation.
