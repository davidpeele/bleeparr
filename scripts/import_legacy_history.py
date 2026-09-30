"""Import an operator-reviewed handoff audit; does not enqueue or edit media.

Run in the app container with DATA_DIR and MEDIA_ROOTS configured:
  python scripts/import_legacy_history.py /data/cleanvid-handoff-audit.json

Audit success entries must have a dated CLI success, unchanged file metadata,
and passed basic probe checks. They are inherited history, not a new full decode.
"""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store, output


def import_history(report, accept_tagged=False):
    if store.settings()['auto_process']:
        raise ValueError('Pause automatic processing before importing history')
    if any(j['status'] in ('running','queued','retry') for j in store.jobs()):
        raise ValueError('Finish or pause pending jobs before importing history')
    roots=[Path(p).resolve() for p in os.getenv('MEDIA_ROOTS','/media').split(os.pathsep) if p]
    imported=recovered=changed=accepted=0
    with store.db() as db:
        for row in report['files']:
            p=Path(row.get('path','')).resolve()
            if not any(p.is_relative_to(root) for root in roots):continue
            if not output.matches(p,row.get('signature')):
                changed+=1;continue
            db.execute('DELETE FROM legacy_completions WHERE path=?',(str(p),))
            db.execute('DELETE FROM legacy_recovery_inputs WHERE path=?',(str(p),))
            approved_tag = accept_tagged and ((row['status']=='no_success_record' and 'edited by bleeparr' in p.name.lower()) or (row['status']=='unprocessed_or_other_cleaner' and 'cleanedwithcleanvid' in p.name.lower()))
            if approved_tag or (row['status']=='legacy_reported_success' and row.get('recorded_success',0)>0):
                db.execute('INSERT OR REPLACE INTO legacy_completions VALUES (?,?,?)',(str(p),json.dumps(row['signature']),row.get('recorded_success',0)))
                imported+=1
                accepted+=int(approved_tag)
            elif row.get('alternate_path') and row['status'] in ('recorded_failure','probe_failed','suspicious_output'):
                alt=Path(row['alternate_path']).resolve()
                if any(alt.is_relative_to(root) for root in roots) and alt.is_file():
                    db.execute('INSERT OR REPLACE INTO legacy_recovery_inputs VALUES (?,?,?)',(str(p),json.dumps(row['signature']),str(alt)))
                    recovered+=1
    store.event(f'CLI handoff history: {imported} inherited completions imported ({accepted} tagged files accepted by operator); {recovered} failed outputs linked to retained originals; {changed} changed/missing files skipped. Media unchanged.')
    return dict(imported=imported,recovered=recovered,changed=changed,accepted=accepted)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit')
    parser.add_argument('--accept-tagged',action='store_true',help='Operator explicitly accepts older CleanVid/Bleeparr-tagged files as inherited completions; failed/suspicious files remain eligible')
    args=parser.parse_args()
    print(json.dumps(import_history(json.loads(Path(args.audit).read_text()),accept_tagged=args.accept_tagged)))
