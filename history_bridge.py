"""Bridge normalized past cards to planning evidence without inventing visits or dates."""
from datetime import datetime


def planning_history(snapshot):
    if (not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1
            or snapshot.get('scope') != 'rendered_history_snapshot'
            or snapshot.get('source_url') != 'https://classpass.com/profile/past'):
        raise ValueError('Expected normalized past-history output.')
    stamp = snapshot.get('captured_at')
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace('Z', '+00:00')).utcoffset() is None:
        raise ValueError('Invalid history capture timestamp.')
    rows = snapshot.get('items')
    count, total = snapshot.get('captured_count'), snapshot.get('displayed_total')
    if (not isinstance(rows, list) or not 0 < len(rows) <= 1000
            or type(count) is not int or count != len(rows)
            or type(total) is not int or total < count
            or snapshot.get('complete_history') is not False):
        raise ValueError('Invalid or unsupported history coverage.')
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in ('reservation', 'order'):
            raise ValueError('Unsupported history card type.')
        if row.get('year') is not None or row.get('timezone') is not None:
            raise ValueError('This adapter preserves missing year/timezone; unexpected values require review.')
        for field in ('name', 'studio', 'date_displayed'):
            if not isinstance(row.get(field), str) or not row[field].strip() or len(row[field]) > 500:
                raise ValueError('Missing history display field.')
        credits, rating = row.get('credits'), row.get('rating')
        if type(credits) is not int or not 0 <= credits <= 1000:
            raise ValueError('Invalid history displayed price.')
        if rating is not None and (type(rating) is not int or not 1 <= rating <= 5):
            raise ValueError('Invalid history rating.')
        # Card variant does not establish the offering category or attendance.
        result.append({'kind': 'unknown', 'name': row['name'], 'venue': row['studio'],
            'status': 'past_listed', 'rating': rating, 'credits': None,
            'displayed_credits': credits, 'date_displayed': row['date_displayed'],
            'year': None, 'timezone': None, 'card_variant': row['kind'],
            'evidence_source': 'rendered_history_snapshot'})
    coverage = {'scope': 'rendered_history_snapshot', 'captured_at': stamp,
        'captured_count': count, 'displayed_total': total,
        'count_matches_displayed_total': count == total,
        'reservation_card_count': sum(row['kind'] == 'reservation' for row in rows),
        'order_card_count': sum(row['kind'] == 'order' for row in rows),
        'complete_history': False, 'missing_year_count': count,
        'category_unknown_count': count, 'attendance_unverified_count': count}
    return result, coverage
