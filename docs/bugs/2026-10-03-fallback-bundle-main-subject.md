# 2026-10-03 — Historical fallback bundle and source-subject drift

Severity: high; Area: source-first editor/publication; Status: fixed offline on feature branch.

## Observed run

Oracle run `work/2026-10-03/codex-recency-1` completed 9 edits and `pack` but stopped before publication with `KeyError`: a promoted `ready_stale_fallback` outcome lacked safety/factual fields required by `publication_bundle.build`. Website, database, and archive were not changed by this run. The run directory and answers were preserved.

Editorial inspection also found that a BBC article headed about Aryna Sabalenka had a secondary paragraph about Novak Djokovic, and Codex turned that paragraph into the main headline while retaining the Sabalenka source image. Publication of this edition was withheld. The source article did include the Djokovic paragraph; the error was promoting a secondary event over the title/lead/photo subject.

## Fix

- Persist the complete review/safety metadata when promoting a deferred historical candidate. For an already completed run with the incomplete outcome, the bundle builder may recover those fields only from the matching frozen per-article result (same entry and SHA), without calling a model or rewriting the checkpoint.
- The final-edit request now includes source title and verified publication metadata. The prompt distinguishes a recent page date from an explicitly old event and requires the source title/lead subject to remain the article focus. A conservative Python check requires a distinctive leading title name that appears in the original lead to remain in the Easy/Middle headline or opening; it requests a bounded repair otherwise.

The failed `codex-recency-1` edition must not be published as-is. These changes apply to a fresh run. No existing main-branch pipeline or published reader was modified by this fix.

## Verification

Python 3.10 offline regressions: fallback bundle with a legacy incomplete outcome, request metadata, and Sabalenka-title/Djokovic-body drift. Full end-to-end publication still requires a fresh run and public/DB/archive readback.
