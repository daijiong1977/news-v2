"""Opt-in 8 originals -> one HTTP five-draft batch -> native three + modifier.

Every batch is frozen before the next handoff. Accepted sections are never replayed.
No publication or Supabase writes happen here.
"""
from copy import deepcopy
import hashlib

from .agent_shadow_autonomous import AutonomousEditor, safe_image
from .agent_shadow_editor import validate_rewrite
from .editorial_policy import publisher_key
from .news_sources import NewsSource


# 2026-10-01: family preference was lost between metadata rank and final pick.
FAMILY_SPORTS_PREFERENCE = '''
FAMILY SPORTS PREFERENCE (Fun only): these children are fans of famous tennis and swimming
stars. Among eligible, comparably good stories, prioritize widely recognized champions/stars
and meaningful current matches, comebacks, exciting performances and records (e.g. Djokovic).
Prefer these to general sports reports or career retrospectives; do not automatically rank
a tearful retirement above an engaging current match just for its emotional arc or milestone.
Keep an eligible star story in the first original-text pool and five-draft shortlist when possible,
then carry this preference into the final three. Do not let it displace News importance or
Science diversity. Safety, source support and same-section historical deduplication still win.
Do not invent family favorite names or events absent from the supplied candidates. No forced
sports quota when there is no suitable story. Compare child interest, not celebrity alone.
'''


def sports_preference(snapshot, category=None):
    from .agent_shadow_profiles import uses_native_details
    return FAMILY_SPORTS_PREFERENCE if uses_native_details(snapshot) and category in (None, 'Fun') else ''


def publisher_first_catalog(rows, candidates, sources):
    """Give each Science publisher one early fetch opportunity, then retain rank.

    This is not an approval or a quota: all normal history, safety and body gates
    still apply. Failed hosts cannot monopolize the first twelve paid fetches.
    Only fresh pools use this order; frozen drafts and accepted articles stay put.
    """
    index = {b['id']: b for b in candidates}
    seen, first, rest = set(), [], []
    for row in rows:
        article = index[row['id']]
        source = sources.get(article['source']) or {'rss_url': article.get('link', ''), 'name': article['source']}
        publisher = article.get('publisher') or publisher_key(source)
        if publisher not in seen:
            seen.add(publisher)
            first.append(row)
        else:
            rest.append(row)
    return first + rest


