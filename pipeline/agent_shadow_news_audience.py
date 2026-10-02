"""Shadow News audience selection, not a medical or general safety classifier."""
import re

NEWS_AUDIENCE_RULE = '''
NEWS AUDIENCE OVERRIDE: death toll is NOT importance. Prefer US domestic civic,
school, child/family, public-interest technology and concrete public-service news.
International news needs a clear explainable learning or practical connection for
US children; do not make up that connection. Exclude overseas outbreak/casualty
updates whose main news is deaths, suffering or frightening disease numbers and
which offer no child-relevant development. A vaccine breakthrough or useful
public-health response can qualify; country or illness alone is not a ban.
Suitability and audience value come BEFORE importance; rank the most important
SUITABLE story first, not the biggest death count. Do not turn an excluded event
into a chosen story by adding generic hygiene advice or fictional reassurance.
For school protests, emphasize education/services and verified response, not riots,
injuries, arrest totals or frightening quotations. Serious news is allowed calmly.
'''


def news_exclusion(candidate):
    """Narrow metadata gate for the reported casualty-led outbreak headline.

    This does not decide all relevance from keywords or block medical science.
    Models still assess nuanced relevance using the shared editorial rule.
    """
    title = candidate.get('title', '').lower()
    outbreak = re.search(r'\b(ebola|outbreak|epidemic)\b', title)
    casualties = re.search(r'\b(deaths?|death toll|killed|fatalities)\b', title)
    response = re.search(r'\b(vaccin\w*|treatment\w*|breakthrough|prevention|schools?)\b', title)
    if outbreak and casualties and not response:
        return 'casualty_led_outbreak_not_child_relevant'
    return ''
