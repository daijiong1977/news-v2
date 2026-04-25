# Gotchas — Small Places Where Bugs Hide

Append entries chronologically. Each entry: **Date · Symptom · Root cause · Fix · Where it lives**.

Aim is to capture subtle traps that silently produce wrong-looking output (not crashes — those find themselves). Keep entries ≤ 10 lines.

---

## 2026-04-25 · og:image returned with face cropped off

**Symptom.** Hero photo on the published article had the top of the subject's head cut off (e.g. "ENIAC Replica" article on news.6ray.com — teacher's eyes/forehead missing).

**Root cause.** The article's `<meta property="og:image">` URL embeds publisher-CMS pre-crop directives in its query string. IEEE Spectrum / Squarespace / Imgix-style URLs use `coordinates=`, `rect=`, or `crop=` to force a 2:1 social-share banner. For portrait photos that crop chops heads/feet. Our pipeline downloaded the cropped variant verbatim — `image_optimize.py` only scales, never re-crops — so the bad framing survived all the way to the live site.

**Fix.** `cleaner.py · _strip_banner_crop_params()` strips `coordinates`, `rect`, `crop` from any og:image URL before it gets stored or downloaded. Verified IEEE Spectrum returns the natural 1200×938 (4:3) once `coordinates=` is removed.

**Where to look if it regresses.** `pipeline/cleaner.py · _extract_og_image()` — every call routes through the strip helper. If a new publisher uses a different param name, add it to `_BANNER_CROP_PARAMS`.

---

## 2026-04-25 · Keyword count is not a bundle-validity signal

**Symptom.** Mega run 24921336686 produced 9 finished stories, persisted them to Supabase, then `pack_and_upload` rejected the bundle: 4 News slots had 0 keywords (need ≥3). The article content was fine — the keyword arrays just got drained by the post-LLM literal-appearance filter.

**Why 0 is acceptable.** Keywords aren't editorial signal — they're vocabulary scaffolding for kids. A plain-language body can legitimately yield 0 qualifying terms. Blocking the bundle on keyword count just means a complete article gets withheld over a missing teaching aid.

**Future direction.** Replace the LLM's subjective "above grade-2/3" judgment with a deterministic Google-10k-frequency-rank filter applied server-side: rank >2000 for easy, rank >3000 for middle, plus a small allowlist of named-entity / topical terms the article makes salient. The LLM should emit ALL nouns/verbs from the body; the rank filter does the curation.

**Fix shipped today.** `pipeline/pack_and_upload.py · DETAIL_MIN` no longer lists keywords. The other detail fields (`questions`, `background_read`, `Article_Structure`) still gate the bundle — those ARE editorial signal.
