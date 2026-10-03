"""Category-specific calendar-day gates for new source-first collections.

Publication metadata is not modification time. Lead-event extraction is
deliberately narrow: an explicit 'On Month D, YYYY' opening, not every historical
date in an article. No claim of semantic event-date understanding is made.
"""
from datetime import date, datetime
from email.utils import parsedate_to_datetime
import json
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

POLICY = 'category-source-date-v2'


def parse_day(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return stamp.astimezone(ZoneInfo('America/New_York')).date() if stamp.tzinfo else stamp.date()


def freshness(value, today, max_days=3):
    stamp = parse_day(value)
    if stamp is None:
        return 'unknown'
    age = (date.fromisoformat(today) - stamp).days
    return 'future' if age < 0 else 'stale' if age > max_days else 'current'


def publication_dates(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    values = [n.get('content', '') for n in soup.select(
        'meta[property="article:published_time"], meta[name="datePublished"], meta[itemprop="datePublished"]')]
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            types = node.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if any(t in ('Article', 'NewsArticle', 'BlogPosting', 'ReportageNewsArticle') for t in types):
                values.append(node.get('datePublished', ''))
            if '@graph' in node:
                walk(node['@graph'])
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(tag.get_text()))
        except (ValueError, TypeError):
            continue
    return list(dict.fromkeys(v for v in values if parse_day(v) is not None))


def url_day(url):
    match = re.search(r'/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$)', urlsplit(url or '').path)
    try:
        return date(*map(int, match.groups())) if match else None
    except ValueError:
        return None


def lead_event_day(body):
    match = re.match(r'\s*On\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b', body or '', re.I)
    if not match:
        return None
    month = match[1].rstrip('.').lower()
    months = ('january','february','march','april','may','june','july','august','september','october','november','december')
    indices = [i+1 for i, name in enumerate(months) if month in (name, name[:3])]
    try:
        return date(int(match[3]), indices[0], int(match[2])) if indices else None
    except ValueError:
        return None


def rejection(candidate, today, article=None):
    category = candidate.get('category', 'News')
    if category == 'Science':
        return None
    max_days = 7 if category == 'Fun' else 3
    dates = [parse_day(candidate.get('published')), url_day(candidate.get('link'))]
    if article is not None:
        dates += [parse_day(v) for v in article.get('source_publication_dates', [])]
        dates += [url_day(article.get('evidence_url'))]
    dates = [d for d in dates if d is not None]
    now = date.fromisoformat(today)
    if any((now-d).days > max_days for d in dates):
        return 'stale_source_date'
    if any(d > now for d in dates):
        return 'future_source_date'
    if article is not None:
        event = lead_event_day(article.get('body', ''))
        if category == 'Fun':
            # An old occurrence is not an expiry. Only explicit end/deadline
            # language with a full date can mechanically establish expiry.
            pattern = r'\b(?:expires?|expired|ends?|ended|closes?|closed|deadline\s+is)\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+20\d{2})\b'
            for match in re.finditer(pattern, article.get('body', ''), re.I):
                expiry = lead_event_day('On ' + match[1])
                if expiry and expiry < now:
                    return 'expired_article'
        elif event and (now-event).days > max_days:
            return 'stale_lead_event'
        if not dates and (category == 'Fun' or not event):
            return 'unknown_source_date'
    return None
