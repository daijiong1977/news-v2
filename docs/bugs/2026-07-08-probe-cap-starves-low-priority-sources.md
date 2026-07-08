# 2026-07-08 — probe cap starves low-priority sources (BBC never reached curator)

**Severity:** medium
**Area:** pipeline (mega Stage 1.5 probe)
**Status:** fixed
**Keywords:** PROBE_MAX_PER_CAT, cap, truncation, interleave, round-robin, BBC, source diversity, per-source funnel, telemetry

## Symptom

Owner noticed today's News shipped from only 2 distinct sources (NPR ×2 +
Al Jazeera) and asked "why isn't BBC included?" — BBC has been an enabled,
live, priority-4 News source the whole time.

## Root cause

Reconstructed the 2026-07-08 run from `redesign_checkpoints`:

| source (priority) | briefs | after forbidden | probe kept |
|---|---|---|---|
| PBS (1) | 4 | 3 | 3 |
| NPR (2) | 4 | 4 | 4 |
| Al Jazeera (3) | 4 | 4 | 3 |
| **BBC (4)** | 4 | 4 | **0** |

Stage 1.5 walked briefs in list order — and `phase_a_light` emits briefs
grouped by source in cadence/priority order — keeping the first
`PROBE_MAX_PER_CAT=10` that pass the word gate, then `break`. With 4
sources × 4 briefs, the first three sources filled the cap and BBC's 4
briefs were silently discarded before the curator ever saw them. On any
day the higher-priority feeds are healthy, the last source gets ZERO
probe slots — structural starvation, not editorial choice.

(Also diagnosed in the same pass: PBS reached rank 3 and PASSED image
verify, but was Stage-3 safety-rejected under the old any-dim≥3 rule —
already fixed by the per-dimension thresholds, PR #37.)

## Fix

PR: fix/probe-cap-interleave.

1. **`_interleave_by_source(briefs)`** (`pipeline/full_round.py`) —
   round-robin briefs across sources (within-source order preserved)
   before the probe, so the cap samples every source ~evenly (4 sources ×
   cap 10 → 2-3 slots each).
2. **`_partition_probe_results(...)`** — extracted the classify+cap loop
   into a pure function that classifies EVERY brief (`in/kept/thin/long/
   cap_cut` per source) instead of `break`-ing, so cap starvation is now
   visible instead of silent.
3. **Per-source funnel telemetry** — `phase_a_probe.per_source`,
   `verify.per_source` (verified + reject reasons, source name now in the
   FAIL log line), `stage3_safety.per_source` (shipped / safety_rejected +
   reject reason logged with source name). Answers "which stage killed
   source X" straight from `redesign_runs.telemetry`.

## Invariant

- The probe cap must never be applied to a source-grouped list — always
  interleave first. A funnel stage that drops items silently (uncounted)
  is a bug.

## Pinning test

`python -m pipeline.test_source_funnel` — esp.
`test_interleave_plus_cap_keeps_every_source_represented` (reproduces the
4×4-cap-10 BBC starvation) and
`test_verify_picks_lazy_records_per_source_stats`.

## Related

- `docs/bugs/2026-07-08-news-safety-and-image-tuning.md` — PBS half of
  the "only 2 sources" symptom (safety thresholds).
- Follow-up (open): add more kid-oriented News sources; News has only 4
  sources for a 5-pick curator, so one repeat source per day is
  guaranteed by pigeonhole even with a fair cap.
