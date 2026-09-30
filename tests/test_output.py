import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))
from backend import store, service, output


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path/'data'))
    monkeypatch.setenv('MEDIA_ROOTS', str(tmp_path/'media'))
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path/'cleaned'))
    monkeypatch.setenv('BLEEPARR_CLI', str(Path(__file__).parents[1]/'cli'/'bleeparr.py'))
    (tmp_path/'media').mkdir()
    store.init(); service.STOP.clear()
    # Publication fixtures contain tones, not dialogue for speech verification.
    store.save_settings({'check_subtitle_timing':False,'review_broad_muting':False})
    return tmp_path


def media(root, extension='mkv'):
    p=root/'media'/('episode.'+extension)
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=160x120:r=10:d=4','-f','lavfi','-i','sine=frequency=440:duration=4','-c:v','mpeg4','-c:a','aac',str(p)],check=True)
    p.with_suffix('.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nshit We are going to meet our friends at the station before the train leaves tomorrow morning. Please remember to bring your bag and check that everyone knows where to go. I think we have enough time to walk there together after breakfast. The weather should be pleasant and the children are looking forward to seeing the countryside. We can stop for lunch when we arrive and then visit the museum near the river. It will be a wonderful day if we all stay together and keep an eye on the time.\n')
    os.chmod(p,0o644)
    return p


def job(p):
    return dict(id=1,fingerprint='ab'*32,kind='sonarr',item_id=1,parent_id=1,title='Episode',path=str(p),remote_path=str(p),attempts=1)


@pytest.mark.parametrize('mode,extension',[('separate','mkv'),('alongside','mkv'),('replace','mkv'),('replace','mp4')])
def test_real_processing_modes(setup,mode,extension):
    src=media(setup,extension); original=src.read_bytes()
    result=service.run_job(job(src),{**store.settings(),'output_mode':mode,'bleeptool':'FSM'})
    assert result['success'], result
    dest=Path(result['output_path']); assert dest.is_file()
    assert dest.stat().st_mode & 0o777 == 0o644
    assert output.matches(dest,result['output_signature'])
    if mode=='replace':
        assert dest==src.with_name('episode (profanity removed).mkv')
        assert not src.exists()
    else:
        assert src.read_bytes()==original
        assert dest.parent==(setup/'cleaned' if mode=='separate' else src.parent)
    # Recovering after publication is idempotent, including original deletion.
    again=service.run_job(job(src),{**store.settings(),'output_mode':mode})
    assert again==result


def test_invalid_media_never_removes_original(setup):
    src=setup/'media'/'bad.mkv';src.write_bytes(b'not media')
    result=service.run_job(job(src),{**store.settings(),'output_mode':'replace','bleeptool':'FSM'})
    assert not result['success'];assert src.read_bytes()==b'not media'


def test_destination_collision_preserves_both(setup):
    src=setup/'media'/'show.mp4';src.write_bytes(b'original')
    src.with_name('show (profanity removed).mkv').write_bytes(b'unrelated')
    with pytest.raises(ValueError,match='already exists'):output.plan(job(src),{'output_mode':'replace'})
    assert src.read_bytes()==b'original';assert src.with_name('show (profanity removed).mkv').read_bytes()==b'unrelated'


def test_changed_source_cancels_replacement(setup):
    src=setup/'media'/'show.mkv';src.write_bytes(b'original')
    plan=output.plan(job(src),{'output_mode':'replace'})
    Path(plan['stage']).write_bytes(b'validated cleaned')
    src.write_bytes(b'new release')
    with pytest.raises(ValueError,match='Original changed'):
        output.finish(plan,{'success':True},setup/'receipt.json')
    assert src.read_bytes()==b'new release'