def validate_batch(value, pool, category):
    index = {b['id']: b for b in pool}
    rows = value.get('drafts', [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= min(5, len(pool)):
        return ['drafts must contain one to min(5, supplied candidates) recoverable entries; normally five']
    seen, errors = set(), []
    for row in rows:
        if not isinstance(row, dict):
            errors.append('Each draft must be an object')
            continue
        sid = row.get('id')
        if sid not in index or sid in seen:
            errors.append('Unknown or duplicate draft ID')
            continue
        seen.add(sid)
        if not isinstance(row.get('reason'), str) or not row['reason'].strip():
            errors.append(f'{sid}: selection reason required')
        # The batch envelope identifies articles; individual malformed fields or
        # length errors NEVER trigger regeneration of the other four drafts.
    if category == 'News' and rows:
        highest = max(b['importance'] for b in pool)
        included_highest = any(isinstance(r, dict) and r.get('id') in index and index[r['id']]['importance'] == highest for r in rows)
        if included_highest and isinstance(rows[0], dict) and rows[0].get('id') in index and index[rows[0]['id']]['importance'] != highest:
            errors.append('News first draft must be a highest-importance eligible candidate')
    skipped = value.get('skipped', [])
    if not isinstance(skipped, list):
        errors.append('skipped must be a list')
    else:
        for row in skipped:
            if (not isinstance(row, dict) or row.get('id') not in index or row.get('id') in seen
                    or not isinstance(row.get('reason'), str) or not row['reason'].strip()):
                errors.append('skipped needs a unique supplied ID, reason, and no overlap with drafts')
            else:
                seen.add(row['id'])
    return errors


def validate_order(value, pool, category):
    ids = {b['id'] for b in pool}
    order = value.get('order', [])
    if not isinstance(order, list) or len(order) != len(ids) or set(order) != ids:
        return ['order must contain every supplied draft ID exactly once: three winners then reserves']
    if category == 'News' and pool:
        index = {b['id']: b for b in pool}
        if index[order[0]]['importance'] != max(b['importance'] for b in pool):
            return ['News first winner must be a highest-importance eligible draft']
    return []


class BatchEditor(AutonomousEditor):
    def accepted_context(self, cat):
        """Bounded ready-article context for new-source planning/selection only."""
        from .agent_shadow import read
        path = self.root / 'editor-state.json'
        rows = read(path).get(cat, {}).get('accepted', []) if path.exists() else []
        return [{'id': a['candidate']['id'],
                 'title': a['entry'].get('middle_en', {}).get('headline') or a['candidate']['article']['title'],
                 'topic': a['candidate']['topic'],
                 'publisher': a['candidate']['article'].get('_publisher_key') or a['candidate'].get('publisher', ''),
                 'source_excerpt': a['candidate']['article']['body'][:1200]}
                for a in rows]

    def originals(self, cat):
        return super().pool(cat, len(self.catalog[cat]), limit=8)

    def check_batch(self, value, originals, cat):
        return validate_batch(value, originals, cat)

    def plan(self):
        from .agent_shadow import read, write, RANK_RULES, validate_catalog
        if self.path.exists():
            data = read(self.path)
            self.catalog = data['catalog']
            self.snapshot.update({k: data[k] for k in ('candidates', 'sources')})
        else:
            from .news_topics import TOPICS_BY_CATEGORY
            ids = {b['id'] for b in self.snapshot['candidates']}
            rules = RANK_RULES + '\nBATCH MODE: retain the full eligible reserve catalog up to 30/section. '
            rules += ('Order first eight for quality, varied topics and publishers. News highest importance first, '
                      'before source/topic diversity. Science physics/chemistry/astronomy/biology remain distinct. '
                      'Use canonical topic labels supplied in material. Never invent a source. No browsing.')
            rules += sports_preference(self.snapshot)
            from .agent_shadow_profiles import is_source_first
            if is_source_first(self.snapshot):
                from .editorial_policy import SECTION_POLICY
                rules += '\n' + SECTION_POLICY + '\nSOURCE-FIRST: metadata includes independently fetched body length, photo bytes and final-category fits. Rank only suitable final categories. No new fetching or browsing. Initial risk alone must not exclude calm politics/war/death.'
            def check_plan(value):
                errors = validate_catalog(value, ids)
                if not errors:
                    errors += ['Use canonical topic labels and at most 30 candidates per section'
                               for cat, rows in value['catalog'].items()
                               if len(rows) > 30 or any(b['topic'] not in TOPICS_BY_CATEGORY[cat] for b in rows)]
                return errors
            self.catalog = self.ask(self.root, 'plan', rules,
                {**{k: self.snapshot[k] for k in ('date', 'candidates', 'history')},
                 'topic_labels': {cat: list(labels) for cat, labels in TOPICS_BY_CATEGORY.items()}},
                check_plan)['catalog']
            # Importance is a mechanical first-slot invariant, not only a prompt.
            self.catalog['News'].sort(key=lambda b: -b['importance'])
            self.save()
        self.boundary(self.root, 'plan', self.stepwise)
        return self.catalog

    def pool(self, cat, target):
        from .agent_shadow import read, write, AnswerRejected, pin_task_answers
        path = self.root / f'batch-{cat}-{target}.json'
        if path.exists():
            return read(path)['pool']
        prior = [read(p) for p in sorted(self.root.glob(f'batch-{cat}-*.json'))]
        consumed = {sid for batch in prior for sid in batch['considered']}
        original_catalog = self.catalog[cat]
        # Previous valid-but-unselected originals remain available; only generated drafts
        # and structurally invalid drafts are consumed. No duplicate rewriting of them.
        self.catalog[cat] = [b for b in original_catalog if b['id'] not in consumed]
        if cat == 'Science':
            self.catalog[cat] = publisher_first_catalog(
                self.catalog[cat], self.snapshot['candidates'], self.snapshot['sources'])
        try:
            originals = self.originals(cat)
        finally:
            self.catalog[cat] = original_catalog
            self.save()
        photo_path = self.root / 'candidate-images.json'
        photos = read(photo_path) if photo_path.exists() else {}
        for b in originals:
            sid, art = b['id'], b['article']
            if sid not in photos:
                dest = self.root / 'candidate-images' / f'{sid}.webp'
                dest.parent.mkdir(exist_ok=True)
                import time
                started = time.monotonic()
                try:
                    info, image_url = None, ''
                    for url in dict.fromkeys([art.get('og_image')] + art.get('image_candidates', [])):
                        if url:
                            info = safe_image(url, dest)
                            if info:
                                image_url = url
                                break
                    photos[sid] = {'ok': bool(info), 'path': str(dest) if info else '', 'source_url': image_url,
                                   'width': info.get('width') if isinstance(info, dict) else None,
                                   'height': info.get('height') if isinstance(info, dict) else None,
                                   'sha256': hashlib.sha256(dest.read_bytes()).hexdigest() if info else ''}
                except Exception as exc:
                    photos[sid] = {'ok': False, 'path': '', 'reason': type(exc).__name__}
                photos[sid]['seconds'] = round(time.monotonic()-started, 3)
                write(photo_path, photos)
        self.boundary(self.root, f'originals-images-{cat}-{target}', self.stepwise)
        if not originals:
            write(path, {'pool': [], 'drafts': [], 'considered': []})
            return []
        from .news_rss_core import TRI_VARIANT_REWRITER_PROMPT
        from .agent_shadow_lengths import rewrite_band
        key = f'rewrite-batch-{cat}-{target}'
        material = {'date': self.snapshot['date'], 'category': cat, 'candidates': [
            {**b, 'image_ok': photos[b['id']]['ok'], 'publisher': b['article'].get('_publisher_key') or publisher_key(
                NewsSource(**self.snapshot['sources'][b['article']['source']])),
             'body_word_bands': {level: rewrite_band(level, cat, b['article']['word_count'])
                                 for level in ('easy', 'middle')}} for b in originals]}
        prompt = TRI_VARIANT_REWRITER_PROMPT + '''
BATCH OVERRIDE: select the best min(5, candidate count) articles AND write all selected drafts in ONE answer.
Return {"drafts":[{"id":"supplied ID","reason":"why chosen","article":{...}}]}.
Each article uses source_id 0, easy_en/middle_en headline/body/card_summary, zh headline/summary.
The per-candidate body_word_bands override generic length rules. Do not generate details or quizzes.
News: if a highest-importance candidate is included, put it first. Unsuitable sources may be
skipped with skipped:[{id,reason}]; do not invent facts to satisfy importance.
Prefer varied topics and independent publishers without displacing important News or inventing facts.
Only supplied original texts support facts/quotes/attribution. Do not add unsupported viewpoints.
'''
        prompt += sports_preference(self.snapshot, cat)
        from .agent_shadow_profiles import is_source_first
        if is_source_first(self.snapshot):
            prompt += '\nSOURCE-FIRST OVERRIDE: Include a highest-importance eligible News FIRST, or explicitly skipped:[{id,reason}] for every tied highest unsuitable candidate. Never silently omit it. Source/topic diversity is secondary.'
        try:
            result = self.ask(self.root, key, prompt, material,
                              lambda v: self.check_batch(v, originals, cat))
        except AnswerRejected as exc:
            pin_task_answers(self.root, key)
            write(path, {'pool': [], 'drafts': [], 'considered': [b['id'] for b in originals],
                         'reason': str(exc)})
            self.boundary(self.root, f'batch-invalid-{cat}-{target}', self.stepwise)
            return []
        index = {b['id']: b for b in originals}
        audit = read(self.root / 'provider-audit.json') if (self.root / 'provider-audit.json').exists() else {}
        native = any(token.startswith(key + ':') and r.get('fallback') == 'native'
                     for token, r in audit.get('requests', {}).items())
        for row in result['drafts']:
            index[row['id']]['writer_provider'] = 'native' if native else 'deepseek'
        pool = [index[row['id']] for row in result['drafts']]
        choice_material = {'category': cat, 'drafts': result['drafts'], 'sources': [
                {k: b[k] for k in ('id', 'topic', 'importance')} | {
                    'title': b['article']['title'], 'source': b['article']['source'],
                    'url': b['article']['link']} for b in pool]}
        if is_source_first(self.snapshot):
            choice_material['accepted'] = self.accepted_context(cat)
            for row, b in zip(choice_material['sources'], pool):
                row['publisher'] = b['article'].get('_publisher_key') or publisher_key(
                    NewsSource(**self.snapshot['sources'][b['article']['source']]))
        choice = self.ask(self.root, f'select-batch-{cat}-{target}',
            'Read five drafts and source metadata. Rank best three then every reserve. '
            'Return {"order":["id",...]}, every ID once. News highest importance first; '
            'Science prefer physics/chemistry/astronomy/biology diversity and two independent publishers; '
            'Fun prioritize actual fun, swimming/tennis/other sports distinct. Prefer quality over quotas. '
            'Selection only: modifier will correct selected bodies next. No browsing, writing details or publishing.'
            + sports_preference(self.snapshot, cat),
            choice_material,
            lambda v: validate_order(v, pool, cat))
        pool = [index[sid] for sid in choice['order']]
        write(path, {'pool': pool, 'drafts': result['drafts'],
                     'considered': [row['id'] for row in result['drafts']] + [row['id'] for row in result.get('skipped', [])],
                     'skipped': result.get('skipped', []),
                     'eight_ids': [b['id'] for b in originals], 'order': choice['order']})
        self.boundary(self.root, f'batch-select-{cat}-{target}', self.stepwise)
        return pool

    def dispatch(self, root, key, system, material, validate, **kwargs):
        from .agent_shadow import read
        if key.startswith('rewrite-') and not key.startswith('rewrite-batch-'):
            _, cat, sid = key.split('-', 2)
            for path in self.root.glob(f'batch-{cat}-*.json'):
                for row in read(path)['drafts']:
                    if row['id'] == sid:
                        result = {'articles': [deepcopy(row.get('article'))]}
                        try:
                            errors = validate(result)
                        except (TypeError, AttributeError, KeyError):
                            errors = ['Malformed individual article']
                        if any('w outside ' not in error for error in errors):
                            result = self.ask(root, f'review-repair-draft-{cat}-{sid}',
                                system + '\nREPAIR OVERRIDE: Repair ONLY this one draft using its original source. Do not touch other drafts. '
                                'Return {"articles":[one corrected article with source_id 0, easy_en, middle_en, zh]}. '
                                'Restore required fields, valid structure and requested body lengths; never invent facts.',
                                {'article': row.get('article'), 'errors': errors, 'original': material}, validate)
                        return result
            raise ValueError('Selected draft is missing from frozen batch')
        return self.ask(root, key, system, material, validate, **kwargs)

    def extend(self, cat, target, section):
        from .agent_shadow import read
        from .agent_shadow_lengths import original_band
        consumed = {sid for p in self.root.glob(f'batch-{cat}-*.json') for sid in read(p)['considered']}
        cache = read(self.root / 'bodies.json') if (self.root / 'bodies.json').exists() else {}
        lo, hi = original_band(cat)
        def available(b):
            if (b['id'] in consumed or b['history_status'] != 'clear' or b['history_confidence'] < .7
                    or b['initial_risk'] >= 4 or b['id'] in self.audit.get('url_exclusions', {})):
                return False
            art = cache.get(b['id'])
            return not art or (not art.get('skip_reason') and lo <= art['word_count'] <= hi)
        remaining = [b for b in self.catalog[cat] if available(b)]
        if any(b['id'] in cache for b in remaining):
            return target + 8
        if self.audit['budget_exhausted'] or self.audit.get('exhausted_categories', {}).get(cat):
            return None
        if remaining:
            return target + 8
        # Existing discovery guardrails and finite search budget are retained.
        return super().extend(cat, max(target, len(self.catalog[cat])), section)
