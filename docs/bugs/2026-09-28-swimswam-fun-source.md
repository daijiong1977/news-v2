# SwimSwam retired from the active Fun pool (2026-09-28)

In a non-publishing replay of the 2026-09-28 probed pool with the pending News-neutrality branch, Fun had only four qualified briefs. The Jev floor filled the thin shortlist with a SwimSwam obituary, “Frank Busch, NCAA Title Winning Coach and Former US National Team Director, Dies, 75,” at editorial pick 0.41, below the normal Fun floor 0.50. A coach obituary is not the swimming result or star achievement that Fun is meant to prioritize. This was a curator **input**, not a published article.

The live `redesign_source_configs` row was verified as ID 220, `Fun` / `SwimSwam` / `https://swimswam.com/feed/`, enabled before the change. BBC Swimming is a separate enabled row (ID 365), and the 2026-09-28 pipeline used BBC Swimming for its promoted Fun spare. The user chose to remove SwimSwam from the active pool and retain BBC Swimming.

Set only the exact SwimSwam row to `enabled=false`; do not delete it, because its historical attribution and probe counters remain useful and the change is reversible. Update the old seed as well so replaying it does not re-enable the source. No published article is changed, and disabling SwimSwam does not guarantee that every future Fun shortlist is full; the existing quality floor and independent child-safety checks still apply.

Operational verification at 2026-09-28 12:23 UTC: the live source table returned SwimSwam ID 220 `enabled=false` and BBC Swimming ID 365 `enabled=true`. A fresh `load_sources('Fun', n=999)` read excluded SwimSwam and included BBC Swimming. The PR has not been merged into `main`; the table change is already active and the PR records the exact reproducible configuration change.
