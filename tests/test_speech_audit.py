import json
from backend import store,output
from scripts.audit_speech_completions import audit
from test_app import client,job


def test_audit_distinguishes_errors_from_completed_speech_and_unknown_causes(client,tmp_path):
    scenarios=[('small.en unavailable; retaining full-subtitle fallback: metadata_errors', 'model_failure'),
               ('Finished speech model small.en\nFinished speech model medium.en','speech_completed_with_fallback'),
               ('{"success":true}','fallback_cause_unverified')]
    for i,(log,category) in enumerate(scenarios):
        path=tmp_path/f'{i}.mkv';path.write_bytes(b'cleaned')
        store.enqueue(job(str(i)));claimed=store.claim(3)
        store.finish(claimed,dict(success=True,output_path=str(path),output_signature=output.signature(path),candidate_sections=2,fallback_sections=2),store.settings())
        folder=store.data_dir()/'jobs'/str(claimed['id']);folder.mkdir(parents=True)
        (folder/'worker.log').write_text(log)
    report=audit()
    assert report['completed_jobs']==3 and report['missing_logs']==0
    assert [r['category'] for r in report['findings']]==[x[1] for x in scenarios]
    assert all(r['current_output_matches'] for r in report['findings'])
    (tmp_path/'0.mkv').write_bytes(b'fresh replacement different size')
    assert not audit()['findings'][0]['current_output_matches']
