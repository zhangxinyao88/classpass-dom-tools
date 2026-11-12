import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from history_adapter import parse_history
ROOT=Path(__file__).resolve().parents[1]
# Entirely synthetic data, no real user history.
ROW={'kind':'reservation','name':'Example Class','studio':'Example Studio','date_text':'Feb 29, 1:00 PM','credits_text':'5 credits','instructor':'Example Instructor','rating_text':'Rated 4 stars out of 5'}
CAP={'schema_version':1,'source_url':'https://classpass.com/profile/past','captured_at':'2026-11-12T04:00:00Z','displayed_total':3,'rows':[ROW,dict(ROW,kind='order',name='Example Bowl',instructor=None,rating_text=None)]}
class HistoryTests(unittest.TestCase):
 def test_variants_and_no_year_inference(self):
  x=parse_history(CAP);self.assertEqual(x['captured_count'],2);self.assertFalse(x['complete_history'])
  self.assertEqual(x['items'][0]['rating'],4);self.assertEqual(x['items'][1]['credits'],5)
  self.assertIsNone(x['items'][1]['rating']);self.assertIsNone(x['items'][0]['year'])
  self.assertEqual(x['items'][0]['date_displayed'],'Feb 29, 1:00 PM')
 def test_count_match_not_completeness(self):
  c=copy.deepcopy(CAP);c['displayed_total']=2;x=parse_history(c)
  self.assertTrue(x['count_matches_displayed_total']);self.assertFalse(x['complete_history'])
 def test_bad_fields(self):
  for key,val in [('kind','unknown'),('rating_text','Rated 8 stars out of 5'),('credits_text','5 dollars'),('date_text','Feb 30, 1:00 PM'),('instructor',{}),('name',None)]:
   c=copy.deepcopy(CAP);c['rows'][0][key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):parse_history(c)
 def test_bad_envelope(self):
  for key,val in [('source_url','https://classpass.com/profile/past?token=SECRET'),('captured_at','2026-11-12'),('rows',[]),('displayed_total',1),('displayed_total',True)]:
   c=copy.deepcopy(CAP);c[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):parse_history(c)
 def test_cli_and_field_allowlist(self):
  c=copy.deepcopy(CAP);c['account_secret']='SECRET';c['rows'][0]['booking_id']='PRIVATE'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'capture.json';p.write_text(json.dumps(c))
   r=subprocess.run([sys.executable,str(ROOT/'classpass_cli.py'),'parse-history',str(p)],capture_output=True,text=True,check=True)
   self.assertNotIn('SECRET',r.stdout);self.assertNotIn('PRIVATE',r.stdout)
   self.assertEqual(len(json.loads(r.stdout)['items']),2)
