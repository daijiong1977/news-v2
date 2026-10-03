"""Deterministic shadow-only candidate gates; no model or production writes."""
import re
import unicodedata
from urllib.parse import urlsplit


def _normal(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def commercial_reason(candidate, body=''):
    """Exclude shopping/advertorials, not public-interest reporting about ads."""
    title = candidate.get('title', '').casefold()
    text = title + '\n' + candidate.get('summary', '').casefold() + '\n' + body.casefold()
    url = (candidate.get('link') or candidate.get('source_url') or '').casefold()
    disclosure = r'\b(?:affiliate links?|sponsored content|advertorial|paid partnership|(?:may|can|will) earn (?:a )?commissions?)\b'
    shopping = r'\b(?:promo codes?|coupon codes?|buying guide|gift guide|shopping guide|deals? of the (?:day|week)|where to buy)\b'
    products = r'\b(?:best|top)\b.{0,90}\b(?:trackers?|toys?|headphones?|laptops?|phones?|earbuds?|vacuums?|smartwatches?|speakers?|mattresses?|cameras?|products?|gadgets?)\b'
    if (re.search(disclosure, text) or re.search(shopping, title)
            or re.search(products, title)
            or re.search(r'/(?:coupons?|promo-codes?|deals|buying-guides?)(?:/|[-?])', url)):
        return 'commercial_or_advertorial'
    return ''


def extraction_reason(url, html, body):
    """Reject TFK only when actual related-card prose entered the extraction."""
    host = (urlsplit(url).hostname or '').lower()
    if host != 'timeforkids.com' and not host.endswith('.timeforkids.com'):
        return ''
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    normalized = ' ' + _normal(body) + ' '
    for paragraph in soup.select('.article-show__related-articles p, .related-articles p, .related-posts p'):
        text = _normal(paragraph.get_text(' ', strip=True))
        if len(text.split()) >= 12 and ' ' + text + ' ' in normalized:
            return 'related_articles_in_extracted_body'
    return ''


def _reported_events(candidate, body):
    """Specific named tournament plus edition, never just a franchise/topic."""
    events = set()
    subject = set(_normal(candidate.get('title', '') + ' ' + candidate.get('summary', '')).split())
    for paragraph in re.split(r'\n+', body or ''):
        text = _normal(paragraph)
        for match in re.finditer(r'\b([a-z][a-z0-9]+) (world championships?|world cup)\b', text):
            qualifier, event = match.groups()
            if qualifier in {'the', 'a', 'this', 'next', 'previous', 'annual', 'at', 'of', 'in'}:
                continue
            # An unrelated sidebar/reference must not redefine the story's subject.
            if qualifier not in subject:
                continue
            years = re.findall(r'\b(?:19|20)\d{2}\b', text[max(0, match.start()-60):match.start()])
            year = years[-1] if years else (re.findall(r'\b(?:19|20)\d{2}\b', candidate.get('published', '')) or [''])[0]
            if year:
                events.add((qualifier, event.rstrip('s'), year))
    return events


def filter_ranked_overlap(rows, candidates, bodies):
    """Keep higher-ranked coverage when model event keys disagree.

    A named tournament edition shared with an anniversary feature is overlap.
    Unrelated franchise events survive. Substantial verbatim overlap is a
    conservative fallback. General semantic/history dedup remains the model's job.
    """
    kept, audit, signatures = [], [], []
    for row in rows:
        sid = row['id']
        article = bodies.get(sid, {})
        body = article.get('body', '')
        events = _reported_events({**article, **candidates.get(sid, {})}, body)
        words = _normal(body).split()
        shingles = {tuple(words[i:i+5]) for i in range(max(0, len(words)-4))}
        duplicate = None
        for other_id, other_events, other_shingles in signatures:
            shared = len(shingles & other_shingles)
            if events & other_events or (shared >= 20 and shared / max(1, min(len(shingles), len(other_shingles))) >= .5):
                duplicate = other_id
                break
        if duplicate is not None:
            audit.append({'id': sid, 'reason': 'same_reported_event_overlap', 'kept_id': duplicate})
        else:
            kept.append(row)
            signatures.append((sid, events, shingles))
    return kept, audit
