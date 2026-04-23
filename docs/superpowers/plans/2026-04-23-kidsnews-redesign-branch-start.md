# KidsNews redesign branch-start plan

**Date:** 2026-04-23
**Purpose:** Start the real redesign from a clean baseline without carrying forward the failed preview branch assumptions.

## 1. Branch position

- Treat the current local `redesign` branch as archive / scratch history.
- Do not use the current `redesign` branch as the branch that defines the new baseline.
- Start the new redesign branch from `origin/main`.
- Recommended branch name: `newdesign-baseline`.

## 2. Baseline rules

- Do not commit secrets.
- Do not push generated test outputs as part of the redesign baseline.
- Do not use `git add .` for the first redesign commits.
- Use path-limited commits so the new baseline stays reviewable.
- Keep the old Supabase schema live while the redesign writes to a new parallel table family.

## 3. What belongs in the baseline

Carry forward only the assets that match the locked redesign contract.

### Include

- `newdesign/News Oh,Ye! prototype.html`
- `newdesign/home.jsx`
- `newdesign/article.jsx`
- `newdesign/components.jsx`
- `newdesign/user-panel.jsx`
- `supabase/migrations/20260423_redesign_parallel_schema.sql`
- image assets that are directly required by the prototype UI
- the new dated redesign docs under `docs/superpowers/`

### Exclude from the first push

- generated HTML exports under `newdesign/uploads/`
- screenshots that are not part of runtime
- temporary prototype outputs
- leaked-secret files until they are cleaned
- unrelated backup files such as `index.html.bak*`

## 4. Required cleanup before any push

These files must be cleaned before the new redesign branch goes to GitHub:

- `PIPELINE-IMPLEMENTATION.md`
- `vetter-comparison-test.mjs`
- `.gitignore`

Why:

- they currently contain hard-coded credentials or leaked key material
- they still encode outdated redesign assumptions

## 5. Commit sequence

Use small commits in this order.

### Commit 1: lock the redesign contract

Contents:

- `docs/superpowers/specs/2026-04-23-kidsnews-redesign-contract.md`
- `docs/superpowers/plans/2026-04-23-kidsnews-redesign-branch-start.md`

Goal:

- establish the new product truth before code churn starts

### Commit 2: parallel schema scaffold

Contents:

- `supabase/migrations/20260423_redesign_parallel_schema.sql`
- doc updates that state the redesign writes to new tables first

Goal:

- let the redesign pipeline run beside the old project instead of replacing it immediately

### Commit 3: secret cleanup and doc correction

Contents:

- remove hard-coded keys from `PIPELINE-IMPLEMENTATION.md`
- remove hard-coded keys from `vetter-comparison-test.mjs`
- remove leaked key text from `.gitignore`
- update the pipeline guide to the new category and funnel contract

Goal:

- make the repo safe to push

### Commit 4: UI baseline import

Contents:

- only the `newdesign/` files that are actually part of the current visual baseline
- any required runtime images

Goal:

- preserve the working prototype screens as the redesign starting point

### Commit 5: data and copy alignment

Contents:

- clean `Sports` remnants inside `newdesign/data.jsx`
- align labels and mock content to `News / Science / Fun`
- record placeholder actions clearly where needed

Goal:

- make the prototype match the new product language

### Commit 6: pipeline implementation work

Contents:

- update prototype pipeline code and docs to the per-category `6 + 4 -> 10 -> 5 -> 3` contract
- write the redesign pipeline into the parallel tables first
- align payload planning to easy/middle/Chinese outputs

Goal:

- move from redesign baseline to executable implementation

### Commit 7: cutover preparation

Contents:

- read-path adapters, views, or copy jobs needed for migration from old to new
- validation notes comparing old and new outputs

Goal:

- make the final cutover an explicit, reversible step

## 6. Suggested git flow

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c newdesign-baseline
```

Then stage by path, not globally.

For the first commit:

```bash
git add docs/superpowers/specs/2026-04-23-kidsnews-redesign-contract.md
git add docs/superpowers/plans/2026-04-23-kidsnews-redesign-branch-start.md
git commit -m "Lock redesign contract and branch baseline"
```

For later commits, keep the same rule:

- stage only the files that belong to that commit
- avoid mixing docs cleanup, UI import, and pipeline logic in one snapshot

## 7. Push criteria

Do not push `newdesign-baseline` until all of the following are true:

- secret material is removed
- the parallel redesign schema is committed and reviewed
- the pipeline guide reflects the new redesign contract
- the initial `newdesign/` import excludes generated junk
- the first commit history is understandable without repo archaeology

## 8. Result

If this plan is followed, the new branch will:

- start from clean `main`
- preserve the useful redesign UI work
- avoid carrying forward the failed preview branch as source of truth
- keep the first GitHub review focused on the real redesign baseline