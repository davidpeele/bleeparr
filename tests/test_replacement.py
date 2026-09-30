import hashlib
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from backend import replacement, store, service


@pytest.fixture(params=['sonarr','radarr'])
def setup(request,tmp_path,monkeypatch):
    kind=request.param
    monkeypatch.setenv('DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('MEDIA_ROOTS',str(tmp_path))
    store.init()
    source=tmp_path/'file.mkv';source.write_bytes(b'bad data')
    stat=source.stat()
    job=dict(id=1,kind=kind,item_id=2,parent_id=3,title='Example',path=str(source),remote_path=str(source),
             fingerprint=hashlib.sha256(repr((kind,str(source),stat.st_size,stat.st_mtime_ns)).encode()).hexdigest(),result={'error_code':'invalid_media'})
    config={**store.settings(),'auto_blocklist':True,kind+'_url':'http://manager',kind+'_api_key':'test'}
    file=dict(id=4,path=str(source),size=stat.st_size,dateAdded='2026-01-01T00:00:00Z')
    key='episodeId' if kind=='sonarr' else 'movieId'
    grab=dict(id=8,eventType='grabbed',downloadId='download1',sourceTitle='Release',date='2025-12-31T23:58:00Z',data={'releaseSource':'Rss'},**{key:2})
    imported=dict(id=9,eventType='downloadFolderImported',downloadId='download1',sourceTitle='Release',date='2026-01-01T00:00:01Z',data={'importedPath':str(source)},**{key:2})
    state=dict(records=[imported,grab],download=[imported,grab],episodes=[{'episodeFileId':4}],native=True,posts=[],file=file)
    def api(self,method,resource,**kw):
        if method=='POST':
            state['posts'].append((resource,kw))
            if state.get('timeout'):raise ValueError('unreachable')
            return {}
        if resource=='episode/2':return {'seriesId':3,'episodeFileId':4}
        if resource=='episodefile/4':return file
        if resource=='episode':return state['episodes']
        if resource=='movie/2':return {'movieFile':file}
        if resource=='history':
            records=state['download'] if 'downloadId' in kw['params'] else state['records']
            return {'records':records,'totalRecords':len(records)}
        if resource=='config/downloadclient':return {'autoRedownloadFailed':state['native'],'autoRedownloadFailedFromInteractiveSearch':False}
        raise AssertionError(resource)
    monkeypatch.setattr(service.Arr,'request',api)
    return job,config,state


def test_exact_match_native_search_once_and_source_retained(setup):
    job,config,state=setup
    assert replacement.prepare(job,config)['release']=='Release'
    assert not state['posts']
    assert 'search requested' in replacement.request(job,config)['message']
    assert [p[0] for p in state['posts']]==['history/failed/8']
    assert Path(job['path']).exists()
    with pytest.raises(ValueError,match='already has'):replacement.request(job,config)
    assert len(state['posts'])==1


def test_explicit_search_when_native_disabled(setup):
    job,config,state=setup;state['native']=False
    replacement.request(job,config)
    assert state['posts'][1][0]=='command'
    assert state['posts'][1][1]['json']['name']==('EpisodeSearch' if job['kind']=='sonarr' else 'MoviesSearch')


@pytest.mark.parametrize('problem',['local_failure','changed','path','date','missing_grab','pack','disabled'])
def test_unsafe_cases_never_mutate_manager(setup,problem):
    job,config,state=setup
    if problem=='local_failure':job['result']['error_code']='out_of_memory'
    if problem=='changed':Path(job['path']).write_bytes(b'new release')
    if problem=='path':state['records'][0]['data']['importedPath']='/different.mkv'
    if problem=='date':state['file']['dateAdded']='2026-02-01T00:00:00Z'
    if problem=='missing_grab':state['download']=[]
    if problem=='pack':state['download'].append({**state['download'][1],('episodeId' if job['kind']=='sonarr' else 'movieId'):7})
    if problem=='disabled':config['auto_blocklist']=False
    with pytest.raises(ValueError):replacement.request(job,config)
    assert not state['posts']


def test_unknown_post_outcome_not_resent(setup):
    job,config,state=setup;state['timeout']=True
    with pytest.raises(ValueError,match='uncertain'):replacement.request(job,config)
    with pytest.raises(ValueError,match='already has'):replacement.request(job,config)
    assert len(state['posts'])==1
    with store.db() as db:assert db.execute('SELECT status FROM replacements').fetchone()[0]=='outcome_unknown'


def test_cooldown_and_rolling_limit(setup):
    import time
    job,config,state=setup
    with store.db() as db:db.execute('INSERT INTO searches VALUES (?,?,?,?)',(job['kind'],2,time.time(),'requested'))
    with pytest.raises(ValueError,match='cooldown'):replacement.request(job,config)
    with store.db() as db:
        db.execute('DELETE FROM searches')
        for i in range(3):db.execute('INSERT INTO replacements VALUES (?,?,?,?,?,?,?,?)',(job['kind'],str(i),2,i,8,time.time()-2*86400,'requested','release'))
    with pytest.raises(ValueError,match='limit'):replacement.request(job,config)
    assert not state['posts']


def test_latest_import_must_match_not_older_same_name(setup):
    job,config,state=setup
    state['records'].insert(0,{**state['records'][0],'date':'2026-02-01T00:00:00Z','data':{'importedPath':'/new-release.mkv'}})
    with pytest.raises(ValueError,match='unambiguously'):replacement.request(job,config)
    assert not state['posts']


def test_interactive_native_search_disabled_gets_one_explicit_search(setup):
    job,config,state=setup
    state['download'][1]['data']['releaseSource']='InteractiveSearch'
    replacement.request(job,config)
    assert [x[0] for x in state['posts']]==['history/failed/8','command']
