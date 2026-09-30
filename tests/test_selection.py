from unittest.mock import patch
import pytest
from test_app import client
from backend import store, service, selection


def config():
    return {**store.settings(),'cleanvid_enabled':True,'cleanvid_roots':'/srv/media/CleanVid','sonarr_url':'http://sonarr','sonarr_api_key':'test','radarr_url':'http://radarr','radarr_api_key':'test'}


@pytest.mark.parametrize('path,expected',[
('/srv/media/CleanVid/TV/Show',True),('/srv/media/CleanVid/Movies/Film',True),
('/srv/media/CleanVid2/Film',False),('/srv/media/TV/Show',False),
('/srv/media/CleanVid/../TV/Show',False),('',False),
('relative/CleanVid/Show',False),('/srv/media/CleanVid//TV/Show/',True)])
def test_path_boundaries(client,path,expected):
    assert selection.matches({'path':path},config())==expected


def test_rule_defaults_and_validation(client):
    assert not store.settings()['cleanvid_enabled']
    for value in ['/', '../CleanVid', '/mnt/../TV']:
        assert client.put('/api/settings',json={'cleanvid_roots':value}).status_code==400
    assert client.put('/api/settings',json={'cleanvid_enabled':True,'cleanvid_roots':''}).status_code==400
    assert client.put('/api/settings',json={'cleanvid_enabled':True,'cleanvid_roots':'/srv/media/CleanVid\n/other/CleanVid/'}).status_code==200


def test_automatic_selection_and_persistent_optout(client):
    store.save_settings(config())
    item={'id':1,'title':'Show','path':'/srv/media/CleanVid/TV/Show'}
    with patch.object(service.Arr,'library',return_value=[item]),patch.object(service.Arr,'request',return_value=item):
        assert client.get('/api/library/sonarr').json()[0]['monitoring_source']=='cleanvid'
        assert client.put('/api/library/sonarr/1/monitor',json={'enabled':False}).status_code==200
        assert not client.get('/api/library/sonarr').json()[0]['selected']
        store.init()
        assert client.get('/api/library/sonarr').json()[0]['monitoring_source']=='excluded'
        assert client.put('/api/library/sonarr/1/monitor',json={'enabled':True}).status_code==200
        item['path']='/srv/media/TV/Show'
        assert client.get('/api/library/sonarr').json()[0]['monitoring_source']=='manual'


def test_dynamic_selection_removes_moved_titles_and_keeps_manual(client):
    store.save_settings(config())
    auto={'id':1,'title':'Automatic','path':'/srv/media/CleanVid/Movies/Automatic'}
    with store.db() as db:db.execute('INSERT INTO monitored VALUES (?,?,?)',('radarr',2,'Manual'))
    with patch.object(service.Arr,'library',return_value=[auto]),patch.object(service,'queue_item',return_value=1) as q:
        assert service.scan()==3 # manual movie + automatic TV/movie IDs kept distinct
        auto['path']='/srv/media/Movies/Automatic'
        q.reset_mock();assert service.scan()==1
        assert q.call_args.args[:2]==('radarr',2)
        store.save_settings({'cleanvid_enabled':False})
        assert service.scan()==1


def test_preview_never_queues_and_scan_deduplicates(client):
    store.save_settings(config())
    item={'id':1,'title':'Example','path':'/srv/media/CleanVid/TV/Example'}
    with store.db() as db:db.execute('INSERT INTO monitored VALUES (?,?,?)',('sonarr',1,'Example'))
    with patch.object(service.Arr,'library',return_value=[item]),patch.object(service,'queue_item',return_value=1) as q:
        result=client.get('/api/monitoring/preview').json()
        assert len(result['items'])==2 and not result['auto_process']
        q.assert_not_called();assert store.jobs()==[]
        assert service.scan()==2
        assert q.call_count==2


def test_manager_failure_does_not_block_manual_selection(client):
    store.save_settings(config())
    with store.db() as db:db.execute('INSERT INTO monitored VALUES (?,?,?)',('sonarr',7,'Manual'))
    with patch.object(service.Arr,'library',side_effect=ValueError('Unavailable')),patch.object(service,'queue_item',return_value=1):
        assert service.scan()==1
        assert len(client.get('/api/monitoring/preview').json()['errors'])==2
