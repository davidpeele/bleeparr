"""Speech failures must never masquerade as successful broad censorship."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
from cli import bleeparr as cli
from test_subtitles import ENGLISH, write_subs


@pytest.fixture
def speech(tmp_path, monkeypatch):
    args = cli.parser().parse_args(['--input', str(tmp_path/'original.mkv')])
    section = dict(start=10.0, end=12.0, expected=Counter({'damn': 1}))
    def extract(source, section, clip, *unused):
        clip.write_bytes(b'clip')
        return section['start'] - args.clip_context
    monkeypatch.setattr(cli, 'extract_clip', extract)
    def model(words):
        return SimpleNamespace(transcribe=Mock(return_value=(
            [SimpleNamespace(words=[SimpleNamespace(word=w, start=a, end=b) for w,a,b in words])], None)))
    return args, section, tmp_path, model


def refine(speech, sections=None):
    args, section, scratch, _ = speech
    return cli.refine(args, sections or [section], scratch, 1, 30, {'damn'})


def test_word_timing_uses_clip_offset_and_never_loads_medium_when_small_resolves(speech, monkeypatch):
    _, _, _, model = speech
    load = Mock(return_value=model([(' damn', 1.0, 1.3)]))
    monkeypatch.setattr(cli, 'load_speech_model', load)
    assert refine(speech) == [dict(start=10.5, end=10.8, word='damn', fallback=False)]
    assert [call.args[0] for call in load.call_args_list] == ['small.en']


def test_medium_handles_only_clips_unresolved_by_small(speech, monkeypatch):
    _, section, _, model = speech
    second = dict(start=20.0, end=22.0, expected=Counter({'damn': 1}))
    small = model([])
    small.transcribe.side_effect = [([SimpleNamespace(words=[SimpleNamespace(word='damn',start=1,end=1.3)])],None), ([],None)]
    medium = model([('damn', 1.0, 1.3)])
    load = Mock(side_effect=[small, medium]); monkeypatch.setattr(cli,'load_speech_model',load)
    hits = refine(speech, [section,second])
    assert len(hits)==2 and all(not h['fallback'] for h in hits)
    assert small.transcribe.call_count==2 and medium.transcribe.call_count==1
    assert medium.transcribe.call_args.args[0].endswith('clip_000001.wav')


@pytest.mark.parametrize('failure', [TypeError("open() got an unexpected keyword argument 'metadata_errors'"),
                                      cli.ProcessingError('speech_model_missing','Offline model missing')])
def test_broken_primary_can_recover_through_working_medium(speech, monkeypatch, failure):
    _, _, _, model = speech
    monkeypatch.setattr(cli,'load_speech_model',Mock(side_effect=[failure,model([('damn',1,1.3)])]))
    hits=refine(speech)
    assert len(hits)==1 and hits[0]['fallback'] is False


@pytest.mark.parametrize('failure_stage', ['load','lazy_transcription'])
def test_dependency_failure_blocks_full_subtitle_fallback(speech, monkeypatch, failure_stage):
    _, _, _, model = speech
    def broken_segments():
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
        yield  # Whisper returns a lazy generator; errors can occur during iteration.
    broken=model([])
    broken.transcribe.return_value=(broken_segments(),None)
    load=Mock(side_effect=[TypeError('decoder failed'),model([])]) if failure_stage=='load' else Mock(side_effect=[broken,model([])])
    monkeypatch.setattr(cli,'load_speech_model',load)
    with pytest.raises(cli.ProcessingError) as caught:refine(speech)
    assert caught.value.code=='speech_model'
    assert caught.value.details['unresolved_sections']==1
    assert caught.value.details['speech_model_errors']
    assert load.call_count==2


def test_successful_but_incomplete_speech_uses_fallback_only_after_both_models(speech, monkeypatch):
    _, section, _, model = speech
    section['expected']=Counter({'damn':2})
    load=Mock(side_effect=[model([('damn',1,1.3)]),model([('damn',1.1,1.4)])])
    monkeypatch.setattr(cli,'load_speech_model',load)
    assert refine(speech)==[dict(start=10,end=12,fallback=True)]
    assert load.call_count==2  # Hypotheses must not combine into a false two-word match.


def test_no_fallback_strategy_stops_on_unresolved_words(speech, monkeypatch):
    args, _, _, model=speech;args.bleeptool='S-M'
    monkeypatch.setattr(cli,'load_speech_model',Mock(side_effect=[model([]),model([])]))
    with pytest.raises(cli.ProcessingError) as caught:refine(speech)
    assert caught.value.code=='speech_unresolved'


def test_subtitle_only_mode_is_explicit_and_never_loads_speech(speech, monkeypatch):
    args, _, _, _=speech;args.bleeptool='FSM'
    load=Mock(side_effect=AssertionError('Speech must not run in explicit FSM mode'))
    monkeypatch.setattr(cli,'load_speech_model',load)
    assert refine(speech)==[dict(start=10,end=12,fallback=True)]
    load.assert_not_called()


def test_cli_model_failure_preserves_original_and_creates_no_cleaned_file(tmp_path, monkeypatch):
    video=tmp_path/'original.mkv';video.write_bytes(b'original media')
    words=tmp_path/'words.txt';words.write_text('damn')
    write_subs(video.with_suffix('.srt'), [(10,12)], 'damn '+ENGLISH)
    monkeypatch.setattr(cli,'probe',lambda _:({'streams':[dict(index=0,codec_type='video'),dict(index=1,codec_type='audio',tags={'language':'eng'})]},30))
    monkeypatch.setattr(cli,'load_speech_model',Mock(side_effect=TypeError('metadata_errors incompatibility')))
    render=Mock();monkeypatch.setattr(cli,'render',render)
    result=tmp_path/'result.json'
    assert cli.main(['--input',str(video),'--swears',str(words),'--result-json',str(result),'--delete-original','--no-download-subs'])==1
    assert json.loads(result.read_text())['error_code']=='speech_model'
    assert video.read_bytes()==b'original media'
    assert not cli.default_output(video,'(profanity removed)').exists()
    render.assert_not_called()


def test_installed_speech_decoder_accepts_wav_and_returns_float_audio(tmp_path):
    """Fails with the original PyAV 19 / Faster Whisper decoder incompatibility."""
    import wave
    decoder=pytest.importorskip('faster_whisper.audio',reason='Speech runtime is checked in the Linux application image')
    path=tmp_path/'speech.wav'
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b'\x00\x00'*16000)
    samples=decoder.decode_audio(str(path))
    assert samples.shape==(16000,)
    assert str(samples.dtype)=='float32'
    assert (samples==0).all()
