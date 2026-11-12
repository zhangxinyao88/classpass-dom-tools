import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAP={'schema_version':1,'source_url':'https://classpass.com/profile/past','captured_at':'2026-11-12T04:00:00Z','displayed_total':2,'rows':[{'kind':'order','name':'Example Bowl','studio':'Example Cafe','date_text':'Jan 1, 1:00 PM','credits_text':'4 credits','rating_text':None,'instructor':None}]}
class IngestTests(unittest.TestCase):
 def run_it(self,data,path):return subprocess.run([sys.executable,str(ROOT/'ingest_capture.py'),'history','--output',str(path)],input=json.dumps(data),text=True,capture_output=True)
 def test_private_normalized_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result.json';r=self.run_it(CAP,p)
   self.assertEqual(r.returncode,0);self.assertEqual(p.stat().st_mode&0o777,0o600)
   self.assertEqual(json.loads(p.read_text())['captured_count'],1)
   self.assertNotIn('Example',r.stdout)
 def test_invalid_capture_does_not_replace(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'result.json';p.write_text('existing');r=self.run_it({'secret':'PRIVATE'},p)
   self.assertEqual(r.returncode,2);self.assertEqual(p.read_text(),'existing');self.assertNotIn('PRIVATE',r.stderr)
 def test_refuses_shared_output_directory(self):
  with tempfile.TemporaryDirectory() as d:
   os.chmod(d,0o755);p=Path(d)/'result.json';r=self.run_it(CAP,p)
   self.assertEqual(r.returncode,2);self.assertFalse(p.exists())
 def test_missing_search_options(self):
  r=subprocess.run([sys.executable,str(ROOT/'ingest_capture.py'),'search','--output','unused.json'],input='{}',text=True,capture_output=True)
  self.assertEqual(r.returncode,2)
