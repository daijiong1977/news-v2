# Source Engine — Design Spec

**Date**: 2026-04-27
**Status**: Draft (pending user review)
**Owner**: Jiong + Claude

## Problem statement

The kidsnews-v2 pipeline picks 3 articles per category (News / Science / Fun)
from a hand-curated set of RSS sources. Three pain points:

1. **Source visibility is poor.** We have no automated read on which sources
   actually carry the bundle and which are dead weight. Yesterday's bundle
   exposed this — Fun ended up 3-from-Popular-Mechanics because the curator
   had no real diversity to choose from at input.
2. **Source freshness decays silently.** V1 of this product died partly
   because RSS feeds expired or went stale and we noticed too late. A
   category dropping from 5 live sources to 3 cripples diversity rules.
3. **Discovery is manual and intermittent.** When a category needs more
   sources, we sit and brainstorm. Fun in particular has resisted manual
   curation — most candidates we tried got dropped after a few days.

We need an automated system that (a) continuously surfaces health stats
on existing sources, (b) discovers new candidates, and (c) tournaments
candidates through programmatic + LLM validation before promoting them
to live rotation.

## Goals (v1)

- Per-source per-day health metrics, retained and queryable.
- Weekly DeepSeek-driven health report exposed in admin.
- Automated source discovery + 3-5 day probation tournament.
- Promote winners to live, keep next-best as bench.
- **Pilot on Fun category first** — most painful, most diagnostic.
- Reusable framework — same engine handles other verticals later
  (kids/finance, kids/sports, adult/AI, etc.).

## Non-goals (v1)

- Mining from X/Twitter (paid API or fragile bridges — defer).
- Fully automated drop. Verdict suggests; user clicks to apply.
- Cross-vertical replication. Build for kidsnews; extract later.
- Replacing the existing pipeline. Engine writes to the same
  `redesign_source_configs` table the pipeline already reads.

## Core principle: dynamic config

**Nothing the user might want to tune lives in code.** Concretely:

- DeepSeek prompts (validation, verdict, mining queries) → DB.
- Numeric thresholds (word count, image min size, freshness window,
  probation length, bench size, verdict cutoffs) → DB.
- Sub-bucket definitions (Fun's 6 sub-themes, their seed feeds) → DB.
- Forbidden-word lists, kid-appropriateness criteria → DB.
- Discovery agent input lists (Reddit registry, Substack categories,
  RSS aggregator URLs) → DB.

Code reads config rows at startup or per-run. Admin UI gets future
surfaces to edit any of these without redeploying.

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ Phase 0 — Instrumentation (foundation, both A and B depend on it) │
│   Pipeline writes per-source per-day stats to                      │
│   redesign_source_daily_stats after each run.                      │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────┐  ┌─────────────────────────────────┐
│ Phase 1 — Health Report (A)    │  │ Phase 2 — Mining Engine (B)     │
│                                │  │                                 │
│ Weekly cron:                   │  │ Active mode (every 2 weeks):    │
│   pull last 7d stats           │  │   discover candidates           │
│   call DeepSeek for verdict    │  │   triage programmatically       │
│   write redesign_source_reports│  │   pre-rank with DeepSeek        │
│                                │  │   probation 3-5 days            │
│ Admin tab "Source Health":     │  │   verdict + promote/bench       │
│   show latest report           │  │                                 │
│   per-row enable/disable button│  │ Admin tab "Mining Console":     │
│                                │  │   trigger mining manually       │
│                                │  │   review pending probation      │
│                                │  │   approve promotion/rejection   │
└────────────────────────────────┘  └─────────────────────────────────┘
```

Both phases consume Phase 0's stats; Phase 2 also writes back stats
during probation.

## Schema

All new tables live in the existing Supabase project. Naming follows
the `redesign_` prefix convention for consistency with the active
schema (the legacy unprefixed tables are V1 dead code).

### Phase 0 — instrumentation

```sql
-- One row per (source, day). Pipeline writes after each run.
CREATE TABLE redesign_source_daily_stats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid REFERENCES redesign_source_configs(id),
  source_name text NOT NULL,    -- denormalized for human reading
  category text NOT NULL,
  subbucket text,                -- nullable for News/Science
  run_date date NOT NULL,
  -- raw counts
  input_count int,               -- briefs pulled in phase_a_light
  probe_kept int,
  probe_thin int,
  probe_long int,
  curator_top5_count int,        -- ranked into top 5
  winner_top3_count int,         -- made it to bundle
  -- aggregates over the kept articles only
  avg_word_count float,
  avg_safety_total float,
  avg_interest_peak float,
  -- feed health
  feed_last_modified timestamptz,
  feed_fetch_ok boolean,
  paywall_count int,             -- body fetch returned a paywall stub
  no_image_count int,
  -- raw json for forensics
  raw_telemetry jsonb,
  created_at timestamptz DEFAULT now(),
  UNIQUE(source_id, run_date)
);
```

### Sub-bucket support

```sql
ALTER TABLE redesign_source_configs
  ADD COLUMN subbucket text,
  ADD COLUMN state text DEFAULT 'live'
    CHECK (state IN ('candidate','probation','live','watch','dropped'));

