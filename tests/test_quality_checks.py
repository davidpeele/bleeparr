from collections import Counter
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from cli import bleeparr as cli, quality
from backend import store, service, output, speech_health
from test_app import client, job


@pytest.mark.parametrize('declared,expected,duration,holds',[
    ('PSArips.com | Ponyo.2008.DUAL-AUDIO.JAP-ENG.1080p',{'title':'Saturday Night','year':2024},6142,True),
    ('Saturday.Night.2024.1080p.BluRay.x264-OFT',{'title':'Saturday Night','year':2024,'runtime_seconds':6540},6545,False),
    ('The.Studio.2025.S01E02.1080p',{'title':'The Studio (2025)','season':1,'episode':1},2600,True),
    ('The.Studio.2025.S01E01E02.1080p',{'title':'The Studio','season':1,'episode':2},2600,False),
    ('The.Actor.2025.WEB',{'title':'The Actor','runtime_seconds':5880},9000,True),
    ('Le.Conformiste.1970',{'title':'The Conformist','year':1970,'aliases':['Le Conformiste']},6500,False),
    ('',{'title':'Example'},600,False),
])
def test_title_year_episode_runtime_and_alternate_names(declared,expected,duration,holds):
    data={'format':{'tags':{'title':declared}}}
    if holds:
        with pytest.raises(quality.QualityReview) as caught:quality.identity(data,duration,expected)
        assert caught.value.code=='title_review'
    else:
        report=quality.identity(data,duration,expected)
        assert report['status']==('passed' if declared else 'unavailable')


def test_shared_episode_file_identity_matches_the_queued_episode(client,monkeypatch):
    store.save_settings({'sonarr_url':'http://sonarr','sonarr_api_key':'test'})
    arr=service.Arr('sonarr')
    arr.request=Mock(side_effect=[{'title':'Example','year':2020},
        [{'id':11,'seasonNumber':1,'episodeNumber':1,'episodeFileId':7},
         {'id':12,'seasonNumber':1,'episodeNumber':2,'episodeFileId':7}],
        [{'id':7,'path':'/media/shared.mkv'}]])
    files=arr.files(1)
    assert len(files)==1 and files[0][0]==11 and files[0][2]['_identity']['episode']==1


def muting_setup(tmp_path):
    source=tmp_path/'input.mkv';source.write_bytes(b'original')
    subs=tmp_path/'input.srt';subs.write_text('matching English dialogue')
    args=cli.parser().parse_args(['--input',str(source),'--review-broad-muting'])
    sections=[dict(start=i*10,end=i*10+2,expected=Counter({'damn':1})) for i in range(4)]
    hits=[dict(start=s['start'],end=s['end'],fallback=True) for s in sections]
    return args,source,subs,sections,hits


def test_broad_muting_holds_and_approval_binds_source_subtitles_and_plan(tmp_path):
    args,source,subs,sections,hits=muting_setup(tmp_path)
    sig=output.signature(source)
    with pytest.raises(quality.QualityReview) as caught:quality.muting(args,hits,sections,600,subs,{'damn'},sig)
    assert caught.value.details['muting_review']['fallback_percent']==100
    args.muting_approval=caught.value.details['review_token']
    assert quality.muting(args,hits,sections,600,subs,{'damn'},sig)['approved']
    subs.write_text('different matching dialogue')
    with pytest.raises(quality.QualityReview):quality.muting(args,hits,sections,600,subs,{'damn'},sig)
    args.muting_approval=''
    for changes in [dict(max_fallback_percent=99),dict(pre_buffer=200)]:
        for k,v in changes.items():setattr(args,k,v)
        with pytest.raises(quality.QualityReview):quality.muting(args,hits,sections,600,subs,{'damn'},sig)


@pytest.mark.parametrize('hits,seconds',[
    ([dict(start=10,end=50,fallback=False,word='phrase')],600),
    ([dict(start=10,end=22,fallback=True)],600)
])
def test_long_or_large_mutes_also_require_review(tmp_path,hits,seconds):
    args,source,subs,sections,_=muting_setup(tmp_path)
    with pytest.raises(quality.QualityReview):quality.muting(args,hits,sections,seconds,subs,{'damn'},output.signature(source))


def test_word_mutes_with_small_fallback_share_do_not_hold(tmp_path):
    args,source,subs,sections,hits=muting_setup(tmp_path)
    hits=[dict(start=s['start'],end=s['start']+.2,fallback=False,word='damn') for s in sections]
    assert not quality.muting(args,hits,sections,600,subs,{'damn'},output.signature(source))['reasons']


def timing_setup(tmp_path,shift=0):
    args=cli.parser().parse_args(['--input',str(tmp_path/'movie.mkv')])
    subtitles=[SimpleNamespace(start=timedelta(seconds=50+i*100),end=timedelta(seconds=54+i*100),
                  content='Bright orange bicycles cross quiet roads') for i in range(6)]
    def extract(source,section,dest,audio,boost,context,duration):
        dest.write_bytes(b'audio');return section['start']-context
    def model(name,args):
        words=[SimpleNamespace(word=w,start=2+shift+i*.2,end=2+shift+i*.2+.15)
               for i,w in enumerate('Bright orange bicycles cross quiet roads'.split())]
        return SimpleNamespace(transcribe=Mock(return_value=([SimpleNamespace(words=words)],None)))
    return args,subtitles,extract,model


