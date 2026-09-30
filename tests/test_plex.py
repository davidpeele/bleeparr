import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from test_app import client, job
from backend import plex, store


class Item:
    def __init__(self, key, paths, summary='Original synopsis', parent=None):
        self.ratingKey = key
        self.summary = summary
        self.media = [SimpleNamespace(parts=[SimpleNamespace(file=path)]) for path in paths]
        self.parent = parent
        self.grandparentRatingKey = parent.ratingKey if parent else None
        self.edits = []
    def reload(self): pass
    def editSummary(self, summary):
        self.edits.append(summary)
        self.summary = summary
    def show(self): return self.parent


@pytest.fixture
def setup(client, tmp_path, monkeypatch):
    output = tmp_path / 'output'; output.mkdir()
    path = output / 'clean.mkv'; path.write_bytes(b'clean')
    monkeypatch.setenv('OUTPUT_DIR',str(output))
    store.enqueue(job())
    claimed = store.claim(3)
    store.finish(claimed, {'success':True,'output_path':str(path)},store.settings())
    config = {**store.settings(), 'plex_enabled':True,'plex_url':'http://plex:32400','plex_token':'private-token',
              'plex_libraries':[1], 'plex_path_from':str(output),'plex_path_to':'/plex/cleaned'}
    server = SimpleNamespace(machineIdentifier='server1',library=SimpleNamespace(sectionByID=Mock()))
    monkeypatch.setattr(plex,'connect',lambda c: server)
    return config,server,claimed,path


def section(server, items, kind='movie'):
    server.library.sectionByID.return_value = SimpleNamespace(type=kind,all=lambda:items,search=lambda **kw:items)


def test_movie_preserves_summary_and_avoids_duplicate_note(setup):
    config,server,claimed,path = setup
    movie=Item('10',['/plex/cleaned/clean.mkv'])
    section(server,[movie])
    assert plex.sync(config)['updated'] == 1
    assert movie.summary == '(Profanity removed by AI) Original synopsis'
    assert plex.sync(config,manual=True)['updated'] == 0
    assert len(movie.edits) == 1
    with store.db() as db:
        assert db.execute('SELECT status FROM plex_updates').fetchone()[0] == 'done'


def test_series_note_is_optional_and_does_not_claim_every_episode_clean(setup):
    config,server,_,_ = setup
    show=Item('20',[], 'Series story')
    ep=Item('21',['/plex/cleaned/clean.mkv'],parent=show)
    section(server,[ep],'show')
    assert plex.sync(config)['updated'] == 2
    assert show.summary == '(Includes episodes with profanity removed) Series story'


def test_series_note_can_be_disabled(setup):
    config,server,_,_ = setup
    show=Item('20',[], 'Series story'); ep=Item('21',['/plex/cleaned/clean.mkv'],parent=show)
    section(server,[ep],'show')
    plex.sync({**config,'plex_series_note_enabled':False})
    assert not show.edits and len(ep.edits) == 1


def test_does_not_label_original_or_mixed_versions(setup):
    config,server,_,_ = setup
    original=Item('10',['/tv/original.mkv'])
    mixed=Item('11',['/plex/cleaned/clean.mkv','/tv/original.mkv'])
    section(server,[original,mixed])
    assert plex.sync(config)['waiting'] == 1
    assert not original.edits and not mixed.edits


def test_waits_until_plex_indexes_output_and_manual_retry_works(setup):
    config,server,_,_ = setup
    section(server,[])
    assert plex.sync(config)['waiting'] == 1
    movie=Item('10',['/plex/cleaned/clean.mkv']); section(server,[movie])
    assert plex.sync(config)['updated'] == 0  # cooldown
    assert plex.sync(config,manual=True)['updated'] == 1


def test_disabling_never_contacts_plex(setup):
    config,server,_,_ = setup
    assert plex.sync({**config,'plex_enabled':False})['updated'] == 0
    server.library.sectionByID.assert_not_called()


def test_errors_are_separate_from_completed_media_and_redact_tokens(setup):
    config,server,_,_ = setup
    server.library.sectionByID.side_effect=RuntimeError('URL contains private-token')
    with pytest.raises(ValueError) as exc:
        plex.sync(config)
    assert 'private-token' not in str(exc.value)
    assert store.jobs()[0]['status'] == 'completed'
    with store.db() as db:
        assert 'private-token' not in db.execute('SELECT error FROM plex_updates').fetchone()[0]


def test_changed_note_replaces_only_previously_managed_prefix(setup):
    config,server,_,_ = setup
    movie=Item('10',['/plex/cleaned/clean.mkv']); section(server,[movie])
    plex.sync(config)
    plex.sync({**config,'plex_note':'(Cleaned with Bleeparr)'},manual=True)
    assert movie.summary == '(Cleaned with Bleeparr) Original synopsis'


def test_retry_budget_is_bounded(setup):
    config,server,claimed,_ = setup
    with store.db() as db:
        db.execute('INSERT INTO plex_updates VALUES (?,?,?,?,?)',(claimed['id'],12,0,'pending','not indexed'))
    assert plex.sync(config)['updated'] == 0
    server.library.sectionByID.assert_not_called()


def test_failed_and_dry_run_jobs_are_not_marked(setup):
    config,server,claimed,path = setup
    with store.db() as db:
        db.execute("UPDATE jobs SET status='failed'")
    assert plex.sync(config)['updated'] == 0
    with store.db() as db:
        db.execute("UPDATE jobs SET status='completed',result=?",(json.dumps({'success':True,'dry_run':True,'output_path':str(path)}),))
    assert plex.sync(config)['updated'] == 0
    server.library.sectionByID.assert_not_called()


def test_plex_token_hidden_preserved_and_enable_requires_setup(client):
    assert client.put('/api/settings',json={'plex_enabled':True}).status_code == 400
    assert client.put('/api/settings',json={'plex_url':'http://plex:32400','plex_token':'secret'}).status_code == 200
    result=client.get('/api/settings').json()
    assert result['plex_token'] == '' and result['plex_token_configured']
    assert client.put('/api/settings',json={'plex_token':''}).status_code == 200
    assert store.settings()['plex_token'] == 'secret'
    assert client.put('/api/settings',json={'plex_enabled':True,'plex_libraries':[1]}).status_code == 200
    assert client.put('/api/settings',json={'plex_note':'   '}).status_code == 400


def test_settings_migration_keeps_existing_values(client):
    store.save_settings({'plex_note':'custom','auto_process':True})
    store.init()
    assert store.settings()['plex_note'] == 'custom' and store.settings()['auto_process']
