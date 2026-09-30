from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import srt
import pytest
from cli import bleeparr as cli

ENGLISH = ('We should leave the house early tomorrow and meet everyone at the station. '
           'Please bring your bag and make sure the children know where we are going. '
           'I think there is enough time for breakfast before we start walking along the river. '
           'Our friends are waiting for us and would like to visit the museum after lunch. '
           'When we arrive we can decide whether to stay for the evening or take the next train home. '
           'It should be a pleasant trip if we all remember to stay together and keep an eye on the time.')
FRENCH = ('Nous devons quitter la maison demain matin pour retrouver nos amis à la gare. '
          'Les enfants veulent visiter le musée et se promener dans le jardin. '
          'Je pense que nous avons assez de temps pour prendre le petit déjeuner avant de partir. '
          'Il faut vérifier que tout le monde a son billet et connaît le chemin. '
          'Quand nous arriverons nous pourrons choisir un restaurant pour déjeuner ensemble. ')*3
SELECTION = dict(subtitle_source='sidecar', subtitle_declared_language='eng', subtitle_stream_index=None)


def write_subs(path, intervals, text=ENGLISH):
    subs = [srt.Subtitle(i+1, timedelta(seconds=a), timedelta(seconds=b), text) for i,(a,b) in enumerate(intervals)]
    path.write_text(srt.compose(subs), encoding='utf-8')
    return subs


def test_language_checks_actual_text_despite_english_label(tmp_path):
    path = tmp_path/'movie.en.srt'
    write_subs(path, [(1, 10)], FRENCH)
    with pytest.raises(cli.ProcessingError) as caught:
        cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    assert caught.value.code == 'subtitle_language_mismatch'
    assert caught.value.details['subtitle_language'] == 'fr'
    assert caught.value.details['subtitle_file'] == 'movie.en.srt'
    json.dumps(caught.value.details)


def test_english_and_insufficient_or_uncertain_language(tmp_path):
    path = tmp_path/'movie.srt'
    write_subs(path, [(1, 10)])
    _, report = cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    assert report['subtitle_language'] == 'en'
    with patch('langid.langid.LanguageIdentifier.classify', return_value=('en', 0.5)):
        with pytest.raises(cli.ProcessingError, match='confidently'):
            cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    write_subs(path, [(1, 10)], 'Hello there.')
    with pytest.raises(cli.ProcessingError) as caught:
        cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    assert caught.value.code == 'subtitle_language_uncertain'


def test_foreign_ending_is_not_hidden_by_english_intro(tmp_path):
    path = tmp_path/'mixed.en.srt'
    write_subs(path, [(1, 10)], ENGLISH*35 + FRENCH*20)
    with pytest.raises(cli.ProcessingError) as caught:
        cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    assert caught.value.code == 'subtitle_language_mismatch'
    assert len(caught.value.details['subtitle_language_samples']) == 3


def test_coverage_tolerates_credits_and_short_silences(tmp_path):
    subs = write_subs(tmp_path/'full.srt', [(i, i+5) for i in range(60, 1620, 10)])
    report = cli.subtitle_coverage(subs, 1800)
    assert report['warnings'] == []
    assert report['largest_gap_seconds'] == 5


@pytest.mark.parametrize('times,reason', [
    ([(10, 20), (1000, 1010)], 'sparse'),
    ([(i,i+5) for i in range(500,1700,10)], 'opening'),
    ([(i,i+5) for i in range(10,700,10)], 'ending'),
    ([(i,i+5) for i in list(range(10,400,10))+list(range(1100,1700,10))], 'gap'),
])
def test_coverage_flags_suspicious_programs(tmp_path, times, reason):
    path = tmp_path/'partial.srt'
    write_subs(path, times)
    with pytest.raises(cli.ProcessingError) as caught:
        cli.inspect_subtitles(path, 'eng', 1800, SELECTION)
    assert caught.value.code == 'subtitle_coverage_suspect'
    assert reason in ' '.join(caught.value.details['subtitle_coverage']['warnings'])


def test_overlap_union_does_not_inflate_coverage_or_flag_contiguous_cues(tmp_path):
    path = tmp_path/'overlap.srt'
    subs = write_subs(path, [(i,i+20) for i in range(10,1700,10)])
    report = cli.subtitle_coverage(subs, 1800)
    assert report['dialogue_seconds'] == 1700
    assert report['warnings'] == []
    subs = write_subs(path, [(1,2)]*100)
    assert cli.subtitle_coverage(subs,1800)['dialogue_seconds'] == 1
    assert cli.subtitle_coverage(subs,1800)['warnings']


