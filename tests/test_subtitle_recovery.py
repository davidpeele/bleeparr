"""Subtitle recovery tests use synthetic dialogue and mocked provider/speech calls."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cli import bleeparr as cli, quality, subtitle_search
from test_subtitles import ENGLISH, FRENCH, write_subs
from test_app import client, job


def setup(tmp_path, *flags):
    video = tmp_path / 'Example.S01E03.mkv'
    video.write_bytes(b'original')
    args = cli.parser().parse_args(['--input', str(video), '--no-download-subs', *flags])
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    return args, scratch


def stream(index):
    return dict(index=index, codec_type='subtitle', codec_name='subrip',
                tags={'language': 'eng'}, disposition={})


def test_wrong_language_sidecar_recovers_with_embedded_track(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--check-subtitle-timing')
    sidecar = Path(args.input).with_suffix('.srt')
    write_subs(sidecar, [(1, 10)], FRENCH)
    monkeypatch.setattr(cli, 'run', lambda cmd: write_subs(Path(cmd[-1]), [(1, 10)]))
    alignment = Mock(return_value={'status': 'passed'})
    monkeypatch.setattr(quality, 'alignment', alignment)
    path, _, report = cli.select_subtitle(args, {'streams': [stream(4)]}, scratch, 1, 20)
    assert path.name == 'embedded-4.srt'
    assert [a['status'] for a in report['subtitle_attempts']] == ['rejected', 'accepted']
    assert report['subtitle_attempts'][0]['error_code'] == 'subtitle_language_mismatch'
    assert report['subtitle_alignment']['status'] == 'passed'
    assert sidecar.read_text().find('Nous') >= 0
    assert alignment.call_count == 1


def test_shifted_local_subtitles_try_next_track(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--check-subtitle-timing')
    write_subs(Path(args.input).with_suffix('.en.srt'), [(1, 10)])
    monkeypatch.setattr(cli, 'run', lambda cmd: write_subs(Path(cmd[-1]), [(1, 10)]))
    alignment = Mock(side_effect=[quality.QualityReview('subtitle_alignment_review', 'Wrong cut',
                                  {'subtitle_alignment': {'status': 'review'}}), {'status': 'passed'}])
    monkeypatch.setattr(quality, 'alignment', alignment)
    _, _, report = cli.select_subtitle(args, {'streams': [stream(4)]}, scratch, 1, 20)
    assert report['subtitle_source'] == 'embedded'
    assert report['subtitle_attempts'][0]['subtitle_alignment']['status'] == 'review'


def fake_search(command, timeout):
    destination = Path(command[command.index('--download-subtitle-candidates') + 3])
    destination.mkdir()
    entries = []
    for i in range(2):
        name = f'candidate-{i}.srt'
        write_subs(destination / name, [(1, 10)])
        entries.append(dict(file=name, subtitle_provider='example', subtitle_matches=['series', 'episode', 'season']))
    (destination / 'candidates.json').write_text(json.dumps(entries))


def test_online_alternative_must_pass_timing_even_when_guard_disabled(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--no-embedded-subs', '--temp-dir', str(tmp_path))
    args.no_download_subs = False
    monkeypatch.setattr(cli, 'run', fake_search)
    alignment = Mock(side_effect=[quality.QualityReview('subtitle_alignment_review', 'Wrong cut', {}), {'status': 'passed'}])
    monkeypatch.setattr(quality, 'alignment', alignment)
    path, _, report = cli.select_subtitle(args, {'streams': []}, scratch, 1, 20)
    assert alignment.call_count == 2
    assert report['subtitle_file'] == 'candidate-1.srt'
    assert report['subtitle_provider'] == 'example'
    assert report['subtitle_alignment']['status'] == 'passed'
    assert path == tmp_path / 'selected-subtitle.srt' and path.is_file()


def test_partial_downloads_survive_provider_timeout(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--no-embedded-subs')
    args.no_download_subs = False
    def timeout(command, limit):
        fake_search(command, limit)
        raise cli.ProcessingError('timeout', 'Provider stalled')
    monkeypatch.setattr(cli, 'run', timeout)
    monkeypatch.setattr(quality, 'alignment', Mock(return_value={'status': 'passed'}))
    _, _, report = cli.select_subtitle(args, {'streams': []}, scratch, 1, 20)
    assert report['subtitle_attempts'][0]['error_code'] == 'timeout'
    assert report['subtitle_source'] == 'downloaded'


def test_runtime_failure_stops_without_trying_another_candidate(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--check-subtitle-timing')
    write_subs(Path(args.input).with_suffix('.en.srt'), [(1, 10)])
    write_subs(Path(args.input).with_suffix('.srt'), [(1, 10)])
    alignment = Mock(side_effect=quality.QualityReview('speech_model', 'Decoder failed', {}))
    monkeypatch.setattr(quality, 'alignment', alignment)
    with pytest.raises(cli.ProcessingError) as caught:
        cli.select_subtitle(args, {'streams': []}, scratch, 1, 20)
    assert caught.value.code == 'speech_model' and alignment.call_count == 1


def test_explicit_subtitle_failure_is_not_silently_replaced(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path)
    args.subtitle = str(tmp_path / 'manual.srt')
    write_subs(Path(args.subtitle), [(1, 10)], FRENCH)
    write_subs(Path(args.input).with_suffix('.en.srt'), [(1, 10)])
    with pytest.raises(cli.ProcessingError) as caught:
        cli.select_subtitle(args, {'streams': []}, scratch, 1, 20)
    assert caught.value.code == 'subtitle_language_mismatch'
    assert len(caught.value.details['subtitle_attempts']) == 1


def test_dry_run_recovers_locally_without_network_or_speech(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path, '--dry-run', '--check-subtitle-timing')
    write_subs(Path(args.input).with_suffix('.en.srt'), [(1, 10)], FRENCH)
    write_subs(Path(args.input).with_suffix('.srt'), [(1, 10)])
    run = Mock(side_effect=AssertionError('Must stay offline'))
    monkeypatch.setattr(cli, 'run', run)
    monkeypatch.setattr(quality, 'alignment', run)
    _, _, report = cli.select_subtitle(args, {'streams': [stream(4)]}, None, 1, 20)
    assert report['subtitle_source'] == 'sidecar'
    assert run.call_count == 0


def test_exhaustion_reports_rejections_and_keeps_original(tmp_path, monkeypatch):
    args, scratch = setup(tmp_path)
    write_subs(Path(args.input).with_suffix('.en.srt'), [(1, 10)], FRENCH)
    write_subs(Path(args.input).with_suffix('.srt'), [(1, 10)], 'Hello')
    with pytest.raises(cli.ProcessingError) as caught:
        cli.select_subtitle(args, {'streams': []}, scratch, 1, 20)
    assert len(caught.value.details['subtitle_attempts']) == 2
    assert Path(args.input).read_bytes() == b'original'


def test_provider_identity_and_release_ranking():
    pytest.importorskip('subliminal')
    video = subtitle_search.search_video('Other.Name.S01E03.720p.WEB.mkv',
                                        {'title': 'Example', 'year': 2026, 'season': 1, 'episode': 3})
    assert video.series == 'Example' and video.episode == 3
    def sub(*matches):
        return SimpleNamespace(get_matches=lambda video: set(matches), foreign_only=False)
    identity = ['series', 'season', 'episode', 'year']
    close = subtitle_search.candidate_rank(sub(*identity), video)
    exact = subtitle_search.candidate_rank(sub(*identity, 'release_group', 'resolution'), video)
    assert exact[0] > close[0]
    assert subtitle_search.candidate_rank(sub('series', 'season', 'year'), video) is None
    assert subtitle_search.candidate_rank(sub('series', 'season', 'episode'), video) is None
    assert subtitle_search.candidate_rank(sub('hash'), video) is not None


def test_provider_downloads_are_ranked_deduplicated_and_bounded(tmp_path, monkeypatch):
    subliminal = pytest.importorskip('subliminal')
    from babelfish import Language
    from subliminal.core import ProviderPool
    video = subtitle_search.search_video('Example.S01E03.mkv', {})
    monkeypatch.setattr(subtitle_search, 'search_video', lambda *args: video)
    subtitles = [SimpleNamespace(provider_name='example', id=str(i), language=Language('eng'),
        text=ENGLISH, get_matches=lambda video: {'series', 'season', 'episode'}, foreign_only=False)
        for i in range(8)]
    monkeypatch.setattr(ProviderPool, 'list_subtitles', lambda *args: [subtitles[0], *subtitles])
    download = Mock(return_value=True)
    monkeypatch.setattr(ProviderPool, 'download_subtitle', download)
    monkeypatch.setattr(subliminal.region, 'configure', lambda *args: None)
    entries = subtitle_search.download_candidates('Example.S01E03.mkv', 'en', tmp_path)
    assert len(entries) == 5 and download.call_count == 5
    assert len({entry['subtitle_provider_id'] for entry in entries}) == 5
    assert json.loads((tmp_path / 'candidates.json').read_text()) == entries


def test_settings_and_worker_keep_discovery_identity_independent_of_title_guard(client, tmp_path, monkeypatch):
    from backend import service, store
    assert client.get('/api/settings').json()['download_subtitles'] is True
    assert client.put('/api/settings', json={'download_subtitles': False, 'verify_title': False}).status_code == 200
    assert store.settings()['download_subtitles'] is False
    video = tmp_path / 'media' / 'Example.mkv'
    video.parent.mkdir()
    video.write_bytes(b'original')
    monkeypatch.setenv('OUTPUT_DIR', str(tmp_path / 'cleaned'))
    identity = {'title': 'Example', 'season': 1, 'episode': 3, 'year': 2026}
    commands = []
    def launch(command, **kwargs):
        commands.append(command)
        Path(command[command.index('--result-json') + 1]).write_text(json.dumps(
            {'success': False, 'error_code': 'subtitle_missing'}))
        return SimpleNamespace(poll=lambda: 1, returncode=1)
    monkeypatch.setattr(service.subprocess, 'Popen', launch)
    result = service.run_job({**job(), 'id': 1, 'path': str(video), 'identity': identity}, store.settings())
    assert result['error_code'] == 'subtitle_missing'
    command = commands[0]
    assert '--no-download-subs' in command and '--expected-identity' not in command
    assert json.loads(command[command.index('--subtitle-identity') + 1]) == identity
