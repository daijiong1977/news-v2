"""Narrow, text-preserving batch envelope recovery; never finish truncated prose."""
import json


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _drop_unmatched_closers(raw):
    # Work outside quoted strings only. Never insert missing delimiters, commas
    # or text. A row's surplus } immediately before its list delimiter is the
    # observed failure; ambiguous syntax remains a native format-repair task.
    stack, result, actions = [], [], []
    quoted = escaped = False
    previous = ''
    for char in raw:
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in '{[':
            stack.append(char)
        elif char in '}]':
            expected = '{' if char == '}' else '['
            if stack and stack[-1] == expected:
                stack.pop()
            elif char == '}' and previous == '}' and (not stack or stack[-1] == '['):
                actions.append('drop_unmatched_object_closer')
                continue
            else:
                raise ValueError('Ambiguous JSON delimiters')
        result.append(char)
        if not char.isspace():
            previous = char
    if stack or quoted:
        raise ValueError('Incomplete JSON; cannot recover missing content')
    return ''.join(result), actions


def decode_batch(raw):
    actions = []
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except json.JSONDecodeError:
        repaired, actions = _drop_unmatched_closers(raw)
        value = json.loads(repaired, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError('Batch JSON object required')
    for row in value.get('drafts', []):
        if not isinstance(row, dict) or 'zh' not in row:
            continue
        article = row.get('article')
        if not isinstance(article, dict) or 'zh' in article or not isinstance(row['zh'], dict):
            raise ValueError('Ambiguous sibling zh; do not overwrite article text')
        article['zh'] = row.pop('zh')
        actions.append('move_sibling_zh:' + str(row.get('id', '?')))
    return value, actions