@pytest.mark.parametrize('extension',['mkv','mp4'])
def test_restart_between_publication_and_deletion(setup,extension):
    src=setup/'media'/('show.'+extension);src.write_bytes(b'original')
    plan=output.plan(job(src),{'output_mode':'replace'})
    stage=Path(plan['stage']);stage.write_bytes(b'cleaned')
    receipt={**plan,'cleaned_signature':output.signature(stage),'result':{'success':True}}
    dest=Path(plan['destination'])
    if dest==src:os.replace(stage,dest)
    else:os.link(stage,dest)
    result=output.publish(receipt)
    assert result['success'] and dest.read_bytes()==b'cleaned'
    assert output.is_processed(dest)
    if extension=='mp4':assert not src.exists()
    assert output.publish(receipt)==result


def test_completed_replacement_is_not_requeued(setup):
    src=media(setup);entry=job(src);store.enqueue(entry);claimed=store.claim(3)
    result=service.run_job(claimed,{**store.settings(),'output_mode':'replace','bleeptool':'FSM'})
    store.finish(claimed,result,store.settings());assert output.is_processed(Path(result['output_path']))
    config={**store.settings(),'sonarr_path_from':'','sonarr_path_to':'','sonarr_url':'http://sonarr','sonarr_api_key':'test'}
    with patch.object(service.Arr,'files',return_value=[(1,'Episode',{'path':str(src)})]):
        assert service.queue_item('sonarr',1,config)==0
    src.write_bytes(b'new upgrade');assert not output.is_processed(src)


def test_separate_folder_cannot_escape_mount(setup):
    with pytest.raises(ValueError):output.separate_root({'output_directory':str(setup/'elsewhere')})
    assert output.separate_root({'output_directory':str(setup/'cleaned'/'TV')})==setup/'cleaned'/'TV'


def test_readonly_destination_fails_before_processing(setup):
    src=setup/'media'/'show.mkv';src.write_bytes(b'original')
    with patch.object(output.tempfile,'TemporaryFile',side_effect=OSError('Read-only file system')):
        with pytest.raises(ValueError,match='not writable'):
            output.plan(job(src),{'output_mode':'replace'})
    assert src.read_bytes()==b'original'


def test_imported_success_is_invalidated_when_file_changes(setup):
    src=setup/'media'/'legacy.mkv';src.write_bytes(b'old completion')
    with store.db() as db:
        db.execute('INSERT INTO legacy_completions VALUES (?,?,?)',(str(src),json.dumps(output.signature(src)),123))
    assert output.is_processed(src)
    src.write_bytes(b'new release');assert not output.is_processed(src)


def test_legacy_recovery_uses_original_only_for_same_failed_output(setup):
    bad=setup/'media'/'edited.mkv';bad.write_bytes(b'bad')
    original=setup/'media'/'original.mkv';original.write_bytes(b'original')
    with store.db() as db:
        db.execute('INSERT INTO legacy_recovery_inputs VALUES (?,?,?)',(str(bad),json.dumps(output.signature(bad)),str(original)))
    assert output.recovery_input(bad)==original
    bad.write_bytes(b'new file');assert output.recovery_input(bad)==bad


def test_recovered_original_replaces_manager_indexed_failed_output(setup):
    src=media(setup);bad=src.with_name('episode (edited by Bleeparr).mkv');bad.write_bytes(b'broken output')
    with store.db() as db:
        db.execute('INSERT INTO legacy_recovery_inputs VALUES (?,?,?)',(str(bad),json.dumps(output.signature(bad)),str(src)))
    entry={**job(src),'remote_path':str(bad)}
    result=service.run_job(entry,{**store.settings(),'output_mode':'replace','bleeptool':'FSM'})
    assert result['success'],result
    dest=src.with_name('episode (profanity removed).mkv')
    assert result['output_path']==str(dest) and dest.stat().st_size>100
    assert not src.exists() and not bad.exists() and output.is_processed(dest)
    assert service.run_job(entry,store.settings())==result


