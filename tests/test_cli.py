import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classpass_cli as cp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://classpass.com/studios/example-fitness-studio'
TEXT = (ROOT / 'examples/synthetic-studio.txt').read_text()


class AdapterTests(unittest.TestCase):
    def parse(self, text=TEXT, day='2026-11-11', tz='America/Los_Angeles'):
        return cp.parse_schedule(text, SOURCE, day, tz, "Example Fitness Studio")

    def test_synthetic_studio_fixture(self):
        result = self.parse()
        self.assertEqual(len(result['classes']), 3)
        first = result['classes'][0]
        self.assertEqual(first['starts_at'], '2026-11-11T15:00:00-08:00')
        self.assertEqual(first['ends_at'], '2026-11-11T15:50:00-08:00')
        self.assertIsNone(first['credits'])
        self.assertIsNone(first['bookable'])
        self.assertEqual(result['freshness'], 'unverified_capture')
        again = self.parse()
        result.pop('parsed_at')
        again.pop('parsed_at')
        self.assertEqual(result, again)

    def test_stale_day_wrong_timezone_and_empty_fail_closed(self):
        for kwargs in ({'day': '2026-11-12'}, {'tz': 'Europe/London'},
                       {'text': 'Schedule\nWed, Nov 11\nNo classes'},
                       {'text': 'Just a moment...\n' + TEXT}):
            with self.subTest(kwargs=kwargs), self.assertRaises(cp.InputError):
                self.parse(**kwargs)

    def test_simple_html_excludes_scripts_and_preserves_input_hash(self):
        html = '<html><body><script>SECRET</script>' + ''.join(
            '<div>' + line + '</div>' for line in TEXT.splitlines()) + '</body></html>'
        result = self.parse(text=html)
        self.assertEqual(len(result['classes']), 3)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual(result['input_sha256'], cp.hashlib.sha256(html.encode()).hexdigest())

    def test_ambiguous_dst_time_fails_closed(self):
        text = 'Schedule\nSun, Nov 1\n1:30 AM PDT 50 min\nExample class\nSee pricing\nSee next day'
        with self.assertRaisesRegex(cp.InputError, 'Ambiguous'):
            self.parse(text=text, day='2026-11-01')

    def test_url_allowlist(self):
        for url in ('http://classpass.com/studios/a', 'https://evil.test/studios/a',
                    SOURCE + '?token=secret', 'https://classpass.com@evil.test/studios/a',
                    'https://classpass.com/account', SOURCE + '#secret'):
            with self.subTest(url=url), self.assertRaises(cp.InputError):
                cp.public_url(url)

    def test_403_is_one_attempt(self):
        opener = unittest.mock.Mock()
        opener.open.side_effect = HTTPError(SOURCE, 403, 'secret-cookie', {}, None)
        with patch.object(cp, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(cp.InputError, 'HTTP 403') as exc:
                cp.fetch(SOURCE)
        opener.open.assert_called_once()
        self.assertNotIn('secret-cookie', str(exc.exception))

    def test_redirects_are_not_followed(self):
        self.assertIsNone(cp.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test'))

    def test_har_redacts_query_path_headers_and_bodies(self):
        har = {'log': {'entries': [{'request': {'url':
            'https://classpass.com/api/v1/users/private-email/search?token=SECRET',
            'method': 'GET', 'headers': [{'name': 'Cookie', 'value': 'COOKIESECRET'}],
            'postData': {'text': 'BODYSECRET'}}, 'response': {'status': 200,
            'content': {'mimeType': 'application/json', 'text': 'RESPONSESECRET'}}}]}}
        output = json.dumps(cp.inspect_har(har))
        for secret in ('SECRET', 'private-email', 'users', 'token', 'Cookie'):
            self.assertNotIn(secret, output)
        self.assertIn('/api/v1/:segment/:segment/search', output)

    def test_cli_parse_and_filter(self):
        args = [sys.executable, str(ROOT / 'classpass_cli.py')]
        parsed = subprocess.run(args + ['parse', str(ROOT / 'examples/synthetic-studio.txt'),
            '--source-url', SOURCE, '--date', '2026-11-11', '--timezone',
            'America/Los_Angeles', '--studio', "Example Fitness Studio"], capture_output=True, text=True, check=True)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'schedule.json'
            file.write_text(parsed.stdout)
            filtered = subprocess.run(args + ['filter', str(file), '--after', '16:00',
                '--before', '17:00', '--keyword', 'lift'], capture_output=True, text=True, check=True)
        result = json.loads(filtered.stdout)
        self.assertEqual(len(result['classes']), 1)
        self.assertEqual(result['classes'][0]['starts_at'], '2026-11-11T16:10:00-08:00')


if __name__ == '__main__':
    unittest.main()
