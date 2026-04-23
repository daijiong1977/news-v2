# news-v2

Working repo for the KidsNews v2 redesign.

**Future deploy target:** `news.6ray.com` (separate domain from the v1 site at `kidsnews.6ray.com`).

**Relationship to other repos:**
- `kidsnews` (reference only, untouched) — v1 production site at `kidsnews.6ray.com`. The v2 UI consumes v1 payloads during Phase 1.
- `kidsnews-v2` (future, not yet created) — deploy target. Phase 3 pipeline will push generated zip bundles here, Vercel auto-deploys.

## Layout

```
news-v2/
├── docs/superpowers/        # specs + plans
├── newdesign/               # React prototype (source of truth for UI design)
├── website/                 # static UI — the thing that ships
│   ├── index.html           # prototype, adapted for real payloads
│   ├── *.jsx                # copied from newdesign/, adapted
│   ├── payloads/            # v1 listing JSON (local snapshot for Phase 1 dev)
│   ├── article_payloads/    # v1 article detail JSON (local snapshot)
│   └── article_images/      # v1 WebP images (local snapshot)
├── supabase/migrations/     # parallel redesign schema (for Phase 2 pipeline)
├── PIPELINE-IMPLEMENTATION.md  # Phase 2 reference
└── vetter-comparison-test.mjs  # Phase 2 reference
```

## Phase 1 (current): UI only

Local dev:
```bash
cd website
python3 -m http.server 8000
open http://localhost:8000/
```

The UI loads real v1 payloads from `website/payloads/` and `website/article_payloads/`.

## Phase 2 (next): Pipeline

Node.js pipeline per `PIPELINE-IMPLEMENTATION.md`:
Tavily discover → Jina read → DeepSeek vet → DeepSeek rewrite → Supabase `redesign_*` tables.

Contract: 6 search + 4 RSS → 10 candidates → vet → top 5 detailed → 3 published per category, per day.

## Phase 3 (future): Zip + sync

Pipeline generates `website-v2-YYYY-MM-DD.zip` → pushes to `kidsnews-v2` repo → Vercel deploys to `news.6ray.com`.
