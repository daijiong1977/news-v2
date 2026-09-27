# 2026-09-27: repeated US storm and two severe-weather stories

## Evidence

The scheduled [Daily run 36302246549](https://github.com/daijiong1977/news-v2/actions/runs/36302246549) used merged main `fb54576`, so this was not an old deployment. It finished successfully while publishing an editorial defect.

- Sep 26 / BBC: **Nor'easter brings flooding as New York and New Jersey declare emergency**.
- Sep 27 / CBC: **Powerful storm causes widespread flooding, outages in northeast U.S.**. Its saved summary reports the same slow-moving US northeast coastal storm; the feed image caption explicitly identifies the nor'easter and New Jersey on September 26.
- Sep 27 / BBC: **Bangkok roads submerged as flood disaster declared**. This is a different event, but shares the severe-weather topic.

## Root causes

1. The seven-day database window was correct and readable. Logs show the original BBC storm URL being removed. However, `jev_rank._Pairs.already_published` required **two shared headline tokens** before a semantic comparison. The CBC/BBC headlines share only `flooding`. The model never compared this pair. Different source URLs also prevented exact-URL rejection.
2. Historical matches rejected from the shortlist were still retained at the end of the reserve pool. Late promotion had same-day checks but no complete seven-day semantic review. This was a second route for historical duplicates to return, even though it was not needed for the reported CBC leak.
3. Topic diversity was a soft initial preference, weakened by later attrition. The curator's CNN ownership choice failed verification because NPR supplied a generic social image. The Hawaii hurricane and Trump/Iran choices subsequently failed the independent safety check; a drone-story spare also failed safety. The Bangkok flood was promoted, yielding only three safe candidates and two weather topics. No further search for a new topic ran once the count reached three. A later source-only reordering could also undo earlier topic ordering when more alternatives existed.

The US/Bangkok stories must not be classified as the same event merely to enforce variety. Same-event dedup is mandatory; topic variety remains a preference when qualified alternatives exist.

## Fix

- Early historical pair checks now accept one shared token, catching the reported pair sooner. This remains an optimization, not the final protection.
- Known historical duplicates are removed from reserves, not merely demoted.
- Per the owner's updated scope, historical and current-candidate comparisons are section-local: **News vs News, Science vs Science, Fun vs Fun**. Early URL/title filtering, ranking and final review follow that policy. A seven-day history normally has 21 articles per section.
- New `PublicationHistoryGuard` compares each candidate against its **entire seven-day, same-section history** in one typed JEV Choice request with no lexical gate. Exact normalized URLs/titles are handled in code. An uncertain Choice gets at most one binary confirmation. Invalid, failed or unresolved decisions remain unverified, not clear.
- Initial rewritten candidates, late spares and deep-dig candidates must clear the guard. A final assertion runs after loading the safety checkpoint as well, before emit/persist/upload. Reviews are cached within the run and report calls, tokens when returned, elapsed time and blocked candidates.
- After attrition, try qualified different-topic spares and, if needed, a bounded deeper pickup from the already selected feeds even when there are three safe articles. Joint final selection preserves important News / Science publisher requirements, then topic variety, then publisher/source variety. If no alternate topic survives, record an explicit warning.
- After safety and history review, a section with fewer than three fresh stories searches the **entire scored catalog from today's probed candidates**, rather than only the former top-ten reserve. The curator still sees at most 6/6/7 candidates for News/Science/Fun. The ranking stage removes detected same-event duplicates when forming this full catalog. Late promotion prefers a different confident topic group; only when no qualified different-group article survives does it take the highest-ranked article from a repeated or unknown group. There is no extra same-day model check during refill. The seven-day same-section historical check remains in force for every promoted candidate, and body/rewrite/independent safety checks remain mandatory. If the catalog and deeper same-day feed search are exhausted, publish the qualified fresh survivors even when fewer than three. The mega path disables previous-bundle carry-over for these short sections.

## Verification and limitations

Offline regression cases cover the actual one-token headline pair, zero-shared-token paraphrases, exact URL tracking variants, different-region floods, uncertain/invalid/outage responses, one bounded binary confirmation, call budgets, reserve exclusion, checkpoint review, full-catalog retention, different-group priority, same-group fallback without another model call, and final topic/publisher combinations.

Read-only JEV replay used the saved Sep-27 candidate briefs and the published records from Sep 20–26. After switching to **21 same-section records per judgment**, it identified the CBC storm as repeating the Sep-26 BBC event, while clearing the other eight published articles, including Bangkok and the diplomatic meeting.

| Replay scope | Requests | Input tokens | Output tokens | Judgment time |
| --- | ---: | ---: | ---: | ---: |
| Initial experiment: all 63 records per candidate | 9 | 27,446 | 5,808 | 2.34s |
| Final policy: own section's 21 records | 9 | 11,798 | 2,028 | 2.38s |

The final sample used about 58% fewer total reported tokens; it did not demonstrate a latency improvement. News alone took three calls, 3,894 input / 678 output tokens, and 0.71s. These are SDK-reported usage counts, not a billed-cost measurement. The full pipeline may check more candidates while replacing rejected items; all three guards share a run-level limit of 40 requests and a 60-second accumulated review budget.

An initial three-story probe produced a low-confidence diplomacy answer, motivating bounded binary confirmation. Later output varied and cleared it at the normal threshold. This small sample is not a general model calibration result. Model false positives/negatives remain possible; full-catalog topic tagging and upfront pair checks can add JEV calls versus the old top-ten reserve, while refill itself makes no extra same-day comparison. No production pipeline rerun or public-content edit was performed for this fix.

Tuning: `publication_history.py` contains confidence, request-count and review-time limits; `jev_rank.rank_briefs` forms the candidate catalog; `full_round.promote_spare_and_rewrite` implements group-first refill; `editorial_policy.prefer_final_editorial_diversity` contains final combination priorities. Roll back by reverting the PR, acknowledging that the prior history leak and old carry-over behavior would return.
