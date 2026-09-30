import json
from pathlib import Path
from unittest.mock import patch
import pytest
from backend import store,output,retention,service,reprocessing
from test_app import client,job
from test_subtitles import ENGLISH,write_subs


@pytest.fixture
def original(client,tmp_path,monkeypatch):
    archive=tmp_path/'originals';monkeypatch.setenv('ORIGINALS_DIR',str(archive))
    folder=tmp_path/'media';folder.mkdir()
    source=folder/'Example.mkv';source.write_bytes(b'original unmuted audio')
    store.save_settings({'retain_originals':True,'output_mode':'replace'})
    entry={**job(),'id':1,'path':str(source),'remote_path':str(source)}
    return entry,source,archive


def publish(entry,source,tmp_path):
    plan=output.plan(entry,store.settings());Path(plan['stage']).write_bytes(b'cleaned audio')
    receipt=tmp_path/'receipt.json'
    return output.finish(plan,{'success':True},receipt),json.loads(receipt.read_text())


def test_verified_original_retained_outside_library_and_publication_resumes(original,tmp_path):
    entry,source,archive=original;content=source.read_bytes()
    result,receipt=publish(entry,source,tmp_path)
    assert not source.exists() and Path(result['output_path']).read_bytes()==b'cleaned audio'
    backup=retention.records()[0]
    assert Path(backup['path']).is_relative_to(archive) and Path(backup['path']).read_bytes()==content
    assert retention.recovery_source(result['output_path'])==Path(backup['path'])
    assert output.publish(receipt)==result


def test_retention_off_does_not_create_backup(original,tmp_path):
    entry,source,archive=original;store.save_settings({'retain_originals':False})
    result,_=publish(entry,source,tmp_path)
    assert not source.exists() and not retention.records() and not archive.exists()
    assert 'original_backup_id' not in result


def test_matching_subtitle_retained_and_expires_with_original(original,tmp_path):
    entry,source,archive=original
    subtitle=source.with_suffix('.srt');subtitle.write_text('correct English dialogue')
    plan=output.plan(entry,store.settings());Path(plan['stage']).write_bytes(b'cleaned')
    output.finish(plan,{'success':True,'subtitle_path':str(subtitle)},tmp_path/'receipt.json')
    row=retention.records()[0]
    assert Path(row['subtitle_path']).is_relative_to(archive)
    assert Path(row['subtitle_path']).read_text()=='correct English dialogue'
    retention.cleanup(now=row['expires']+1)
    assert not Path(row['path']).exists() and not Path(row['subtitle_path']).exists()
    assert subtitle.read_text()=='correct English dialogue'


def test_changed_archived_subtitle_preserves_expired_original(original,tmp_path):
    entry,source,_=original;subtitle=source.with_suffix('.srt');subtitle.write_text('dialogue')
    plan=output.plan(entry,store.settings());Path(plan['stage']).write_bytes(b'cleaned')
    output.finish(plan,{'success':True,'subtitle_path':str(subtitle)},tmp_path/'receipt.json')
    row=retention.records()[0];Path(row['subtitle_path']).write_text('changed dialogue')
    retention.cleanup(now=row['expires']+1)
    assert Path(row['path']).exists() and retention.records()[0]['status']=='changed'


def test_ready_archive_not_charged_again_after_interrupted_publication(original,tmp_path,monkeypatch):
    entry,source,_=original;plan=output.plan(entry,store.settings());Path(plan['stage']).write_bytes(b'cleaned')
    receipt={**plan,'result':{'success':True},'cleaned_signature':output.signature(plan['stage'])}
    retention.ensure(receipt)
    monkeypatch.setattr(retention,'capacity',lambda *args:(_ for _ in ()).throw(retention.RetentionFull('full')))
    assert output.plan(entry,store.settings())['original_retention']['id']==plan['original_retention']['id']
    assert output.publish(receipt)['success']


def test_archive_limit_holds_before_publication_without_evicting_unexpired(original,tmp_path,monkeypatch):
    entry,source,archive=original;archive.mkdir();(archive/'unregistered').write_bytes(b'x')
    monkeypatch.setattr(retention,'usage',lambda:100*1024**3)
    with pytest.raises(retention.RetentionFull):output.plan(entry,store.settings())
    assert source.exists() and (archive/'unregistered').read_bytes()==b'x'


