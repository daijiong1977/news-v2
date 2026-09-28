# 2026-09-28 pre-DeepSeek pipeline preview

Read-only local replay of the open PR branch on 2026-09-28 at about 17:45 ET.
It fetched current feeds and article bodies, read seven-day same-category
publication history, and ran the JEV prefilter, section routing, topic tagging
and complete-catalog ranking. It stopped before **every DeepSeek call**: no
editorial whole-list ranking, curator, rewrite, full-text independent safety
review, checkpoint/run row, email, publication or site sync was performed.
These are unapproved editorial candidates, not safe-to-publish articles.

**Historical snapshot, not the current PR funnel:** this replay was taken
before the ranked-body-probe change. It opened 97 article pages after JEV's
first screen (News 40, Science 27, Fun 30) to count source words. The current
proposal first ranks RSS titles/summaries, then opens only the top 12 originals
per section; if fewer than six pass source-body/image checks (seven for Fun's
existing curator input), it opens the next six, repeating only as needed.
Therefore the 29/20/21 catalog below must **not** be used as the new
DeepSeek input or as a measured cost/quality result for the reordered funnel.

| Stage | News | Science | Fun |
| --- | ---: | ---: | ---: |
| Raw feed briefs | 46 | 28 | 36 |
| After prior-seven-day history | 46 | 27 | 33 |
| After local forbidden-title screen | 42 | 27 | 32 |
| After JEV prefilter | 40 | 27 | 30 |
| After source-body gate (old order) | 35 | 27 | 27 |
| After section routing | 34 | 28 | 27 |
| Unique JEV catalog | 29 | 20 | 21 |

One replay took 47.5 seconds. JEV reported 100/100 prefilter scores in
4.9 seconds and 89/89 catalog scores plus 89 pair checks in 22.2 seconds;
section routing and topic tagging also called JEV. The preview was run twice
because the first terminal output was truncated: **both** runs used JEV, and
neither called DeepSeek. The exact JEV charge must be read from its billing
console; no dollar estimate is inferred from request counts.

This PR applies source-body gates of News 350–1,200, Science 350–1,500, Fun
250–1,200 words. Today **zero** Science originals were 1,201–1,500 words,
so increasing that Science ceiling did not change this sample's eligible pool.
BBC Tennis's 254-word Laver Cup result did pass the new Fun minimum. A
339-word TIME for Kids item entered Science *after* passing Fun's 250-word
gate; routing currently does not reapply the destination section's minimum.
That is a separate cross-section gate issue to evaluate, not evidence that
Science's 350-word input floor was met.

The News/Fun whole-list DeepSeek ranking inputs use titles and short summaries,
not full bodies, so the Science 1,500-word source limit has no direct cost there.
If a longer Science candidate later reaches rewriting, the rewriter passes up
to 2,500 source words; a test confirms a 1,500-word source is not truncated by
this application's prompt builder. This does not assert any current DeepSeek
service context-window specification.

The whole-list DeepSeek step would receive all 29 News titles below. Fun has
8 candidates above its 0.50 JEV floor, exceeding the conditional 7-slot
threshold, so its 21-title list would also go to DeepSeek. Science does not
use this whole-list comparison; its JEV-selected six are marked below.

## News — 29 titles before whole-list DeepSeek ranking

`*` marks JEV's preliminary six; DeepSeek may reorder this list.

1. * SpaceX's Starship launches on first orbital mission from Texas — NPR World, 617w
2. * Russian drones hammer apartments and cultural landmark in Ukraine, killing 7 — PBS NewsHour, 571w
3. * Ukraine uses drones to make airdrops of aid to occupied city of Oleshky on brink of starvation — CBC World, 641w
4. * Hurricane Polo threatens Mexico's Pacific coast with landfall expected today — CBC World, 786w
5. * California health officials warn of possible measles exposure in 6 counties — NPR World, 485w
6. * Contradicting Trump, Pope Leo says AI safety concerns not 'fake news' — PBS NewsHour, 664w
7. What we know about the suspected U.K. terror plot. And, why the Gulf remains in limbo — NPR World, 448w
8. Remains of dozens of suspected kidnap victims found in Nigerian forests — BBC News, 394w
9. U.K. police arrest 5 near airbase used by U.S. on suspicion of preparing a terrorist act — CBC World, 595w
10. Pope Leo wraps up France trip by urging Europe to blunt 'desire for domination' driving today's wars — PBS NewsHour, 720w
11. Seoul summons Ukraine envoy over North Korean prisoner-of-war row — BBC News, 569w
12. Myanmar military airstrike hits market, killing at least 33 people in Rakhine state — CBC World, 402w
13. Four bodies found after avalanche hits Himalayan climbing group — BBC News, 481w
14. Nor'easter wallops Northeast coastal communities — NPR World, 714w
15. Trump's immigration push has largely spared farms. Idaho dairymen worry it won't last. — NPR World, 710w
16. Schools are experimenting with AI with little evidence or policy to guide them — NPR World, 749w
17. Trump aims to leave a physical legacy in D.C., bulldozing norms along the way — NPR World, 846w
18. Trump's tariffs are unpopular in Maine. A Republican senator may pay the price — CBC World, 589w
19. How the phrase 'Lower 48' became a fixture in Alaska's high-stakes Senate race — PBS NewsHour, 782w
20. As work requirements kick in for Medicaid, some states are taking a tougher stance — PBS NewsHour, 690w
21. Inside Yemen's front-line city as Houthis battle for control — BBC News, 611w
22. In a relatively mild speech, North Korea uses UN platform to lament 'mutual distrust' and tension — PBS NewsHour, 626w
23. Iran court upholds lashes sentence for singer who performed without hijab — BBC News, 592w
24. WATCH: Trump says Perdue 'was probably talking about Taiwan' in saying Trump offered Xi arms sales — PBS NewsHour, 692w
25. A bankrupt Camp Mystic seeks to sell the property as its legal troubles grow — PBS NewsHour, 494w
26. TikTok, X reportedly barring ads for documentary about Elon Musk — CBC World, 552w
27. Paramount and States Defend Antitrust Settlement From Sen. Booker’s Criticisms — Variety, 478w
28. Stand-up comic released after being convicted of insulting Erdoğan — BBC News, 491w
29. Plan for controversial Sydney data centre scrapped after push-back — BBC News, 468w