def test_recovery_never_overwrites_changed_manager_target(setup):
    src=setup/'media'/'original.mkv';src.write_bytes(b'original')
    bad=setup/'media'/'edited.mkv';bad.write_bytes(b'old bad output')
    with store.db() as db:db.execute('INSERT INTO legacy_recovery_inputs VALUES (?,?,?)',(str(bad),json.dumps(output.signature(bad)),str(src)))
    plan=output.plan({**job(src),'replacement_path':str(bad)},{'output_mode':'replace'})
    Path(plan['stage']).write_bytes(b'cleaned');bad.write_bytes(b'new manager release')
    with pytest.raises(ValueError,match='Failed output changed'):
        output.finish(plan,{'success':True},setup/'receipt.json')
    assert bad.read_bytes()==b'new manager release' and src.read_bytes()==b'original'


@pytest.mark.parametrize('name', ['Show.mkv', 'Show (edited by Bleeparr).mkv', 'Show (eddited by Bleeparr).mp4', 'Show (profanity removed).mkv', 'Show (edited by Bleeparr) (profanity removed).mkv'])
def test_cleaned_name_normalizes_tags(name):
    assert output.cleaned_name(Path(name)) == 'Show (profanity removed).mkv'


def test_already_tagged_alongside_does_not_replace_source(setup):
    src=setup/'media'/'Show (profanity removed).mkv'; src.write_bytes(b'original')
    with pytest.raises(ValueError, match='already has'):
        output.plan(job(src), {'output_mode':'alongside'})
    assert output.plan(job(src), {'output_mode':'replace'})['destination'] == str(src)


def test_rename_requests_manager_rescan_without_failing_completed_output(setup):
    config={**store.settings(), 'sonarr_url':'http://sonarr', 'sonarr_api_key':'test'}
    entry=job(setup/'media'/'episode.mkv')
    result={'success':True,'output_mode':'replace','output_path':'/new.mkv'}
    with patch.object(service.Arr,'request',return_value={}) as call:
        assert service.refresh_renamed_media(result,entry,config)['library_refresh']=='requested'
        assert call.call_args.kwargs['json']=={'name':'RescanSeries','seriesId':1}
    with patch.object(service.Arr,'request',side_effect=ValueError('offline')):
        assert service.refresh_renamed_media(result,entry,config)['success']


def test_unwritable_job_is_blocked_then_resumes_when_fixed(setup):
    src=setup/'media'/'blocked.mkv';src.write_bytes(b'input')
    store.enqueue(job(src));claimed=store.claim(3)
    config={**store.settings(),'output_mode':'replace','email_enabled':True}
    with patch.object(output.tempfile,'TemporaryFile',side_effect=OSError('Read-only file system')):
        result=service.run_job(claimed,config)
        assert result['error_code']=='output_unwritable'
        assert store.finish(claimed,result,config)=='blocked'
        service.resume_writable_jobs(config)
        assert store.jobs()[0]['status']=='blocked'
    with store.db() as db:assert db.execute('SELECT count(*) FROM notifications').fetchone()[0]==0
    service.resume_writable_jobs(config)
    assert store.jobs()[0]['status']=='queued'
    assert store.jobs()[0]['attempts']==0


def test_real_no_matches_preserves_original_and_never_publishes(setup):
    src=media(setup); before=output.signature(src)
    candidate=job(src)
    store.enqueue({k:candidate[k] for k in ('fingerprint','kind','item_id','parent_id','title','path','remote_path')})
    claimed=store.claim(3)
    with patch.object(output,'finish',side_effect=AssertionError('No-match output must not be published')):
        result=service.run_job(claimed,{**store.settings(),'output_mode':'replace','swears':'unmatchablecustomtoken','bleeptool':'FSM'})
    assert result['success'] and result['outcome']=='no_matches_found', result
    assert result['output_path'] is None and result['matched_word_count']==0
    assert output.signature(src)==before
    assert not (store.data_dir()/'jobs'/str(claimed['id'])/'delivery.json').exists()
    assert store.finish(claimed,result,store.settings())=='no_matches'
    assert not output.is_processed(src)
    assert store.claim(3) is None
    with store.db() as db:
        assert db.execute('SELECT count(*) FROM processed_outputs').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM plex_updates').fetchone()[0]==0
