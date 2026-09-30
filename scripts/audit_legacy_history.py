import json,os,subprocess,time,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import service,store,selection,output
ledger=json.loads(Path('/data/legacy-ledger.json').read_text());c=store.settings();records=[]
for kind in ['sonarr','radarr']:
 api=service.Arr(kind,c)
 for title in api.library():
  if not selection.matches(title,c):continue
  if kind=='sonarr':files=api.request('GET','episodefile',params={'seriesId':title['id']})
  else:
   f=title.get('movieFile')
   if f and not f.get('path'):f=api.request('GET','movie/'+str(title['id'])).get('movieFile')
   files=[f] if f else []
  for f in files:
   if f.get('path'):records.append(dict(kind=kind,title_id=title['id'],title=title['title'],remote_path=f['path']))
print('Manager files inventoried:',len(records),flush=True)
def inspect(r):
 try:
  p=service.local_path(r['remote_path'],r['kind'],c);r['path']=str(p)
  if not p.is_file():return {**r,'status':'missing'}
  r['signature']=output.signature(p)
  marker=' (edited by Bleeparr)'
  if marker not in p.stem:return {**r,'status':'unprocessed_or_other_cleaner'}
  base=Path(r['remote_path']);stem=base.stem.replace(marker,'')
  originals=[str(base.with_name(stem+ext)) for ext in ['.mkv','.mp4','.mov']]
  candidates=[(ledger['success'].get(x,0),x) for x in originals]
  success,original=max(candidates)
  failure=max((ledger['failures'].get(x,0) for x in originals),default=0)
  r['recorded_success']=success
  for raw in originals:
   alt=service.local_path(raw,r['kind'],c)
   if alt.is_file():r['alternate_path']=str(alt);break
  if failure>success:return {**r,'status':'recorded_failure'}
  if not success:return {**r,'status':'no_success_record'}
  if p.stat().st_mtime>success+10:return {**r,'status':'changed_since_success'}
  probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],capture_output=True,text=True,timeout=20)
  if probe.returncode or probe.stderr.strip():return {**r,'status':'probe_failed'}
  data=json.loads(probe.stdout);duration=float(data['format'].get('duration',0));types={s.get('codec_type') for s in data.get('streams',[])}
  r['duration']=duration
  if duration<60 or not {'audio','video'}<=types or p.stat().st_size/max(duration,1)<4000:return {**r,'status':'suspicious_output'}
  return {**r,'status':'legacy_reported_success'}
 except Exception as e:return {**r,'status':'audit_error','error':str(e)[:300]}
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(inspect,records))
from collections import Counter
report=dict(created=time.time(),counts=dict(Counter(r['status'] for r in results)),files=results)
Path('/data/cleanvid-handoff-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report['counts']),flush=True)
