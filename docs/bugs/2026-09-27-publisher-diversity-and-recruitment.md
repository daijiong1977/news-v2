# 2026-09-27 — Science publisher concentration and Fun college recruitment

**Severity:** medium
**Area:** pipeline editorial selection
**Status:** implemented on a PR branch; production rerun pending

## Observed failure

The Sep-26 edition rerun on `49e0031` published three Science articles from
three ScienceDaily feeds, counted as three different sources. Fun published
Owen Gee's university swimming commitment. The owner wants two independent
Science publishers when qualified alternatives exist, and excludes college
recruitment announcements from Fun.

## Root causes

- Source quotas and final diversity used feed names. Four ScienceDaily feeds
  occupied half the eight Science source slots; the final three counted as
  diverse despite sharing one publisher.
- The Fun sports preference withheld a major-event bonus from college
  recruitment but did not reject it. A recruitment piece could still score
  above the normal floor and gain a swimming-topic diversity slot.
- Filtering only initial briefs would leave spare, checkpoint and carry-over
  paths able to restore the same editorially excluded story.

## Change

`editorial_policy.py` centralizes publisher identity and recruitment exclusion.
Science ranking quotas group by publisher. Curator and final safe selection
prefer two publishers, retaining topic diversity within that constraint;
normal-gated spares can supply the second publisher. An unmet target produces
an explicit warning, not a safety exception. Telemetry records actual
publisher and publication counts.

Recruitment exclusions run at collection, selection, verification, spare and
deep-dig promotion, checkpoint handling, carry-over and bundle validation.
College competition results and records remain eligible. No new model calls
are required for the exclusion. The shared rule uses headline/lead wording;
unseen paraphrases remain a limitation and should become regression examples.

## Validation and rollout

225 offline tests pass; changed-file compilation and whitespace checks pass.
The stored 105-brief baseline replay excludes the reported recruitment story
only. Reordering saved Science curator picks introduces Live Science while
preserving biology, archaeology and astronomy. This replay does not predict
fresh model outputs or replace their safety vet.

After approved merge, regenerate Science and Fun (or the full edition) from
collection, then check two Science publishers, zero recruitment stories,
independent safety outcomes and website sync. Old recruitment content has not
been deleted by this code-only change. Bundle validation can block a partial
publication that retains an excluded old Fun story; regenerate that section.

Full source/pool counts, tuning points and other unimplemented audit findings:
[pipeline funnel audit](../pipeline-funnel-audit-2026-09-26.md).
