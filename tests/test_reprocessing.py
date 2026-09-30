import json
import os
import time
from unittest.mock import patch

import pytest
from backend import store,service,reprocessing
from test_app import client,job
from test_subtitles import ENGLISH,write_subs


@pytest.fixture
def candidate(client,tmp_path):
    store.save_settings({'sonarr_url':'http://sonarr','sonarr_api_key':'test','output_mode':'replace','swears':'damn'})
    old={**job(),'path':str(tmp_path/'media'/'old.mkv')}
    store.enqueue(old);claimed=store.claim(3)
    store.finish(claimed,{'success':True,'outcome':'muted_words'},store.settings())
    folder=tmp_path/'media';folder.mkdir()
    source=folder/'new.mkv';source.write_bytes(b'fresh original')
    os.utime(source,(time.time()-300,)*2)
    write_subs(source.with_suffix('.srt'),[(10,12)],'damn '+ENGLISH)
    files=[(5,'Example S01E03',{'path':str(source),'mediaInfo':{'audioLanguages':'eng'}}),
           (6,'Example S01E04',{'path':str(folder/'other.mkv')})]
    data={'streams':[{'index':0,'codec_type':'video'},{'index':1,'codec_type':'audio','tags':{'language':'eng'}}]}
    with patch.object(service.Arr,'files',return_value=files),patch.object(reprocessing.cli,'probe',return_value=(data,30)):
        yield client,claimed['id'],source,files


def test_preview_does_not_queue_and_confirm_targets_one_episode_and_backs_up(candidate):
    client,id,source,_=candidate
    preview=client.get(f'/api/jobs/{id}/reprocess-preview').json()
    assert preview['eligible'] and preview['audio_stream']==1
    assert preview['subtitle_language']=='en' and preview['matched_word_count']==1
    assert len(store.jobs())==1
    response=client.post(f'/api/jobs/{id}/reprocess',json={'fingerprint':preview['fingerprint']})
    assert response.status_code==200,response.text
    queued=next(j for j in store.jobs() if j['id']==response.json()['job_id'])
    assert queued['item_id']==5 and queued['path']==str(source) and queued['status']=='queued'
    assert next(j for j in store.jobs() if j['id']==id)['status']=='completed'
    backup=list((store.data_dir()/'audits').glob('reprocess-*.json'))
    assert len(backup)==1 and json.loads(backup[0].read_text())['reviewed_job']['id']==id
    assert client.post(f'/api/jobs/{id}/reprocess',json={'fingerprint':preview['fingerprint']}).status_code==409
    assert len(store.jobs())==2 and source.read_bytes()==b'fresh original'


def test_changed_source_cannot_be_submitted_with_old_preview(candidate):
    client,id,source,_=candidate
    preview=client.get(f'/api/jobs/{id}/reprocess-preview').json()
    source.write_bytes(b'new replacement with different size');os.utime(source,(time.time()-300,)*2)
    response=client.post(f'/api/jobs/{id}/reprocess',json={'fingerprint':preview['fingerprint']})
    assert response.status_code==409 and 'changed' in response.json()['detail']
    assert len(store.jobs())==1


def test_cleaned_copy_requires_fresh_source_without_clearing_completion(candidate):
    client,id,source,files=candidate
    with store.db() as db:
        from backend import output
        db.execute('INSERT INTO processed_outputs VALUES (?,?)',(str(source),json.dumps(output.signature(source))))
    before=store.jobs()
    result=client.get(f'/api/jobs/{id}/reprocess-preview').json()
    assert not result['eligible'] and 'fresh copy' in result['reason']
    assert store.jobs()==before


def test_foreign_source_and_active_job_cannot_be_reprocessed(candidate):
    client,id,source,files=candidate
    files[0][2]['mediaInfo']['audioLanguages']='fre'
    assert not client.get(f'/api/jobs/{id}/reprocess-preview').json()['eligible']
    files[0][2]['mediaInfo']['audioLanguages']='eng'
    preview=reprocessing.preview(id)
    store.enqueue({**job('pending'),'fingerprint':preview['fingerprint'],'path':str(source)})
    assert not reprocessing.preview(id)['eligible']
    assert 'already queued' in reprocessing.preview(id)['reason']


def test_failed_source_job_is_backed_up_before_targeted_retry(candidate):
    client,id,source,_=candidate
    preview=reprocessing.preview(id)
    store.enqueue({**job('failed'),'fingerprint':preview['fingerprint'],'path':str(source)})
    claimed=store.claim(3)
    store.finish(claimed,{'success':False,'error_code':'speech_model'},store.settings())
    result=reprocessing.enqueue(id,preview['fingerprint'])
    assert result['job_id']==claimed['id']
    backups=list((store.data_dir()/'audits').glob('reprocess-*.json'))
    saved=json.loads(backups[0].read_text())['previous_source_job']
    assert saved['status']=='failed' and json.loads(saved['result'])['error_code']=='speech_model'


def test_reused_job_archives_old_delivery_receipt_before_fresh_analysis(candidate):
    client,id,source,_=candidate
    preview=reprocessing.preview(id)
    store.enqueue({**job('previous'),'fingerprint':preview['fingerprint'],'path':str(source)})
    claimed=store.claim(3)
    store.finish(claimed,{'success':True},store.settings())
    previous_directory=store.data_dir()/'jobs'/str(claimed['id'])
    previous_directory.mkdir(parents=True)
    (previous_directory/'delivery.json').write_text('{"old_delivery":true}')
    (previous_directory/'worker.log').write_text('previous model analysis')
    result=reprocessing.enqueue(id,preview['fingerprint'])
    assert result['job_id']==claimed['id']
    assert not previous_directory.exists()
    backup=next((store.data_dir()/'audits').glob('reprocess-*.json'))
    from pathlib import Path
    archive=Path(json.loads(backup.read_text())['previous_artifacts'])
    assert json.loads((archive/'delivery.json').read_text())=={'old_delivery':True}
    assert (archive/'worker.log').read_text()=='previous model analysis'
    assert next(j for j in store.jobs() if j['id']==claimed['id'])['status']=='queued'


def test_subtitle_review_failure_blocks_reprocessing(candidate):
    client,id,source,_=candidate
    source.with_suffix('.srt').write_text('1\n00:00:10,000 --> 00:00:12,000\nHello\n')
    assert client.get(f'/api/jobs/{id}/reprocess-preview').status_code==409
    assert len(store.jobs())==1
