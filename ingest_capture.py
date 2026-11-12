#!/usr/bin/env python3
"""Receive one supported DOM capture via stdin, normalize and save privately."""
import argparse,json,os,sys,tempfile
from pathlib import Path
from classpass_cli import parse_search
from history_adapter import parse_history

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('kind',choices=['history','search']);p.add_argument('--output',required=True)
 p.add_argument('--date');p.add_argument('--timezone');a=p.parse_args()
 try:
  raw=sys.stdin.buffer.read(5*1024*1024+1)
  if len(raw)>5*1024*1024: raise ValueError()
  data=json.loads(raw)
  if a.kind=='search' and not (a.date and a.timezone):raise ValueError()
  normalized=parse_history(data) if a.kind=='history' else parse_search(data,a.date,a.timezone)
  path=Path(a.output);parent=path.parent
  parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  if parent.stat().st_mode & 0o077:raise ValueError()
  fd,tmp=tempfile.mkstemp(prefix='.capture-',dir=parent)
  try:
   with os.fdopen(fd,'w') as f:json.dump(normalized,f,ensure_ascii=False);f.write('\n')
   os.replace(tmp,path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  summary={'kind':a.kind,'count':len(normalized.get('items',normalized.get('classes',[]))), 'saved':True}
  if a.kind=='history':summary.update(displayed_total=normalized['displayed_total'],complete_history=normalized['complete_history'])
  print(json.dumps(summary));return 0
 except (ValueError,TypeError,KeyError,AttributeError,OSError):
  print(json.dumps({'error':'Capture rejected or private output unavailable.'}),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