The top six show three serious-risk stories and a possible Science/News
misclassification (SpaceX). This is a reason for the later editor and the
independent finished-article safety review, not a claim they will publish.

## Fun — 21 titles before conditional whole-list DeepSeek ranking

`*` marks JEV's preliminary seven.

1. * Robot dog runs a marathon faster than the average human, all on a single charge — Popular Science, 691w
2. * Zverev comeback leads Europe to Laver Cup victory — BBC Tennis, 254w
3. * Nigerian attempts to break world record by dancing non-stop for seven days — BBC News, 362w
4. * Teen inventor creates a new way to fight microplastics — DOGOnews, 350w
5. * Multiple generations honoured at MTV VMAs as Taylor Swift, Madonna win, Dolly Parton and Nirvana remembered — CBC World, 489w
6. * How To Watch Coyote Vs. Acme At Home — /Film, 453w
7. * Avengers: Endgame Encore's TVA 'Multiverse Is Collapsing' Scene Explained By Directors — /Film, 871w
8. ‘Avengers: Doomsday’ Star Alan Cumming Says ‘I Don’t Fully Understand the Plot’ and Only Acted With Florence Pugh’s Stunt Double — Variety, 362w
9. Before Becoming A Movie Legend, Kurt Russell Guest-Starred In A '60s Spy TV Series — /Film, 540w
10. Dynasty Sports Film Festival Launches to Celebrate Intersection of Sports and Cinema — IndieWire, 620w
11. Jason Momoa's Lobo Performance Slammed By DC Comics Legend Grant Morrison — /Film, 833w
12. Sundance Favorite ‘Hold Onto Me’ Is Cyprus’ First-Ever Best International Feature Oscar Submission — IndieWire, 524w
13. Playing 'La Bamba' for an hour? Must be a Mexican fandango! — NPR Music, 806w
14. Singer Tinashe is a 'Popstar' who enjoys exploring genres on her latest album — NPR Music, 440w
15. ‘Musk,’ ‘You Can See Everything,’ and More to Screen at Inaugural Ojai Documentary Film Festival — IndieWire, 597w
16. Boox Announces the Picco, Its Smallest E-Reader Ever (2026) — Wired Gear, 460w
17. Bose Launches New Wired Earbuds After More Than a Decade — Wired Gear, 571w
18. Angela Autumn brings a new sound to her Appalachian roots — NPR Music, 713w
19. Mighty Sparrow, King of Calypso Music, Dead at 91 — Rolling Stone Music, 783w
20. Brandi Carlile Plots ‘Burn the Setlist’ All-Request Tour — Rolling Stone Music, 522w
21. Broadway Musicals Are in Crisis. Can Major League Baseball and Neil Patrick Harris Help? — IndieWire, 761w

The JEV preliminary seven include a streaming/how-to-watch item and adult
franchise analysis, so the subsequent DeepSeek whole-list ranking and curator
must still enforce a genuine child-fun threshold. This list must not be used
as a substitute for finished-article safety review.

## Science — JEV top ten (no whole-list DeepSeek step)

1. Small but Fierce — TIME for Kids, 339w (routed from Fun)
2. 160-million-year-old proteins show surprising power against superbugs — ScienceDaily Top Environment, 719w
3. SpaceX's Starship reaches orbit for the first time, then returns early and explodes — Live Science, 756w
4. Scientists were wrong about this strange mammal for nearly 40 years — ScienceDaily Top Environment, 658w
5. Ancient shark graveyard discovered in egyptian desert — DOGOnews, 357w
6. 'It is something we must know before we go where no man has gone before': Readers react to NASA's Roman telescope mission — Live Science, 474w
7. Blood tests reveal why astronauts get constipated in space — ScienceDaily All, 580w
8. James Webb reveals why planet formation is a race against time — ScienceDaily Top Technology, 841w
9. US Cold War-era spy satellite explodes above Earth — and nobody knows why — Live Science, 982w
10. Is the universe infinite? The answer gets weird fast — ScienceDaily All, 480w

The top six were JEV's preliminary send set. Source and topic quality still
need the curator's judgment; this preview stopped before that step.
