"""Offline normalization of rendered history cards. No networking or credentials."""
from datetime import datetime, timezone
import re


def parse_history(data):
    if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('source_url') != 'https://classpass.com/profile/past':
        raise ValueError('Unsupported history capture.')
    stamp = data.get('captured_at')
    if not isinstance(stamp, str):
        raise ValueError('Missing capture timestamp.')
    captured = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if captured.utcoffset() is None:
        raise ValueError('Capture timestamp must include timezone.')
    total = data.get('displayed_total')
    if type(total) is not int or total < 0:
        raise ValueError('Invalid displayed total.')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows or len(rows) > 1000 or len(rows) > total:
        raise ValueError('Invalid history row count.')
    items = []
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in ('reservation', 'order'):
            raise ValueError('Unknown history card variant.')
        for key in ('name', 'studio', 'date_text', 'credits_text'):
            if not isinstance(row.get(key), str) or not row[key].strip() or len(row[key]) > 500:
                raise ValueError('Invalid history field.')
        credit = re.fullmatch(r'(\d+) credits?', row['credits_text'])
        if not credit:
            raise ValueError('Unsupported credits text.')
        # Validate display shape but preserve exact text; never infer year or timezone.
        if not re.fullmatch(r'[A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2} [AP]M', row['date_text']):
            raise ValueError('Unsupported displayed date.')
        datetime.strptime('2000 ' + row['date_text'], '%Y %b %d, %I:%M %p')
        rating_text = row.get('rating_text')
        if rating_text is not None and not isinstance(rating_text, str):
            raise ValueError('Invalid rating.')
        rating = re.fullmatch(r'Rated ([1-5]) stars? out of 5', rating_text or '')
        if rating_text is not None and not rating:
            raise ValueError('Unsupported rating.')
        instructor = row.get('instructor')
        if instructor is not None and (not isinstance(instructor, str) or len(instructor) > 500):
            raise ValueError('Invalid instructor.')
        items.append({'kind':row['kind'], 'name':row['name'], 'studio':row['studio'],
            'date_displayed':row['date_text'], 'year':None, 'timezone':None,
            'credits':int(credit[1]), 'rating':int(rating[1]) if rating else None,
            'instructor':instructor})
    return {'schema_version':1, 'scope':'rendered_history_snapshot', 'source_url':data['source_url'],
        'captured_at':captured.isoformat(), 'parsed_at':datetime.now(timezone.utc).isoformat(),
        'displayed_total':total, 'captured_count':len(items),
        'count_matches_displayed_total':len(items)==total, 'complete_history':False,
        'completeness_note':'Only rendered cards captured; header total is not a completeness guarantee.',
        'items':items}
