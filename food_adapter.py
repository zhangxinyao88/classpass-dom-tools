"""Read-only normalization of one food item's rendered schedule. No requests."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def _source(value):
    if not isinstance(value, str):
        raise ValueError('Missing food venue URL.')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname != 'classpass.com'
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.query or parsed.fragment
            or not re.fullmatch(r'/studios/[a-zA-Z0-9/_-]+', parsed.path)):
        raise ValueError('Unsupported food venue URL.')
    return value


def _text(value, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Missing or unsupported food display field.')
    return re.sub(r'\s+', ' ', value).strip()


def _timestamp(value):
    parsed = datetime.fromisoformat(_text(value).replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('Capture timestamp requires timezone.')
    return parsed


def _identity(source, item, day, start=None):
    # Local identities only; do not collect order IDs, checkout URLs or account IDs.
    text = '\n'.join([source, item, day] + ([start] if start else []))
    return 'food-' + hashlib.sha256(text.encode()).hexdigest()[:24]


def parse_food(data, day=None, tz_name=None, block_minutes=None):
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data['schema_version'] != 1 or data.get('capture_type') != 'food_item_schedule'):
        raise ValueError('Unsupported food capture.')
    source = _source(data.get('source_url'))
    captured = _timestamp(data.get('captured_at'))
    venue = _text(data.get('venue'))
    availability = data.get('availability')
    if availability not in ('web_schedule', 'app_only'):
        raise ValueError('Unknown food ordering surface.')
    rows = data.get('rows')
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('Unsupported food row count.')
    base = {'schema_version': 1, 'scope': 'rendered_food_item_snapshot',
        'source_url': source, 'venue': venue, 'captured_at': captured.isoformat(),
        'parsed_at': datetime.now(timezone.utc).isoformat(),
        'availability': availability, 'complete_results': False,
        'freshness': 'observed_dom_snapshot_not_revalidated', 'opportunities': []}
    if availability == 'app_only':
        if rows or data.get('item_name') is not None or data.get('date_heading') is not None:
            raise ValueError('App-only capture must not claim web slots.')
        return {**base, 'schedule_date': None, 'timezone': None,
            'unavailable_reason': 'ordering_requires_app_not_no_food_inventory'}
    if not rows or not day or not tz_name:
        raise ValueError('Web food schedule requires rows, date and timezone.')
    if type(block_minutes) is not int or not 1 <= block_minutes <= 180:
        raise ValueError('Supply an explicit 1–180 minute planning block.')
    d, tz = date.fromisoformat(day), ZoneInfo(tz_name)
    expected = {f'{d.strftime(a)} {d.day}' for a in ('%a, %b', '%a %b', '%A, %B', '%A %B')}
    if _text(data.get('date_heading')) not in expected:
        raise ValueError('Food schedule date mismatch.')
    item = _text(data.get('item_name'))
    policy = data.get('policy_text')
    if policy is not None:
        policy = _text(policy, 1500)
    noncancel = bool(policy and re.search(r'\b(?:cannot|can not|can\x27t)\s+(?:be\s+)?cancel', policy, re.I))
    no_refund = bool(policy and re.search(r'\bcredits?\s+(?:will\s+)?(?:not|cannot)\s+be\s+(?:returned|refunded)', policy, re.I))
    group = _identity(source, item, day)
    pattern = re.compile(r'(\d{1,2}:\d{2}\s*[AP]M)(?:\s+([A-Z]{2,5}))?(?:\s*[·,]?\s*(\d+)\s*min)?')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid food slot.')
        label = _text(row.get('time_text'))
        match = pattern.fullmatch(label)
        if not match:
            raise ValueError('Unsupported food time label.')
        clock = re.sub(r'\s*([AP]M)$', r' \1', match[1])
        start = datetime.combine(d, datetime.strptime(clock, '%I:%M %p').time(), tz)
        if start.replace(fold=1).utcoffset() != start.utcoffset():
            raise ValueError('Ambiguous or nonexistent food time.')
        if match[2] and start.strftime('%Z') != match[2]:
            raise ValueError('Food timezone abbreviation mismatch.')
        shown_duration = int(match[3]) if match[3] else None
        if shown_duration is not None and not 1 <= shown_duration <= 1440:
            raise ValueError('Invalid displayed duration.')
        if start.isoformat() in seen:
            raise ValueError('Duplicate food time; recapture the item.')
        seen.add(start.isoformat())
        end = (start.astimezone(timezone.utc) + timedelta(minutes=block_minutes)).astimezone(tz)
        quote = row.get('credits_text')
        if quote is not None:
            quote = _text(quote)
        price = re.fullmatch(r'(\d+) credits?', quote or '') or re.fullmatch(
            r'(?:Order|Reserve) ' + re.escape(item) + r' for (\d+) credits?', quote or '')
        credits = int(price[1]) if price else None
        if credits is not None and not 1 <= credits <= 1000:
            raise ValueError('Invalid food credit quote.')
        disabled = row.get('action_disabled')
        if disabled is not None and type(disabled) is not bool:
            raise ValueError('Invalid food action state.')
        base['opportunities'].append({'id': _identity(source, item, day, start.isoformat()),
            'kind': 'food', 'name': item, 'venue': venue, 'starts_at': start.isoformat(),
            'ends_at': end.isoformat(), 'credits': credits, 'source_url': source,
            'choice_group': group, 'bookable': False if disabled else None,
            'food_quote_basis': 'displayed_item_slot_quote' if price else None,
            'planning_duration_basis': 'caller_supplied_block_not_pickup_deadline',
            'planning_block_minutes': block_minutes, 'displayed_duration_minutes': shown_duration,
            'pickup_window_ends_at': None, 'noncancelable': True if noncancel else None,
            'no_credit_refund_after_order': True if no_refund else None})
    return {**base, 'schedule_date': day, 'timezone': tz_name, 'timezone_basis': 'caller_supplied',
        'item_name': item, 'selector_basis': 'operator_supplied_dom_mapping',
        'opportunities': sorted(base['opportunities'], key=lambda row: row['starts_at'])}


def planning_food(snapshot):
    """Accept only the narrow normalized adapter envelope, never arbitrary extra fields."""
    if (not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1
            or snapshot.get('scope') != 'rendered_food_item_snapshot'
            or snapshot.get('complete_results') is not False):
        raise ValueError('Expected normalized food item snapshot.')
    source = _source(snapshot.get('source_url'))
    _timestamp(snapshot.get('captured_at'))
    state = snapshot.get('availability')
    rows = snapshot.get('opportunities')
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('Invalid normalized food rows.')
    if state == 'app_only':
        if rows:
            raise ValueError('App-only source cannot supply web slots.')
        return [], {'availability': 'app_only', 'opportunities': 0, 'complete_results': False}
    if state != 'web_schedule' or not rows:
        raise ValueError('No supported web food schedule.')
    day = date.fromisoformat(snapshot['schedule_date'])
    item, venue = _text(snapshot.get('item_name')), _text(snapshot.get('venue'))
    group = _identity(source, item, day.isoformat())
    result = []
    for row in rows:
        start, end = _timestamp(row['starts_at']), _timestamp(row['ends_at'])
        minutes = row.get('planning_block_minutes')
        if (row.get('kind') != 'food' or row.get('name') != item or row.get('venue') != venue
                or row.get('source_url') != source or row.get('choice_group') != group
                or row.get('id') != _identity(source, item, day.isoformat(), start.isoformat())
                or type(minutes) is not int or not 1 <= minutes <= 180
                or start.date() != day or end - start != timedelta(minutes=minutes)
                or row.get('planning_duration_basis') != 'caller_supplied_block_not_pickup_deadline'):
            raise ValueError('Inconsistent normalized food slot.')
        result.append({key: row.get(key) for key in ('id', 'kind', 'name', 'venue',
            'starts_at', 'ends_at', 'credits', 'choice_group', 'bookable', 'food_quote_basis',
            'planning_duration_basis', 'noncancelable', 'no_credit_refund_after_order')})
    return result, {'availability': state, 'opportunities': len(result), 'complete_results': False,
        'planning_duration_basis': 'caller_supplied_block_not_pickup_deadline'}
