# Shadow Fun short-story floor

2026-09-30 Science/Fun hybrid completed but rejected four Fun drafts solely on
middle word count: 247 vs 250, 191 vs 250, 291 vs 300, and 287 vs 300.
User approved 180 words instead of padding otherwise complete short stories.

Shadow-only `agent_shadow_lengths.py` now owns source and output overrides:
source 180–1200; middle 180–350 for short sources, otherwise 180–410.
Easy stays 120–220 for 180–349-word sources, otherwise 140–270.
Writer, modifier and validator share ranges. Both body-pool paths share the
source floor. Production wordcount_policy and production generation are unchanged.

Four regression cases failed before and pass after; tests also cover 179 rejection,
unchanged News/Science and Fun upper bounds, modifier and production isolation.
Python 3.10 relevant suite: 163 passed. No real model, DB writes or deployment.
Use a new run directory; do not edit accepted answers of the completed run.
