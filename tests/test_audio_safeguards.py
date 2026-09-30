"""Language exclusions must survive manual queues and already queued jobs."""
import json
import os
import time
from unittest.mock import patch

import pytest
from backend import store, service, selection, output, notifications
from cli import bleeparr as cli
from test_app import client, job
from test_output import setup, media, job as media_job


@pytest.mark.parametrize('file,skipped',[
    ({'mediaInfo':{'audioLanguages':'fre'}}, True),
    ({'mediaInfo':{'audioLanguages':'fre/eng'}}, False),
    ({'mediaInfo':{'audioLanguages':'French; English'}}, False),
    ({'languages':[{'name':'French'}]}, True),
    ({'languages':[{'name':'French'},{'name':'English'}]}, False),
    ({'mediaInfo':{'audioLanguages':'eng'},'languages':[{'name':'French'}]}, False),
    ({'mediaInfo':{'audioLanguages':'fre'},'languages':[{'name':'English'}]}, True),
    ({'mediaInfo':{'audioLanguages':'und'},'languages':[{'name':'French'}]}, False),
    ({'mediaInfo':{'audioLanguages':'fre/und'}}, False),
    ({'mediaInfo':{'subtitles':'fre'}}, False),
    ({}, False),
])
def test_audio_metadata_policy_does_not_confuse_subtitle_language(file, skipped):
    assert bool(selection.audio_skip_reason(file)) is skipped


def test_known_foreign_movie_is_excluded_even_if_manually_monitored(client):
    config={**store.settings(),'cleanvid_enabled':True,'cleanvid_roots':'/media',
            'radarr_url':'http://radarr','radarr_api_key':'test'}
    item={'id':1,'title':'Foreign movie','path':'/media/movie','movieFile':{'mediaInfo':{'audioLanguages':'fre'}}}
    assert selection.state(item,config,{1},set())=='foreign_audio'
    store.save_settings(config)
    with patch.object(service.Arr,'library',return_value=[item]),patch.object(service.Arr,'request',return_value=item):
        presented=client.get('/api/library/radarr').json()[0]
        assert not presented['selected'] and 'skipped' in presented['processing_states']
        assert 'non-English audio' in presented['skip_reason']
        assert client.put('/api/library/radarr/1/monitor',json={'enabled':True}).status_code==400
    with store.db() as db:assert db.execute('SELECT count(*) FROM monitored').fetchone()[0]==0


@pytest.mark.parametrize('kind',['sonarr','radarr'])
def test_manual_queue_skips_foreign_files_but_keeps_english_tracks(client,tmp_path,kind):
    store.save_settings({kind+'_url':'http://manager',kind+'_api_key':'test'})
    folder=tmp_path/'media';folder.mkdir()
    files=[]
    for i,lang in enumerate(['fre','fre/eng','und'],1):
        path=folder/f'{i}.mkv';path.write_bytes(b'original')
        os.utime(path,(time.time()-300,time.time()-300))
        files.append((i,f'Title {i}',{'path':str(path),'mediaInfo':{'audioLanguages':lang}}))
    with patch.object(service.Arr,'files',return_value=files):
        assert service.queue_item(kind,7)==2
    assert {x['item_id'] for x in store.jobs()}=={2,3}


@pytest.mark.parametrize('dry_run',[False,True])
def test_cli_foreign_audio_skips_before_subtitle_or_model_loading(tmp_path,dry_run):
    path=tmp_path/'movie.mkv';path.write_bytes(b'original')
    words=tmp_path/'words.txt';words.write_text('damn')
    args=cli.parser().parse_args(['--input',str(path),'--swears',str(words),'--delete-original']+(['--dry-run'] if dry_run else []))
    data={'streams':[dict(index=0,codec_type='video'),dict(index=1,codec_type='audio',tags={'language':'fre'})]}
    with patch.object(cli,'probe',return_value=(data,30)),patch.object(cli,'resolve_subtitle') as subs,patch.object(cli,'load_speech_model') as speech,patch.object(cli,'render') as render:
        result=cli.process(args)
        subs.assert_not_called();speech.assert_not_called();render.assert_not_called()
    assert result['success'] and result['outcome']=='skipped_language' and result['output_path'] is None
    assert path.read_bytes()==b'original' and not cli.default_output(path,'(profanity removed)').exists()


def test_english_audio_is_preferred_and_explicit_foreign_selection_is_skipped(tmp_path):
    path=tmp_path/'movie.mkv';path.write_bytes(b'original')
    words=tmp_path/'words.txt';words.write_text('damn')
    data={'streams':[dict(index=0,codec_type='video'),dict(index=1,codec_type='audio',tags={'language':'fre'},disposition={'default':1}),dict(index=2,codec_type='audio',tags={'language':'eng'})]}
    assert cli.select_audio(data,'eng')==2
    args=cli.parser().parse_args(['--input',str(path),'--swears',str(words),'--audio-stream','1'])
    with patch.object(cli,'probe',return_value=(data,30)):
        assert cli.process(args)['outcome']=='skipped_language'


def test_already_queued_foreign_media_never_publishes_or_records_cleaning(setup):
    import subprocess
    src=media(setup)
    tagged=src.with_name('french.mkv')
    subprocess.run(['ffmpeg','-v','error','-i',str(src),'-c','copy','-metadata:s:a:0','language=fre',str(tagged)],check=True)
    before=output.signature(tagged)
    candidate=media_job(tagged)
    store.enqueue({k:candidate[k] for k in ('fingerprint','kind','item_id','parent_id','title','path','remote_path')})
    claimed=store.claim(3)
    with patch.object(output,'finish',side_effect=AssertionError('Skipped media must not publish')):
        result=service.run_job(claimed,{**store.settings(),'output_mode':'replace'})
    assert result['success'] and result['outcome']=='skipped_language'
    assert store.finish(claimed,result,store.settings())=='skipped'
    assert output.signature(tagged)==before
    assert not output.is_processed(tagged) and store.claim(3) is None
    assert not (store.data_dir()/'jobs'/str(claimed['id'])/'delivery.json').exists()
    assert notifications.history()==[]
    with store.db() as db:
        for table in ('processed_outputs','plex_updates','searches','replacements'):
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0


@pytest.mark.parametrize('code',['speech_model','speech_model_missing','speech_unresolved',
                                'subtitle_language_mismatch','subtitle_language_uncertain','subtitle_coverage_suspect'])
def test_review_failures_do_not_retry_or_offer_release_replacement(client,code):
    store.enqueue(job());claimed=store.claim(3)
    result={'success':False,'error_code':code}
    assert store.finish(claimed,result,store.settings())=='failed'
    assert store.claim(3) is None
    with pytest.raises(ValueError,match='invalid media'):
        service.request_search({**claimed,'result':result})
    assert code not in service.RETRYABLE_MEDIA


def test_no_fallback_strategy_is_persisted_by_settings(client):
    assert store.settings()['bleeptool']=='S-M-FSM'
    assert client.put('/api/settings',json={'bleeptool':'S-M'}).status_code==200
    store.init()
    assert store.settings()['bleeptool']=='S-M'
