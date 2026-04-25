# Gotchas — Small Places Where Bugs Hide

Append entries chronologically. Each entry: **Date · Symptom · Root cause · Fix · Where it lives**.

Aim is to capture subtle traps that silently produce wrong-looking output (not crashes — those find themselves). Keep entries ≤ 10 lines.

---

## 2026-04-25 · og:image returned with face cropped off

**Symptom.** Hero photo on the published article had the top of the subject's head cut off (e.g. "ENIAC Replica" article on news.6ray.com — teacher's eyes/forehead missing).

**Root cause.** The article's `<meta property="og:image">` URL embeds publisher-CMS pre-crop directives in its query string. IEEE Spectrum / Squarespace / Imgix-style URLs use `coordinates=`, `rect=`, or `crop=` to force a 2:1 social-share banner. For portrait photos that crop chops heads/feet. Our pipeline downloaded the cropped variant verbatim — `image_optimize.py` only scales, never re-crops — so the bad framing survived all the way to the live site.

**Fix.** `cleaner.py · _strip_banner_crop_params()` strips `coordinates`, `rect`, `crop` from any og:image URL before it gets stored or downloaded. Verified IEEE Spectrum returns the natural 1200×938 (4:3) once `coordinates=` is removed.

**Where to look if it regresses.** `pipeline/cleaner.py · _extract_og_image()` — every call routes through the strip helper. If a new publisher uses a different param name, add it to `_BANNER_CROP_PARAMS`.
