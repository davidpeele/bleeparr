import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
from backend import store, service
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('DISABLE_WORKER', '1')
    monkeypatch.setenv('MEDIA_ROOTS', str(tmp_path / 'media'))
    monkeypatch.delenv('BLEEPARR_TOKEN', raising=False)
    with TestClient(app) as client:
        yield client


def job(identity='first', **values):
    return dict(fingerprint=identity, kind='sonarr', item_id=5, parent_id=1, title='Example', path='/media/test.mkv', remote_path='/tv/test.mkv', **values)


def test_settings_persist_and_hide_keys(client):
    assert client.put('/api/settings', json={'sonarr_url':'http://sonarr:8989', 'sonarr_api_key':'secret'}).status_code == 200
    data = client.get('/api/settings').json()
    assert data['sonarr_key_configured'] and data['sonarr_api_key'] == ''
    client.put('/api/settings', json={'sonarr_api_key':''})
    assert store.settings()['sonarr_api_key'] == 'secret'
    assert client.put('/api/settings', json={'cpu_threads':0}).status_code == 422
    assert client.put('/api/settings', json={'swears':'\n'}).status_code == 400


def test_queue_persists_claims_once_and_retries(client):
    assert store.enqueue(job()) == 1
    assert store.enqueue(job()) == 0
    claimed = store.claim(3)
    assert claimed['attempts'] == 1 and store.claim(3) is None
    assert store.finish(claimed, {'success':False,'error_code':'subtitle_missing'}, store.settings()) == 'retry'
    assert store.claim(3) is None
    assert client.post(f"/api/jobs/{claimed['id']}/retry").status_code == 200
    assert store.claim(3)['attempts'] == 1


def test_failed_job_does_not_block_following_item(client):
    store.enqueue(job('first'))
    store.enqueue(job('second'))
    first = store.claim(3)
    store.finish(first, {'success':False,'error_code':'invalid_media'}, store.settings())
    assert store.claim(3)['fingerprint'] == 'second'


def test_restart_recovers_inflight_jobs(client):
    store.enqueue(job())
    store.claim(3)
    store.init()
    assert store.jobs()[0]['status'] == 'retry'


def test_movie_and_series_ids_do_not_collide(client):
    with store.db() as conn:
        conn.execute('INSERT INTO monitored VALUES (?,?,?)', ('sonarr',1,'TV'))
        conn.execute('INSERT INTO monitored VALUES (?,?,?)', ('radarr',1,'Movie'))
        assert conn.execute('SELECT count(*) FROM monitored').fetchone()[0] == 2


def test_path_mapping_rejects_escape_and_symlink(client, tmp_path):
    media = tmp_path / 'media'
    media.mkdir()
    config = {**store.settings(), 'sonarr_path_from':'/tv', 'sonarr_path_to':str(media)}
    assert service.local_path('/tv/show.mkv','sonarr',config) == media / 'show.mkv'
    with pytest.raises(ValueError):
        service.local_path('/tv/../secret','sonarr',config)
    (media / 'link').symlink_to(tmp_path)
    with pytest.raises(ValueError):
        service.local_path('/tv/link/secret','sonarr',config)


def test_auth_and_cross_origin_writes(client, monkeypatch):
    monkeypatch.setenv('BLEEPARR_TOKEN','test-token')
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/settings').status_code == 401
    headers = {'Authorization':'Bearer test-token'}
    assert client.get('/api/settings',headers=headers).status_code == 200
    assert client.put('/api/settings',json={'auto_process':True},headers={**headers,'Origin':'https://other.example'}).status_code == 403


def test_replacement_only_for_bad_media_and_rate_limited(client):
    candidate = {**job(), 'result':{'error_code':'disk_full'}}
    with pytest.raises(ValueError, match='invalid media'):
        service.request_search(candidate)
    store.save_settings({'sonarr_url':'http://sonarr:8989','sonarr_api_key':'secret'})
    candidate['result'] = {'error_code':'invalid_media'}
    with patch.object(service.Arr, 'request', return_value={'id':7}) as request:
        assert service.request_search(candidate)['command_id'] == 7
        request.assert_called_once_with('POST','command',json={'name':'EpisodeSearch','episodeIds':[5]})
        with pytest.raises(ValueError,match='cooldown'):
            service.request_search(candidate)


