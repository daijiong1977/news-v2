"""Cache-only batch editor; incremental Python collection cannot bypass gates."""
import hashlib
from pathlib import Path

from .agent_shadow_batch import BatchEditor, sports_preference
from .agent_shadow_source_first import collect, validate_priority_batch
from .agent_shadow_lengths import original_band


class SourceFirstEditor(BatchEditor):
    def check_batch(self, value, originals, cat):
        return validate_priority_batch(value, originals, cat)

    def originals(self, cat, limit=8):
        from .agent_shadow import read
        from .full_round import _canonical_source_url
        cache = read(self.root / 'bodies.json')
        photos = read(self.root / 'candidate-images.json')
        index = {b['id']: b for b in self.snapshot['candidates']}
        past = {_canonical_source_url(r.get('source_url', '')) for r in self.snapshot['history'][cat]}
        lo, hi = original_band(cat)
        result = []
        for score in self.catalog[cat]:
            sid = score['id']
            if score['initial_risk'] >= 4 or score['history_status'] != 'clear' or score['history_confidence'] < .7:
                continue
            art = cache.get(sid)
            if not art or not lo <= art['word_count'] <= hi:
                continue
            if _canonical_source_url(art.get('evidence_url') or art['link']) in past:
                continue
            photo = photos[sid]
            asset = Path(photo['path'])
            if asset.is_symlink() or not asset.is_file() or asset.stat().st_size < 20000 or hashlib.sha256(asset.read_bytes()).hexdigest() != photo['sha256']:
                raise ValueError('Qualified photo cache changed/missing: ' + sid)
            art = {**art, 'link': art.get('evidence_url') or art['link']}
            result.append({**score, 'category': cat, 'article': art})
            if limit is not None and len(result) == limit:
                break
        return result

    def extend(self, cat, target, section):
        from .agent_shadow import read, write, RANK_RULES, validate_catalog, AnswerRejected, pin_task_answers, CATS
        pending = self.root / f'pending-source-plan-{cat}.json'
        if pending.exists() and not read(pending)['applied']:
            return self.plan_increment(cat, target, pending)
        consumed = {sid for p in self.root.glob(f'batch-{cat}-*.json') for sid in read(p)['considered']}
        old_catalog = self.catalog[cat]
        self.catalog[cat] = [b for b in old_catalog if b['id'] not in consumed]
        try:
            if self.originals(cat):
                return target + 8
        finally:
            self.catalog[cat] = old_catalog
        # All configured sources are frozen. No Agent discovery or unvetted URL.
        while True:
            collection = read(self.root / 'source-collection.json')
            if not any(s['status'] == 'pending' for s in collection['sections'][cat]['sources']):
                return None
            old_ids = {b['id'] for b in self.snapshot['candidates']}
            candidates = collect(self.root, {}, self.snapshot['date'], expand=cat)
            fresh = [b for b in candidates if b['id'] not in old_ids]
            if not fresh:
                continue
            # Save new originals before handoff. Stable ID restores this request on exit 2.
            write(pending, {'candidates': fresh, 'applied': False})
            break
        return self.plan_increment(cat, target, pending)

    def plan_increment(self, cat, target, pending):
        from .agent_shadow import read, write, RANK_RULES, validate_catalog, CATS
        from .news_topics import TOPICS_BY_CATEGORY
        fresh = read(pending)['candidates']
        ids = {b['id'] for b in fresh}
        key = f'plan-source-refill-{cat}-' + hashlib.sha256('|'.join(sorted(ids)).encode()).hexdigest()[:12]
        def check(v):
            errors = validate_catalog(v, ids)
            if not errors and any(v['catalog'][c] for c in CATS if c != cat):
                errors.append('Incremental plan only requested section; do not alter settled sections')
            if not errors and any(b['topic'] not in TOPICS_BY_CATEGORY[cat] for b in v['catalog'][cat]):
                errors.append('Canonical topic required')
            return errors
        result = self.ask(self.root, key, RANK_RULES + sports_preference(self.snapshot, cat) +
            '\nINCREMENTAL: Only requested section may be nonempty. These candidates passed Python body/photo checks. Keep ready articles unchanged.',
            {'category': cat, 'date': self.snapshot['date'], 'candidates': fresh,
             'history': self.snapshot['history'], 'accepted': [
                 {'id': a['candidate']['id'], 'title': a['entry'].get('headline', ''),
                  'topic': a['candidate']['topic'], 'publisher': a['candidate'].get('publisher', ''),
                  'source_excerpt': a['candidate']['article']['body'][:1200]}
                 for a in read(self.root / 'editor-state.json')[cat]['accepted']],
             'topic_labels': list(TOPICS_BY_CATEGORY[cat])}, check)['catalog'][cat]
        known = {b['id'] for b in self.snapshot['candidates']}
        self.snapshot['candidates'].extend(b for b in fresh if b['id'] not in known)
        catalog_ids = {b['id'] for b in self.catalog[cat]}
        self.catalog[cat].extend(b for b in result if b['id'] not in catalog_ids)
        if cat == 'News':
            self.catalog[cat].sort(key=lambda b: -b['importance'])
        self.save()
        write(pending, {'candidates': fresh, 'applied': True})
        self.boundary(self.root, key, self.stepwise)
        return target + 8
