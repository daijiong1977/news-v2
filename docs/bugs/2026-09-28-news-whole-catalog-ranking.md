# News: whole-catalog editorial ranking before the six-brief curator cut

Status: feature branch / PR #76, not merged into `main`. A manual full-round
run on this branch **did publish** the 2026-09-28 content to the public site;
that does not make the feature code the production `main` implementation.

## Why

The 2026-09-28 News probe had 35 routed briefs. JEV's per-brief scores and
source/topic caps sent six to the DeepSeek curator. The U.S.–China panda
agreement entered, but the public-interest AI safeguards story was JEV catalog
position 8 and the Maricopa election-security explainer was position 14.
The curator cannot select a candidate it never receives. A civics explainer
can matter to U.S. children even without a new law or speech; isolated
headline appeal is not the same as comparing the day's full choice set.

## Revised funnel

1. Keep JEV's category, neutrality, recent-event, same-day-event, source and
   quality checks. Keep its full unique catalog for Stage 3 refill.
2. Compare **at most 29** JEV-qualified News briefs with one DeepSeek chat
   call. The numbered request includes each title, source and short summary,
   plus the prior seven days' News titles. No article body is sent.
3. Require the response to be a bare JSON array containing every input
   integer exactly once, in best-to-worst order. Reject objects, missing or
   repeated numbers, strings, and out-of-range IDs. Resolve the numbers
   against the local catalog; do not accept model-generated titles or facts.
4. Select up to six in that order, preferring known topic groups, no more
   than two per source and topic while enough choices exist, and JEV's News
   quality floor. Relax soft caps only to fill a thin shortlist. DeepSeek
   curator then ranks at most five; rewrite, seven-day publication-history
   review, independent full-text child-safety/neutrality review, and the
   refill process remain in force. Candidates beyond 29 remain in the full
   catalog as reserves.
5. On provider failure or malformed ranking, retain JEV's original catalog
   and six `send` flags. This stage never blocks the daily run.

## Local dry-run, 2026-09-28 saved JEV checkpoint

- 27 News briefs sent to whole-catalog comparison, one DeepSeek Flash chat
  response in about 1.4–1.6 seconds in two local calls. No DeepSeek rewrite,
  publish, or production rerun.
- The bare numeric ordering elevated the panda agreement, Maricopa election
  security, and AI safeguards into the six curator inputs. Previously only
  the panda agreement was in that six.
- A college-sports policy interview initially also entered the six because
  its topic label was unknown. Preferring labelled topics moved it back to
  reserve in a second local call; unknown labels are still allowed if needed
  to fill a genuinely thin shortlist.
- **Remaining limitation:** the comparison ranked an OpenAI/government-site
  candidate high even though it resembles an event in the seven-day published
  list. JEV's earlier event check also retained it. The later independent
  publication-history guard must still reject it before publication. Do not
  treat the numeric ranking as a historical dedup verdict; a future early
  history guard could save a curator slot and rewrite cost if measured first.
- Another source article about disability-office cuts remained high. Final
  neutral wording still depends on the independent full-card and body review;
  ranking does not certify neutrality.

## Tuning and cost

- `pipeline/news_global_rank.py`: `MAX_NEWS_COMPARISON`, ranking instructions,
  numeric contract, source/topic selection and fallback.
- `pipeline/jev_rank.py`: JEV scores, caps, history and same-event filtering.
- `pipeline/full_round.py`: runs whole-catalog ranking inside the checkpointed
  JEV stage, before the curator cut.
- One additional DeepSeek chat call on a JEV-enabled News day. The 29-item
  limit bounds input/output; response contains only integers. Time observed
  in two local calls is not a production latency guarantee.
- This feature is a selection experiment. Validate several natural runs and
  compare top-six choices, published quality, history rejections, call usage
  and topic/source diversity before treating it as a settled editorial rule.

## Manual full-round result (2026-09-28, branch commit `5b1fbb3`)

[Daily pipeline run 36427645986](https://github.com/daijiong1977/news-v2/actions/runs/36427645986)
completed in about 12m27s, published three stories per section and triggered
[kidsnews-v2 sync 36429087887](https://github.com/daijiong1977/kidsnews-v2/actions/runs/36429087887)
(site commit `38609433428fcecb98faf28830a1d59f274b4aa5`). Public article
payloads on both site domains showed the new 2026-09-28 edition. Every shipped
story had the independent safety `SAFE` verdict, but the editorial result did
**not** match the intended News choices:

- News global rank compared 29 candidates in 1.5s. Panda agreement, civil
  rights cuts and AI safeguards entered the six-item curator shortlist;
  Maricopa election-security was numeric rank 7, just outside it.
- The curator put panda agreement at rank 5, a spare. Gates/AI safeguards was
  marked `unverified` by the seven-day history guard and excluded. A nor'easter
  article was correctly identified as a repeat of September 26. The civil
  rights rewrite was independently rejected at bias 3.
- Refill preferred a new broad topic over the higher-ranked panda spare,
  promoting an AI-in-schools experiment and a Maine Senate race. Final News
  became Venezuela prisoner release, AI-in-schools, and the Maine Senate race.
  Telemetry warned `News: no qualified high-importance story in final selection`.
- JEV Stage-1 prefilter timed out at 60s and failed open; later JEV ranking
  nevertheless scored 81/81 candidates. The full run's JEV rank phase took
  150s, including routing/topic overhead reported separately in telemetry.

Conclusion: one numeric whole-set rank improves what the curator can see, but
the six-slot cut, curator ordering, uncertain history decisions and Stage-3
topic-first refill can still undo the editorial choice. A green workflow is
not a quality acceptance. Do not merge PR #76 solely on this run; measure and
fix those downstream interactions before another production overwrite.