def test_search_timeout_does_not_repeat_command(client):
    store.save_settings({'sonarr_url':'http://sonarr:8989','sonarr_api_key':'secret'})
    candidate = {**job(), 'result':{'error_code':'invalid_media'}}
    with patch.object(service.Arr, 'request', side_effect=ValueError('timeout')) as request:
        with pytest.raises(ValueError):
            service.request_search(candidate)
        with pytest.raises(ValueError,match='cooldown'):
            service.request_search(candidate)
        assert request.call_count == 1


def test_monitor_and_queue_uses_real_persistent_store(client, tmp_path):
    media = tmp_path / 'media'
    media.mkdir()
    path = media / 'show.mkv'
    path.write_bytes(b'fixture')
    os.utime(path,(time.time()-300,time.time()-300))
    store.save_settings({'sonarr_url':'http://sonarr:8989','sonarr_api_key':'secret'})
    with patch.object(service.Arr,'files',return_value=[(5,'Example',{'id':9,'path':str(path)})]):
        assert client.post('/api/library/sonarr/1/queue').json()['queued'] == 1
        assert client.post('/api/library/sonarr/1/queue').json()['queued'] == 0
    assert client.get('/api/status').json()['counts']['queued'] == 1


def test_add_movie_uses_validated_manager_options(client):
    store.save_settings({'radarr_url':'http://radarr:7878','radarr_api_key':'secret'})
    def request(method, resource, **kwargs):
        if resource == 'movie/lookup': return [{'tmdbId':42,'title':'Example','year':2026}]
        if resource == 'qualityprofile': return [{'id':1,'name':'HD'}]
        if resource == 'rootfolder': return [{'path':'/movies'}]
        assert method == 'POST' and resource == 'movie'
        assert kwargs['json']['addOptions']['searchForMovie'] is False
        return {'id':7,'title':'Example'}
    with patch.object(service.Arr,'request',side_effect=request):
        assert client.post('/api/discover/radarr',json={'external_id':42,'quality_profile_id':1,'root_folder':'/movies'}).status_code == 200
    with store.db() as conn:
        assert conn.execute("SELECT title FROM monitored WHERE kind='radarr' AND item_id=7").fetchone()[0] == 'Example'


def test_worker_runs_actual_cli_on_synthetic_media(client, tmp_path, monkeypatch):
    import subprocess
    media = tmp_path / 'media'; media.mkdir()
    video = media / 'sample.mkv'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=160x120:r=10:d=3','-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','mpeg4','-c:a','pcm_s16le',str(video)],check=True)
    video.with_suffix('.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nDamn. We are going to meet our friends at the station before the train leaves tomorrow morning. Please remember to bring your bag and check that everyone knows where to go. I think we have enough time to walk there together after breakfast. The weather should be pleasant and the children are looking forward to seeing the countryside. We can stop for lunch when we arrive and then visit the museum near the river. It will be a wonderful day if we all stay together and keep an eye on the time.\n')
    from test_subtitles import FRENCH, write_subs
    write_subs(video.with_suffix('.en.srt'), [(1, 2)], FRENCH)
    monkeypatch.setenv('BLEEPARR_CLI',str(Path(__file__).parents[1] / 'cli' / 'bleeparr.py'))
    monkeypatch.setenv('OUTPUT_DIR',str(tmp_path / 'cleaned'))
    service.STOP.clear()
    candidate = {**job(), 'id':1, 'path':str(video)}
    config = {**store.settings(), 'bleeptool':'FSM', 'swears':'damn',
              'check_subtitle_timing':False,'review_broad_muting':False}
    result = service.run_job(candidate,config)
    assert result['success'] and result['fallback_sections'] == 1
    assert result['subtitle_attempts'][0]['error_code'] == 'subtitle_language_mismatch'
    assert result['subtitle_attempts'][-1]['status'] == 'accepted'
    assert video.exists() and Path(result['output_path']).exists()


def test_settings_accept_phrases_and_reject_punctuation_only(client):
    value = 'eat my shorts\ndamn\n'
    assert client.put('/api/settings',json={'swears':value}).status_code == 200
    assert client.get('/api/settings').json()['swears'] == value
    assert client.put('/api/settings',json={'swears':'!!!'}).status_code == 400