CREATE TABLE redesign_subbuckets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category text NOT NULL,        -- 'Fun'
  slug text NOT NULL,            -- 'fun_animals'
  display_name text NOT NULL,    -- 'Animals & Nature'
  description text,              -- shown to discovery agent + admin
  seed_reddit_subs jsonb DEFAULT '[]',
  seed_substack_categories jsonb DEFAULT '[]',
  seed_rss_lists jsonb DEFAULT '[]',
  weight float DEFAULT 1.0,      -- bundle composition weight
  active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  UNIQUE(category, slug)
);
```

Initial seed (one row per Fun sub-bucket from the brainstorm — Animals,
TIL/History, Travel, Records, Uplifting Humans, Cool Science).

### Phase 1 — Health Report

```sql
CREATE TABLE redesign_source_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  generated_at timestamptz DEFAULT now(),
  window_start date NOT NULL,
  window_end date NOT NULL,
  vertical text DEFAULT 'kidsnews',
  summary text,                  -- DeepSeek's overall summary
  sources jsonb,                 -- [{source_id, name, verdict, score, reasoning, stats}, ...]
  raw_input jsonb,               -- exact stats given to DeepSeek (for audit)
  prompt_version text            -- tracks which prompt revision generated it
);
```

### Phase 2 — Mining

```sql
-- One row per discovery run.
CREATE TABLE redesign_mining_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at timestamptz DEFAULT now(),
  finished_at timestamptz,
  vertical text DEFAULT 'kidsnews',
  category text NOT NULL,
  subbucket text,
  trigger text,                  -- 'cron_active' | 'manual_admin' | 'floor_reactive'
  status text DEFAULT 'running', -- 'running' | 'completed' | 'failed'
  candidates_discovered int,
  candidates_triaged int,
  candidates_pre_ranked int,
  candidates_promoted_to_probation int,
  notes text
);

-- Each candidate that survives triage gets a row.
CREATE TABLE redesign_source_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mining_run_id uuid REFERENCES redesign_mining_runs(id),
  feed_url text NOT NULL,
  display_name text,
  source_strategy text,          -- 'reddit' | 'substack' | 'rss_registry' | 'sibling'
  category text NOT NULL,
  subbucket text,
  -- triage result
  triage_passed boolean,
  triage_reasons jsonb,
  -- pre-rank result
  pre_rank_score float,
  pre_rank_reasoning text,
  -- final disposition
  state text DEFAULT 'discovered', -- 'discovered' | 'probation' | 'promoted' | 'rejected'
  rejection_reason text,
  promoted_to_source_id uuid REFERENCES redesign_source_configs(id),
  created_at timestamptz DEFAULT now(),
  UNIQUE(feed_url)
);
```

### Dynamic config tables

```sql
-- Numeric thresholds, lists, anything tunable.
CREATE TABLE redesign_engine_config (
  key text PRIMARY KEY,           -- 'probe.min_word_count' | 'probation.length_days' | 'discovery.reddit_seed' | ...
  value jsonb NOT NULL,
  description text,               -- human-readable purpose
  updated_at timestamptz DEFAULT now(),
  updated_by text
);