def test_expiry_removes_only_unchanged_registered_originals(original,tmp_path):
    entry,source,archive=original;result,_=publish(entry,source,tmp_path)
    record=retention.records()[0];retention.cleanup(now=record['expires']+1)
    assert not Path(record['path']).exists() and Path(result['output_path']).exists()
    assert retention.recovery_source(result['output_path']) is None


def test_expiry_waits_for_active_reprocessing_to_finish(original,tmp_path):
    import time
    entry,source,_=original;result,_=publish(entry,source,tmp_path)
    row=retention.records()[0];store.enqueue({**job('active-backup'),'path':row['path']});claimed=store.claim(3)
    with store.db() as db:db.execute('UPDATE original_backups SET expires=?',(time.time()-1,))
    retention.cleanup();assert Path(row['path']).exists()
    assert retention.recovery_source(result['output_path']) is not None
    store.finish(claimed,{'success':False,'error_code':'speech_model'},store.settings())
    retention.cleanup();assert not Path(row['path']).exists()


def test_expiry_preserves_changed_and_unregistered_backups(original,tmp_path):
    entry,source,archive=original;publish(entry,source,tmp_path)
    record=retention.records()[0];Path(record['path']).write_bytes(b'modified')
    (archive/'unregistered').write_bytes(b'keep')
    retention.cleanup(now=record['expires']+1)
    assert Path(record['path']).read_bytes()==b'modified' and (archive/'unregistered').read_bytes()==b'keep'
    assert retention.records()[0]['status']=='changed'


def test_retained_original_can_replace_cleaned_copy_without_being_deleted(original,tmp_path):
    entry,source,archive=original;result,_=publish(entry,source,tmp_path)
    dest=Path(result['output_path']);backup=retention.recovery_source(dest)
    recovery={**entry,'path':str(backup),'replacement_path':str(dest)}
    plan=output.plan(recovery,store.settings());Path(plan['stage']).write_bytes(b'improved cleaning')
    improved=output.finish(plan,{'success':True},tmp_path/'new-receipt.json')
    assert dest.read_bytes()==b'improved cleaning' and backup.read_bytes()==b'original unmuted audio'
    assert improved['original_backup_id']==result['original_backup_id']
    assert retention.recovery_source(dest)==backup


def test_retained_copy_is_not_automatically_queued(original,tmp_path):
    entry,source,_=original;result,_=publish(entry,source,tmp_path)
    files=[(5,'Example',{'path':result['output_path']})]
    store.save_settings({'sonarr_url':'http://sonarr','sonarr_api_key':'test'})
    with patch.object(service.Arr,'files',return_value=files):assert service.queue_item('sonarr',1)==0


def test_interrupted_or_failed_backup_never_removes_original(original,tmp_path,monkeypatch):
    entry,source,_=original;plan=output.plan(entry,store.settings());Path(plan['stage']).write_bytes(b'cleaned')
    monkeypatch.setattr(retention.shutil,'copy2',lambda a,b:Path(b).write_bytes(b'incomplete'))
    with pytest.raises(ValueError,match='verification failed'):output.finish(plan,{'success':True},tmp_path/'receipt.json')
    assert source.read_bytes()==b'original unmuted audio' and not Path(plan['destination']).exists()


def test_reprocess_preview_uses_retained_original_not_muted_file(original,tmp_path):
    entry,source,_=original;store.enqueue(entry);claimed=store.claim(3)
    result,_=publish({**entry,'id':claimed['id']},source,tmp_path);store.finish(claimed,result,store.settings())
    dest=Path(result['output_path']);backup=retention.recovery_source(dest)
    import os,time
    os.utime(backup,(time.time()-300,)*2)
    # Update the registered signature after deliberately aging the fixture.
    with store.db() as db:db.execute('UPDATE original_backups SET signature=?',(json.dumps(output.signature(backup)),))
    write_subs(backup.with_suffix('.srt'),[(10,12)],'damn '+ENGLISH)
    data={'streams':[{'index':0,'codec_type':'video'},{'index':1,'codec_type':'audio','tags':{'language':'eng'}}]}
    store.save_settings({'sonarr_url':'http://sonarr','sonarr_api_key':'test'})
    with patch.object(service.Arr,'files',return_value=[(5,'Example',{'path':str(dest)})]),patch.object(reprocessing.cli,'probe',return_value=(data,30)):
        preview=reprocessing.preview(claimed['id'])
        assert preview['eligible'] and preview['retained_original'] and preview['source']==str(backup)