def test_output_settings_validate_and_persist(client):
    assert client.get('/api/settings').json()['output_mode']=='separate'
    for mode in ['alongside','replace','separate']:
        assert client.put('/api/settings',json={'output_mode':mode}).status_code==200
        assert client.get('/api/settings').json()['output_mode']==mode
    assert client.put('/api/settings',json={'output_mode':'delete_first'}).status_code==422
    assert client.put('/api/settings',json={'output_directory':'/outside-output-mount'}).status_code==400
    assert client.put('/api/settings',json={'output_directory':'TV'}).status_code==200


def test_worker_failure_distinguishes_memory_kill():
    assert service.worker_failure(-9, 4, 5)['error_code'] == 'out_of_memory'
    for before, after in [(4, 4), (None, None), (None, 5)]:
        result = service.worker_failure(-9, before, after)
        assert result['error_code'] == 'worker_exit'
        assert 'signal 9' in result['error']
    assert service.worker_failure(1, 4, 5)['error_code'] == 'worker_exit'


def test_log_shows_recorded_failure_without_worker_output(client):
    store.enqueue(job())
    claimed = store.claim(3)
    store.finish(claimed, {'success': False, 'error_code': 'out_of_memory', 'error': 'Memory limit exceeded'}, store.settings())
    response = client.get(f"/api/jobs/{claimed['id']}/log").json()['log']
    assert 'out_of_memory' in response and 'Memory limit exceeded' in response


def test_library_includes_inherited_history_and_mixed_states(client, tmp_path):
    store.save_settings({'sonarr_url': 'http://sonarr:8989', 'sonarr_api_key': 'test'})
    from backend import output
    media = tmp_path / 'media'; media.mkdir()
    series = media / 'Show'; series.mkdir()
    cleaned = series / 'episode.mkv'; cleaned.write_bytes(b'cleaned')
    with store.db() as conn:
        conn.execute('INSERT INTO legacy_completions VALUES (?,?,?)', (str(cleaned), json.dumps(output.signature(cleaned)), 0))
    store.enqueue({**job(), 'path': str(series / 'next.mkv')})
    items = [dict(id=1, title='Show', path=str(series), year=2025, certification='TV-MA', added='2026-09-01T00:00:00Z', statistics={'episodeFileCount': 2})]
    with patch.object(service.Arr, 'library', return_value=items):
        item = client.get('/api/library/sonarr').json()[0]
        assert item['content_rating'] == 'TV-MA'
        assert item['processing_states'] == ['processed', 'queued']
        assert item['processed_files'] == 1 and item['added'] == items[0]['added']
        cleaned.write_bytes(b'changed after inheritance')
        assert client.get('/api/library/sonarr').json()[0]['processing_states'] == ['queued']


def test_library_does_not_mix_movie_and_series_ids(client, tmp_path):
    store.save_settings({'radarr_url': 'http://radarr:7878', 'radarr_api_key': 'test'})
    store.enqueue(job())
    with patch.object(service.Arr, 'library', return_value=[dict(id=1, title='Movie', path=str(tmp_path / 'media' / 'Movie'))]):
        item = client.get('/api/library/radarr').json()[0]
    assert item['content_rating'] == 'Not rated'
    assert item['processing_states'] == ['unprocessed']


def test_blocklist_setting_is_opt_in_and_validated(client):
    assert client.get('/api/settings').json()['auto_blocklist'] is False
    assert client.put('/api/settings',json={'auto_blocklist':True,'replacement_limit':2}).status_code==200
    assert store.settings()['auto_blocklist'] is True
    assert client.put('/api/settings',json={'replacement_limit':0}).status_code==422
    assert client.put('/api/settings',json={'replacement_cooldown_hours':1}).status_code==422
    assert client.get('/api/jobs/999/replacement-preview').status_code==404


def test_no_matches_can_be_explicitly_retried_but_cannot_search(client):
    store.enqueue(job()); claimed=store.claim(3)
    store.finish(claimed,{'success':True,'outcome':'no_matches_found','output_path':None},store.settings())
    assert client.get('/api/status').json()['jobs'][0]['status']=='no_matches'
    assert client.post(f"/api/jobs/{claimed['id']}/search").status_code==404
    assert client.post(f"/api/jobs/{claimed['id']}/retry").status_code==200
    assert store.claim(3)['id']==claimed['id']
