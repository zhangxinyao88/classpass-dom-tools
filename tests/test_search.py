import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classpass_cli as cp
ROOT = Path(__file__).resolve().parents[1]
CAPTURE = {'schema_version': 1, 'source_url': 'https://classpass.com/search/example-city/yoga-classes/example',
    'captured_at': '2026-11-12T00:00:00Z', 'heading': 'Live sessions for Fri, Nov 13',
    'rows': [{'name':'Example Yin Session', 'studio':'Example Yoga Studio', 'instructor':'Example Teacher',
        'class_path':'/classes/example-studio/yin/123', 'studio_path':'/studios/example-studio',
        'time_text':'4:30 PM60 min', 'displayed_action':'Reserve Example Yin Session for 5 credits'}]}
class SearchTests(unittest.TestCase):
    def test_valid(self):
        r = cp.parse_search(CAPTURE, '2026-11-13', 'America/New_York')
        self.assertEqual(r['classes'][0]['credits'], 5)
        self.assertEqual(r['classes'][0]['starts_at'], '2026-11-13T16:30:00-05:00')
        self.assertIsNone(r['classes'][0]['bookable'])
        self.assertFalse(r['complete_results'])
    def test_unknown_action_no_credit_or_availability_claim(self):
        c=copy.deepcopy(CAPTURE);c['rows'][0]['displayed_action']='Join waitlist'
        r=cp.parse_search(c,'2026-11-13','America/New_York')['classes'][0]
        self.assertIsNone(r['credits']);self.assertIsNone(r['bookable'])
    def test_malformed_capture_timestamp_and_action_fail_closed(self):
        for value in (None, 42, {}, []):
            c = copy.deepcopy(CAPTURE)
            c['captured_at'] = value
            with self.subTest(field='captured_at', value=value), self.assertRaises(cp.InputError):
                cp.parse_search(c, '2026-11-13', 'America/New_York')
            c = copy.deepcopy(CAPTURE)
            c['rows'][0]['displayed_action'] = value
            if value is not None:
                with self.subTest(field='displayed_action', value=value), self.assertRaises(cp.InputError):
                    cp.parse_search(c, '2026-11-13', 'America/New_York')
    def test_fail_closed(self):
        variants=[]
        for key,value in [('heading','Live sessions for Sat, Nov 14'),('rows',[]),
                          ('source_url','https://evil.test/search/x'),('captured_at','2026-11-12T03:00:00')]:
            c=copy.deepcopy(CAPTURE);c[key]=value;variants.append(c)
        for key,value in [('class_path','//evil.test/x'),('time_text','4:30 PM0 min'),
                          ('studio',None),('class_path','/classes/x?token=secret')]:
            c=copy.deepcopy(CAPTURE);c['rows'][0][key]=value;variants.append(c)
        c=copy.deepcopy(CAPTURE);c['rows']*=2;variants.append(c)
        for c in variants:
            with self.subTest(c=c),self.assertRaises(cp.InputError):
                cp.parse_search(c,'2026-11-13','America/New_York')
    def test_dst_fails(self):
        for day,heading,time in [('2026-11-01','Live sessions for Sun, Nov 1','1:30 AM60 min'),
                                 ('2026-03-08','Live sessions for Sun, Mar 8','2:30 AM60 min')]:
            c=copy.deepcopy(CAPTURE);c['heading']=heading;c['rows'][0]['time_text']=time
            with self.assertRaises(cp.InputError):cp.parse_search(c,day,'America/New_York')
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture=Path(tmp)/'capture.json'; capture.write_text(json.dumps(CAPTURE))
            args=[sys.executable,str(ROOT/'classpass_cli.py')]
            p=subprocess.run(args+['parse-search',str(capture),'--date','2026-11-13','--timezone','America/New_York'],text=True,capture_output=True,check=True)
            result=Path(tmp)/'result.json';result.write_text(p.stdout)
            q=subprocess.run(args+['filter',str(result),'--keyword','yin','--after','16:00','--before','17:00'],text=True,capture_output=True,check=True)
            self.assertEqual(len(json.loads(q.stdout)['classes']),1)
if __name__=='__main__':unittest.main()