def test_matching_dialogue_passes_timing_without_loading_medium(tmp_path):
    args,subs,extract,model=timing_setup(tmp_path)
    load=Mock(side_effect=model)
    result=quality.alignment(args,subs,tmp_path,1,700,cli.subtitle_text,cli.tokens,load,extract)
    assert result['status']=='passed' and result['confirmed_samples']==6 and load.call_count==1


def test_shifted_speech_and_mismatched_text_hold_for_review(tmp_path):
    args,subs,extract,model=timing_setup(tmp_path,shift=20)
    with pytest.raises(quality.QualityReview) as caught:
        quality.alignment(args,subs,tmp_path,1,700,cli.subtitle_text,cli.tokens,model,extract)
    assert caught.value.code=='subtitle_alignment_review'
    assert caught.value.details['subtitle_alignment']['confirmed_samples']==0


def test_timing_model_error_cannot_turn_into_subtitle_fallback(tmp_path):
    args,subs,extract,_=timing_setup(tmp_path)
    with pytest.raises(quality.QualityReview) as caught:
        quality.alignment(args,subs,tmp_path,1,700,cli.subtitle_text,cli.tokens,Mock(side_effect=TypeError('decoder failed')),extract)
    assert caught.value.code=='speech_model'


def test_review_is_terminal_and_approval_cannot_bypass_another_review(client,tmp_path):
    source=tmp_path/'media';source.mkdir();source=source/'input.mkv';source.write_bytes(b'original')
    store.enqueue({**job(),'path':str(source)})
    claimed=store.claim(3);token='a'*64
    result=dict(success=False,error_code='muting_review',review_token=token,review_source_signature=output.signature(source))
    assert store.finish(claimed,result,store.settings())=='review'
    assert store.claim(3) is None
    assert client.post(f"/api/jobs/{claimed['id']}/approve-muting",json={'token':'b'*64}).status_code==409
    assert client.post(f"/api/jobs/{claimed['id']}/approve-muting",json={'token':token}).status_code==200
    retry=store.claim(3);assert json.loads(retry['result'])['approved_review_token']==token
    store.finish(retry,{**result,'error_code':'subtitle_alignment_review'},store.settings())
    assert client.post(f"/api/jobs/{claimed['id']}/approve-muting",json={'token':token}).status_code==409


def test_review_approval_rejects_changed_original(client,tmp_path):
    source=tmp_path/'input.mkv';source.write_bytes(b'original');store.enqueue({**job(),'path':str(source)})
    claimed=store.claim(3);token='a'*64
    store.finish(claimed,dict(success=False,error_code='muting_review',review_token=token,
                             review_source_signature=output.signature(source)),store.settings())
    source.write_bytes(b'changed original')
    assert client.post(f"/api/jobs/{claimed['id']}/approve-muting",json={'token':token}).status_code==409


def test_readiness_remains_offline_checks_lazy_decoder_and_deduplicates_models(client,monkeypatch):
    store.save_settings({'model':'small.en','fallback_model':'small.en'})
    load=Mock(return_value=SimpleNamespace(transcribe=Mock(return_value=(iter([]),None))))
    monkeypatch.setattr(cli,'load_speech_model',load)
    assert speech_health.run_check()['status']=='passed' and load.call_count==1
    def bad():
        raise TypeError('metadata_errors')
        yield
    load.return_value.transcribe.return_value=(bad(),None)
    assert speech_health.run_check()['status']=='failed'


def test_readiness_does_not_compete_with_media_worker(client):
    with service.INFERENCE_LOCK:
        assert client.post('/api/speech-readiness').status_code==400
        assert not service.process_next_job(store.settings())
    result=client.get('/api/speech-readiness').json()
    assert result['latest']['status']=='not_checked'


def test_new_settings_validated_and_retention_off_by_default(client):
    config=client.get('/api/settings').json()
    assert config['retain_originals'] is False and config['check_subtitle_timing'] and config['review_broad_muting']
    for settings in [{'max_muted_percent':101},{'max_fallback_seconds':0},{'original_storage_gb':0},{'original_retention_days':91}]:
        assert client.put('/api/settings',json=settings).status_code==422


@pytest.mark.parametrize('text,rules,expected',[
    ('Damn, that damn damning thing!', {'damn'}, '****, that **** damning thing!'),
    ('You son of a bitch!', {'son of a bitch'}, 'You ****!'),
    ('That’s bloody hell.', {'bloody', 'bloody hell'}, 'That’s ****.'),
    ("Don't do it. DON’T!", {"don't"}, '**** do it. ****!'),
])
def test_mute_dialogue_masks_complete_words_and_overlapping_phrases(text,rules,expected):
    assert cli.masked_dialogue(text,rules)==expected


def test_review_and_log_include_masked_subtitle_dialogue(tmp_path,capsys):
    args,source,subs,_,_=muting_setup(tmp_path)
    subtitles=[SimpleNamespace(start=timedelta(seconds=i*10), end=timedelta(seconds=i*10+2),
                               content='<i>Damn!</i> Where are you?') for i in range(4)]
    sections=cli.matching_sections(subtitles,{'damn'},600)
    hits=[dict(start=s['start'],end=s['end'],fallback=True) for s in sections]
    with pytest.raises(quality.QualityReview) as caught:
        quality.muting(args,hits,sections,600,subs,{'damn'},output.signature(source))
    cues=caught.value.details['muting_review']['fallback_dialogue']
    assert len(cues)==4
    assert cues[0]==dict(start=0,end=2,dialogue='****! Where are you?')
    log=capsys.readouterr().out
    assert '0.00–2.00s | ****! Where are you?' in log
    assert 'Damn' not in log
