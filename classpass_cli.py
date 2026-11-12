#!/usr/bin/env python3
"""Read-only ClassPass DOM snapshot tools. Python 3.10+, standard library only."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from history_adapter import parse_history
from food_adapter import parse_food

MAX_BYTES = 5 * 1024 * 1024


class InputError(ValueError):
    pass


def public_url(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or p.hostname != 'classpass.com' or p.port not in (None, 443)
            or p.username or p.password or p.query or p.fragment
            or not re.fullmatch(r'/(studios|search)/[a-zA-Z0-9/_-]+', p.path)):
        raise InputError('Use a public https://classpass.com/studios/... or /search/... URL without query parameters.')
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    public_url(url)
    # No cookie jar, credentials, retries, redirects or challenge solving.
    try:
        with build_opener(NoRedirect).open(Request(url, headers={
                'User-Agent': 'classpass-readonly-prototype/0.1',
                'Accept': 'text/html'}), timeout=30) as response:
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise InputError('Expected public HTML; response was not HTML.')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise InputError('Page exceeds 5 MiB limit.')
            return raw.decode('utf-8')
    except HTTPError as exc:
        raise InputError(f'HTTP {exc.code}; stopped without retrying. No access challenge was bypassed.') from None
    except (URLError, TimeoutError, UnicodeError):
        raise InputError('Network or decoding failure; no page was parsed.') from None


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'br', 'section'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_schedule(raw, source, day, tz_name, studio):
    public_url(source)
    input_hash = hashlib.sha256(raw.encode()).hexdigest()
    if not urlsplit(source).path.startswith('/studios/'):
        raise InputError('Schedule parsing currently supports studio pages only.')
    d = date.fromisoformat(day)
    tz = ZoneInfo(tz_name)
    if '<html' in raw.lower() or '<body' in raw.lower():
        parser = PageText()
        parser.feed(raw)
        raw = ''.join(parser.parts)
    if any(s in raw.lower() for s in ('just a moment...', 'enable javascript and cookies', 'cf-chl-')):
        raise InputError('Access challenge detected; no schedule was parsed.')
    lines = [re.sub(r'^#{1,6}\s+', '', s.strip()) for s in raw.splitlines() if s.strip()]
    try:
        start = lines.index('Schedule') + 1
    except ValueError:
        raise InputError('No Schedule section. Supply visible studio page text; this is not an API response parser.') from None
    heading = lines[start] if start < len(lines) else ''
    # Explicit year prevents silently treating a cached schedule as today.
    expected = f'{d.strftime("%a, %b")} {d.day}'
    if heading != expected:
        raise InputError(f'Schedule date mismatch: expected {expected}; recapture the requested day.')
    pattern = re.compile(r'^(\d{1,2}:\d{2} [AP]M) ([A-Z]{2,5}) (\d+) min$')
    records = []
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line == 'See next day' or line.endswith(' Reviews'):
            break
        m = pattern.fullmatch(line)
        if not m:
            continue
        if i + 1 >= len(lines) or lines[i + 1] in ('See pricing', 'Schedule'):
            raise InputError('Incomplete class row; recapture page text.')
        clock, abbreviation, duration = m.groups()
        local = datetime.combine(d, datetime.strptime(clock, '%I:%M %p').time(), tz)
        if local.strftime('%Z') != abbreviation:
            raise InputError('Timezone abbreviation does not match supplied IANA timezone and date.')
        # Reject ambiguous/nonexistent local times; the source has no UTC offset.
        if local.replace(fold=1).utcoffset() != local.utcoffset():
            raise InputError('Ambiguous or nonexistent local time; an API timestamp is required.')
        end = (local.astimezone(timezone.utc) + timedelta(minutes=int(duration))).astimezone(tz)
        instructor = None
        if i + 2 < len(lines) and lines[i + 2] not in ('See pricing', 'See next day') and not pattern.fullmatch(lines[i + 2]):
            instructor = lines[i + 2]
        records.append({'studio': studio, 'name': lines[i + 1], 'instructor': instructor,
                        'starts_at': local.isoformat(), 'ends_at': end.isoformat(),
                        'duration_minutes': int(duration), 'credits': None,
                        'bookable': None, 'source_url': source})
    if not records:
        raise InputError('No supported class rows; empty results are not proof of no availability.')
    return {'schema_version': 1, 'scope': 'public_studio_schedule',
            'captured_at': None, 'parsed_at': datetime.now(timezone.utc).isoformat(),
            'input_sha256': input_hash,
            'timezone': tz_name, 'schedule_date': day,
            'freshness': 'unverified_capture', 'classes': sorted(records, key=lambda r: (r['starts_at'], r['name']))}


def parse_search(data, day, tz_name):
    """Normalize only the documented, rendered search-card capture format."""
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise InputError('Unsupported search capture schema.')
    source = public_url(data['source_url'])
    if not urlsplit(source).path.startswith('/search/'):
        raise InputError('Search capture requires a search page URL.')
    d, tz = date.fromisoformat(day), ZoneInfo(tz_name)
    expected = f'Live sessions for {d.strftime("%a, %b")} {d.day}'
    if data.get('heading') != expected:
        raise InputError('Search date mismatch; recapture the requested day.')
    if not isinstance(data.get('captured_at'), str):
        raise InputError('Capture timestamp requires an ISO 8601 string.')
    captured = datetime.fromisoformat(data['captured_at'].replace('Z', '+00:00'))
    if captured.utcoffset() is None:
        raise InputError('Capture timestamp requires a timezone.')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise InputError('No supported search rows or too many rows; availability is unknown.')
    records, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise InputError('Invalid search row.')
        for key in ('name', 'studio', 'time_text', 'class_path', 'studio_path'):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise InputError('Incomplete search row; recapture the page.')
        for key, prefix in (('class_path', 'classes'), ('studio_path', 'studios')):
            if not re.fullmatch(r'/' + prefix + r'/[a-zA-Z0-9/_-]+', row[key]):
                raise InputError('Unsupported class or studio path.')
        if row['class_path'] in seen:
            raise InputError('Duplicate class row; recapture the page.')
        seen.add(row['class_path'])
        m = re.fullmatch(r'(\d{1,2}:\d{2} [AP]M)\s*(\d+) min', row['time_text'])
        if not m:
            raise InputError('Unsupported search time format.')
        duration = int(m[2])
        if not 0 < duration <= 1440:
            raise InputError('Unsupported class duration.')
        local = datetime.combine(d, datetime.strptime(m[1], '%I:%M %p').time(), tz)
        if local.replace(fold=1).utcoffset() != local.utcoffset():
            raise InputError('Ambiguous or nonexistent local time; an API timestamp is required.')
        end = (local.astimezone(timezone.utc) + timedelta(minutes=duration)).astimezone(tz)
        action = row.get('displayed_action')
        if action is not None and not isinstance(action, str):
            raise InputError('Invalid displayed action field.')
        credit_match = re.fullmatch(r'Reserve ' + re.escape(row['name']) + r' for (\d+) credits?', action or '')
        instructor = row.get('instructor')
        if instructor is not None and not isinstance(instructor, str):
            raise InputError('Invalid instructor field.')
        records.append({'studio': row['studio'], 'name': row['name'],
            'instructor': instructor, 'starts_at': local.isoformat(), 'ends_at': end.isoformat(),
            'duration_minutes': duration, 'credits': int(credit_match[1]) if credit_match else None,
            'credits_basis': 'displayed_reserve_label' if credit_match else None,
            'bookable': None, 'source_url': 'https://classpass.com' + row['class_path'],
            'studio_url': 'https://classpass.com' + row['studio_path']})
    return {'schema_version': 1, 'scope': 'rendered_search_snapshot',
        'source_url': source, 'captured_at': captured.isoformat(),
        'parsed_at': datetime.now(timezone.utc).isoformat(),
        'input_sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
        'schedule_date': day, 'timezone': tz_name, 'timezone_basis': 'caller_supplied',
        'freshness': 'observed_dom_snapshot_not_revalidated', 'complete_results': False,
        'classes': sorted(records, key=lambda r: (r['starts_at'], r['name'], r['source_url']))}


def inspect_har(data):
    """Report route shapes only. Never emit credentials, bodies or parameter values."""
    routes = {}
    safe_parts = {'api', 'v1', 'v2', 'v3', 'graphql', 'search', 'studios',
                  'venues', 'schedules', 'classes', 'sessions', 'availability'}
    for entry in data.get('log', {}).get('entries', []):
        req, resp = entry.get('request', {}), entry.get('response', {})
        p = urlsplit(req.get('url', ''))
        if p.hostname != 'classpass.com' and not (p.hostname or '').endswith('.classpass.com'):
            continue
        # JSON POSTs may be GraphQL queries OR mutations: summarize only, never replay.
        if 'json' not in resp.get('content', {}).get('mimeType', '').lower():
            continue
        shape = '/'.join(s if s in safe_parts else ':segment' for s in p.path.split('/') if s)
        method = req.get('method', 'UNKNOWN')
        if method not in ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'):
            method = 'UNKNOWN'
        status = resp.get('status')
        if type(status) is not int or not 0 <= status <= 599:
            status = None
        key = (method, '/' + shape, status)
        routes[key] = routes.get(key, 0) + 1
    return {'scope': 'offline_redacted_har_inventory', 'routes': [
        {'method': k[0], 'path_shape': k[1], 'status': k[2], 'count': v,
         'authentication': 'not_determined', 'read_only': 'not_determined'}
        for k, v in sorted(routes.items(), key=lambda item: str(item[0]))]}


def read_text(path):
    if Path(path).stat().st_size > MAX_BYTES:
        raise InputError('Input exceeds 5 MiB limit.')
    return Path(path).read_text(encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('fetch', help='GET a public page once; stop on access restrictions')
    f.add_argument('url')
    s = sub.add_parser('parse', help='Normalize captured public studio text/HTML into JSON')
    s.add_argument('file')
    s.add_argument('--source-url', required=True)
    s.add_argument('--date', required=True, help='YYYY-MM-DD matching the captured schedule')
    s.add_argument('--timezone', required=True, help='IANA timezone, e.g. America/Los_Angeles')
    s.add_argument('--studio', required=True)
    ds = sub.add_parser('parse-search', help='Normalize captured rendered search cards; no network')
    ds.add_argument('file')
    ds.add_argument('--date', required=True)
    ds.add_argument('--timezone', required=True)
    hs = sub.add_parser('parse-history', help='Normalize captured past cards; preserve unknown years and completeness')
    hs.add_argument('file')
    fs = sub.add_parser('parse-food', help='Normalize one rendered food item schedule or app-only notice')
    fs.add_argument('file')
    fs.add_argument('--date', help='Caller-verified YYYY-MM-DD for a web schedule')
    fs.add_argument('--timezone', help='Caller-verified IANA timezone')
    fs.add_argument('--block-minutes', type=int, help='Explicit planning occupancy, not a pickup deadline')
    h = sub.add_parser('inspect-har', help='Offline route inventory, with all values and bodies omitted')
    h.add_argument('file')
    q = sub.add_parser('filter', help='Filter parsed JSON locally; no network')
    q.add_argument('file')
    q.add_argument('--keyword', default='')
    q.add_argument('--after', help='Local HH:MM, inclusive')
    q.add_argument('--before', help='Local HH:MM, exclusive')
    a = p.parse_args()
    try:
        if a.command == 'fetch':
            print(fetch(a.url))
            return 0
        if a.command == 'parse':
            result = parse_schedule(read_text(a.file), a.source_url, a.date, a.timezone, a.studio)
        elif a.command == 'parse-search':
            result = parse_search(json.loads(read_text(a.file)), a.date, a.timezone)
        elif a.command == 'parse-history':
            result = parse_history(json.loads(read_text(a.file)))
        elif a.command == 'parse-food':
            result = parse_food(json.loads(read_text(a.file)), a.date, a.timezone, a.block_minutes)
        elif a.command == 'inspect-har':
            result = inspect_har(json.loads(read_text(a.file)))
        else:
            result = json.loads(read_text(a.file))
            after = datetime.strptime(a.after, '%H:%M').time() if a.after else None
            before = datetime.strptime(a.before, '%H:%M').time() if a.before else None
            result['classes'] = [r for r in result['classes']
                if a.keyword.casefold() in (r['studio'] + ' ' + r['name']).casefold()
                and (after is None or datetime.fromisoformat(r['starts_at']).time() >= after)
                and (before is None or datetime.fromisoformat(r['starts_at']).time() < before)]
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        return 0
    except (InputError, ValueError, KeyError, TypeError, IndexError, OSError, ZoneInfoNotFoundError) as exc:
        # Never echo untrusted input/error contents: HARs may contain credentials.
        message = str(exc) if isinstance(exc, InputError) else 'Invalid input, missing file, or unsupported data shape.'
        print(json.dumps({'error': message}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