def test_invalid_timing_stops_before_language_detection(tmp_path):
    path = tmp_path/'bad.srt'
    write_subs(path, [(1, 30)])
    with pytest.raises(cli.ProcessingError) as caught:
        cli.inspect_subtitles(path, 'eng', 20, SELECTION)
    assert caught.value.code == 'invalid_subtitles'


def test_counts_preserve_repeated_words_and_multiword_phrases(tmp_path):
    path = tmp_path/'repeat.srt'
    write_subs(path, [(1,2)], 'fuck fucking fucking eat my shorts')
    sections = cli.parse_subtitles(path, {'fuck','fucking','eat my shorts'}, 3)
    assert cli.match_counts(sections) == {'matched_occurrences':4, 'matched_word_count':6}


def test_embedded_selection_reports_absolute_stream_and_skips_foreign_forced(tmp_path):
    args = SimpleNamespace(subtitle=None, input=str(tmp_path/'movie.mkv'), subtitle_lang='en',
                           dry_run=False, no_embedded_subs=False, no_download_subs=True)
    streams = [dict(index=i, codec_type='subtitle', codec_name='subrip', tags=dict(language=lang, title='Dialogue'), disposition=dict(forced=forced))
               for i,lang,forced in [(2,'fre',0),(3,'eng',1),(4,'eng',0)]]
    def extract(command):
        assert command[command.index('-map')+1] == '0:4'
        Path(command[-1]).write_text('extracted')
    with patch.object(cli,'run',side_effect=extract):
        path, report = cli.resolve_subtitle(args, {'streams':streams}, tmp_path)
    assert path.name == 'embedded.srt'
    assert report['subtitle_stream_index'] == 4
    assert report['subtitle_track_title'] == 'Dialogue'
    assert report['subtitle_declared_language'] == 'eng'


def test_coverage_failure_keeps_original_and_writes_review_details(tmp_path):
    video = tmp_path/'movie.mkv'; video.write_bytes(b'original')
    subs = tmp_path/'movie.srt'; write_subs(subs,[(10,20),(1000,1010)])
    words = tmp_path/'words.txt'; words.write_text('damn')
    result_path = tmp_path/'result.json'
    data = dict(streams=[dict(index=0,codec_type='video'),dict(index=1,codec_type='audio')])
    with patch.object(cli,'probe',return_value=(data,1800)), patch.object(cli,'render') as render:
        assert cli.main(['--input',str(video),'--swears',str(words),'--result-json',str(result_path),'--no-download-subs']) == 1
        render.assert_not_called()
    result=json.loads(result_path.read_text())
    assert result['error_code']=='subtitle_coverage_suspect'
    assert result['subtitle_coverage']['warnings']
    assert video.read_bytes()==b'original'
    assert list(tmp_path.glob('*profanity removed*.mkv'))==[]


def test_dry_run_applies_the_same_language_and_coverage_checks(tmp_path):
    video=tmp_path/'movie.mkv'; video.write_bytes(b'original')
    write_subs(tmp_path/'movie.srt',[(10,20),(1000,1010)])
    words=tmp_path/'words.txt'; words.write_text('damn')
    args=cli.parser().parse_args(['--input',str(video),'--swears',str(words),'--dry-run'])
    with patch.object(cli,'probe',return_value=({'streams':[dict(index=0,codec_type='video'),dict(index=1,codec_type='audio')]},1800)):
        with pytest.raises(cli.ProcessingError) as caught:cli.process(args)
    assert caught.value.code=='subtitle_coverage_suspect'


def test_formatting_tags_are_not_counted_as_dialogue():
    sub=srt.Subtitle(1,timedelta(0),timedelta(seconds=1),r'{\an8}<i>Hello there.</i>')
    assert cli.tokens(cli.subtitle_text(sub))==['hello','there']


def test_overlapping_rules_count_each_subtitle_word_once(tmp_path):
    path=tmp_path/'overlap.srt'
    write_subs(path,[(1,2)],'eat my shorts')
    sections=cli.parse_subtitles(path,{'shorts','eat my shorts'},3)
    assert cli.match_counts(sections)=={'matched_occurrences':2,'matched_word_count':3}