-- DeepSeek prompts, versioned.
CREATE TABLE redesign_engine_prompts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  prompt_key text NOT NULL,       -- 'mining.discover_query' | 'pre_rank.kid_appropriate' | 'weekly_verdict' | ...
  vertical text DEFAULT 'kidsnews',
  prompt_text text NOT NULL,
  variables jsonb DEFAULT '[]',   -- list of {{placeholder}} the prompt uses
  active boolean DEFAULT false,
  notes text,
  created_at timestamptz DEFAULT now(),
  UNIQUE(prompt_key, vertical, active)  -- only one active per (key, vertical)
);
```

Initial seed for `redesign_engine_config`:

| key | value | description |
|---|---|---|
| `probe.min_word_count` | `350` | Stage 1.5 lower gate |
| `probe.max_word_count` | `1200` | Stage 1.5 upper gate |
| `probe.max_per_cat` | `10` | Cap candidates per category before curator |
| `probation.length_days` | `5` | How long a candidate sits in probation |
| `probation.min_articles_to_pass` | `3` | Need at least N articles surviving probe to evaluate |
| `mining.cadence_days` | `14` | Active mining every 2 weeks |
| `mining.candidates_per_run` | `20` | How many fresh candidates to surface |
| `health.window_days` | `7` | Weekly report window |
| `health.cadence_cron` | `"0 6 * * 1"` | Every Monday 06:00 UTC |
| `floor.live_count` | `6` | Per-category target (sub-buckets sum to this for Fun) |
| `floor.subbucket_count` | `2` | Min live sources per Fun sub-bucket |
| `floor.alert_threshold` | `3` | Below this, page admin |
| `verdict.score_keep_min` | `7.0` | DeepSeek score ≥ this → KEEP |
| `verdict.score_drop_max` | `4.0` | DeepSeek score ≤ this → DROP suggestion |

## Build order

### Stage 0 — Instrumentation (½ day)

- Migration: `redesign_source_daily_stats`, `subbucket` column on
  `redesign_source_configs`, `state` column.
- Pipeline patch: at end of each run, write one row per source to the
  daily_stats table from the existing telemetry (we already capture
  most of these in `phase_a_probe.dropped_thin/long/kept`,
  `stage2_curator.picks`, `redesign_stories`).
- Seed sub-buckets table with Fun's 6 entries.
- Seed `redesign_engine_config` with the table above.

### Stage 1 — Health Report (1 day)

- Script `pipeline/source_health.py` — pulls last 7 days from
  `redesign_source_daily_stats`, formats per-source stats block,
  reads active prompt from `redesign_engine_prompts`
  (`prompt_key='weekly_verdict'`), calls DeepSeek, writes to
  `redesign_source_reports`.
- Workflow `.github/workflows/source-health.yml` — cron from
  `redesign_engine_config['health.cadence_cron']`.
- Admin tab "Source Health" in `website/admin.html` — read latest
  report row, render table with per-row enable/disable button that
  flips `redesign_source_configs.enabled`.

### Stage 2 — Mining Engine pilot on Fun (3-5 days code + 5 days probation)

- Script `pipeline/source_mining.py` orchestrates:
  - **Phase 1: discovery** — agents per strategy (Reddit subreddit
    listings, Substack leaderboards, RSS aggregators, sibling discovery).
    Strategy code reads input lists from `redesign_engine_config`.
  - **Phase 2: triage** — fetch each candidate, check feed validity,
    article count, body extractability, word_count distribution.
    Insert survivors into `redesign_source_candidates` with
    `triage_passed=true`.
  - **Phase 3: pre-rank** — sample 5 articles per survivor, format
    block, read prompt from `redesign_engine_prompts` (`prompt_key=
    'pre_rank.kid_appropriate'` + vertical), call DeepSeek, score 0-10.
    Top 12 advance.
  - **Phase 4: probation** — flip 12 candidates to
    `state='probation'`, also insert into `redesign_source_configs`
    with `state='probation'` and `enabled=true` so the daily pipeline
    starts ingesting them. Daily pipeline writes their daily_stats
    rows just like live sources.
  - **Phase 5: verdict** — after `probation.length_days` days, pull
    each candidate's daily_stats, format block, read prompt
    (`prompt_key='probation_verdict'`), DeepSeek returns
    PROMOTE/BENCH/REJECT. Code applies state changes.
- Admin tab "Mining Console" — manual trigger button per (category,
  subbucket), live view of in-flight runs, list of probation
  candidates with verdict pending or recently decided. Each candidate
  has Approve/Reject buttons that override the auto-verdict.

### Stage 3 — Floor monitor (½ day, after pilot succeeds)

- Daily cron checks `live_count` per category and per Fun sub-bucket.
- Below floor → triggers a mining run with `trigger='floor_reactive'`.
- Below `alert_threshold` → also writes to admin notification stream.

## Dynamic-config touchpoints

Every tunable value in the pipeline above must be sourced from
`redesign_engine_config` or `redesign_engine_prompts` at runtime.
Concretely:

| Value | Stored in | Read by |
|---|---|---|
| Word-count range | `engine_config['probe.min_word_count']` etc. | Pipeline `phase_a_probe`, mining triage |
| Probation duration | `engine_config['probation.length_days']` | Mining engine verdict timer |
| Discovery seed lists | `engine_config['mining.reddit_seed']` etc. | Mining discovery phase |
| Sub-bucket descriptions | `redesign_subbuckets.description` | Discovery prompts, admin UI |
| All prompts | `redesign_engine_prompts` | Every DeepSeek call |
| Image size minima | `engine_config['probe.image_min_kb']` etc. | Pipeline body verify |
| Forbidden-word list | `engine_config['safety.forbidden_words']` | Already exists in `redesign_categories` — migrate to engine_config |
| Vertical filter prompts | `engine_prompts[vertical='kidsnews']` etc. | Mining pre-rank, weekly verdict |

**No hardcoded strings, numbers, lists, or thresholds anywhere in the
engine code.** Code reads config and panics with a clear error if a
required key is missing.

## Admin UI surfaces (future tabs)

Three new tabs in `website/admin.html`, all React components with the
existing Babel-standalone setup:

1. **Source Health** — weekly report, per-row enable/disable.
2. **Mining Console** — trigger runs, view probation pool, override
   verdicts.
3. **Engine Config** — KV editor for `redesign_engine_config` and
   prompt editor for `redesign_engine_prompts` with diff/preview/
   activate-version semantics. **(Built last, after engine works
   well enough that you actually want to tune it.)**

## DeepSeek prompt set (initial)

All seeded into `redesign_engine_prompts` as `active=true`,
`vertical='kidsnews'`. Each is a Jinja-style template with `{{var}}`
placeholders documented in the `variables` jsonb column.

| prompt_key | purpose | variables |
|---|---|---|
| `mining.discover_reddit` | Given a sub-bucket description, suggest 10-20 candidate subreddit names | `{{subbucket_name}}`, `{{description}}`, `{{age_target}}` |
| `mining.discover_substack` | Same, for Substack newsletters | same |
| `pre_rank.kid_appropriate` | Score a candidate source 0-10 on age-appropriateness given 5 sample articles | `{{age_target}}`, `{{subbucket}}`, `{{sample_articles}}` |
| `probation_verdict` | Decide PROMOTE / BENCH / REJECT given 5-day stats | `{{stats_block}}`, `{{thresholds}}` |
| `weekly_verdict` | Per-source weekly KEEP / WATCH / DROP given 7-day stats | `{{stats_block}}`, `{{thresholds}}` |

Each prompt's first version is drafted in this spec and committed
into the seed migration. Future edits go through the admin Engine
Config tab and bump the active version.

## Open questions

1. **Repository placement** — proposing `news-v2` repo, with engine
   code under `pipeline/source_engine/` so it can be extracted later.
   User to confirm.
2. **Image-size threshold** — what counts as "appropriate"? Need a
   baseline number for `engine_config['probe.image_min_kb']`. Plan
   to derive empirically: take last 30 days of bundle articles, look
   at og:image file sizes, set threshold at 5th percentile.
3. **Probation impact on daily bundle** — do probation sources count
   toward curator candidate pool, or stay isolated until promoted?
   Proposing isolated (probation has its own daily fetch loop, doesn't
   feed curator) so a bad probation candidate doesn't pollute live
   bundles. User to confirm.
4. **Reddit-as-source mechanics** — Reddit RSS returns posts (titles +
   external links). For the kidsnews use case, do we treat the post
   itself as the article (title + Reddit text), or follow the link to
   the actual destination article? Mixed feeds work better with the
   latter; needs a "follow link" enrichment step. Proposing follow-
   link with fallback to the post itself if the link is dead.
5. **Mining cadence** — confirmed active (every 2 weeks). User
   reserves the right to switch to passive/hybrid later.
6. **Cross-vertical extraction** — when 21mins-finance comes online,
   the engine should accept a `vertical` parameter. Schema already
   supports it; code needs to read vertical-specific prompts. Defer
   actual second-vertical to that later project.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Probation candidates pollute live bundle | Isolation flag (Q3 above); daily pipeline filters by `state='live'` |
| DeepSeek hallucinates Reddit/Substack URLs | Triage step verifies feed actually exists before scoring |
| Cron fires while existing run still in flight | Reuse the `concurrency: daily-pipeline` group pattern from this morning's fix |
| Engine config typo silently breaks pipeline | Code reads config at startup, validates required keys, fails fast |
| Sub-bucket weights starve under-represented buckets | Curator post-validator ensures Fun bundle pulls from ≥3 distinct sub-buckets when possible (extension of today's source-diversity validator) |
| LLM cost balloons | Mining runs are bounded (20 candidates × few prompts each). Health report is one prompt per week. Floor-reactive only when needed. Estimate: <50 DeepSeek calls/week steady state. |

## Success criteria (v1 done definition)

- Phase 0: 7 consecutive days of daily_stats rows present with
  non-null counts for every live source.
- Phase 1: First weekly report visible in admin, with per-source
  verdicts that match human intuition for at least 80% of rows.
- Phase 2: First Fun mining run discovers ≥30 candidates, triages
  to ≥10 survivors, pre-ranks, runs probation, and produces a verdict
  list. At least 1 candidate promotes to live.
- After 30 days: Fun has ≥6 live sources spanning ≥4 sub-buckets.

## Next steps after this spec is approved

1. User reviews this spec, requests changes.
2. After approval: write implementation plan
   (`docs/superpowers/plans/2026-04-27-source-engine-plan.md`)
   with task-by-task TDD steps for Stage 0 first.
3. Build Stage 0 (instrumentation) and verify daily_stats rows
   land for 2-3 days before starting Stage 1.
4. Build Stage 1 (health report) — this is the first user-visible
   output.
5. Build Stage 2 (mining engine) only after Stage 1 stats are
   trustworthy.
