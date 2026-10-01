#!/usr/bin/env python3
"""Subtitle-guided censorship with transactional output and machine-readable results."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import errno
import gc
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProcessingError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def tokens(text):
    return re.findall(r"\w+(?:['’]\w+)*", text.lower().replace('’', "'"))


def phrase_matches(words, entries):
    """Match complete, consecutive words; phrase components are not separate rules."""
    for entry in sorted(entries):
        phrase = tokens(entry)
        if not phrase:
            continue
        for start in range(len(words) - len(phrase) + 1):
            if words[start:start + len(phrase)] == phrase:
                yield ' '.join(phrase), start, start + len(phrase)


def run(command, timeout=3600):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ProcessingError('dependency', f'Required executable missing: {command[0]}') from exc
    except subprocess.TimeoutExpired as exc:
        raise ProcessingError('timeout', f'{command[0]} exceeded {timeout} seconds') from exc
    if result.returncode:
        detail = result.stderr[-4000:]
        code = 'disk_full' if 'no space left' in detail.lower() else 'processing'
        if any(marker in detail.lower() for marker in ('permission denied', 'input/output error', 'read-only file system')):
            code = 'filesystem'
        corruption = ('invalid data found when processing input', 'invalid bitstream', 'exceeds containing master', 'invalid as first byte of an ebml', 'obu_forbidden_bit', 'error while decoding')
        if code == 'processing' and any(marker in detail.lower() for marker in corruption):
            code = 'invalid_media'
        raise ProcessingError(code, f'{command[0]} failed: {detail}')
    return result.stdout


def probe(path):
    try:
        data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], 60))
    except ProcessingError as exc:
        if exc.code == 'processing':
            raise ProcessingError('invalid_media', str(exc)) from exc
        raise
    duration = float(data.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ProcessingError('invalid_media', 'Media duration is missing or invalid')
    return data, duration


def select_audio(data, language, index=None):
    streams = [s for s in data['streams'] if s['codec_type'] == 'audio']
    if index is not None:
        streams = [s for s in streams if s['index'] == index]
    else:
        tagged = [s for s in streams if s.get('tags', {}).get('language', '').lower() in language_codes(language)]
        if tagged:
            streams = tagged
        else:
            streams = [s for s in streams if s.get('tags', {}).get('language', 'und').lower() in ('und', '')]
    if not streams:
        raise ProcessingError('audio_missing', 'No matching audio track; specify --audio-stream with its absolute stream index')
    streams.sort(key=lambda s: (-s.get('disposition', {}).get('default', 0), s['index']))
    return streams[0]['index']


def language_codes(language):
    normalized = canonical_language(language)
    aliases = {'eng': 'en', 'spa': 'es', 'fra': 'fr', 'fre': 'fr', 'deu': 'de', 'ger': 'de', 'ita': 'it', 'por': 'pt'}
    return {normalized, *(key for key, value in aliases.items() if value == normalized)}


def canonical_language(language):
    aliases = {'eng': 'en', 'spa': 'es', 'fra': 'fr', 'fre': 'fr', 'deu': 'de', 'ger': 'de', 'ita': 'it', 'por': 'pt'}
    return aliases.get(language.lower(), language.lower())


def load_swears(path):
    try:
        words = [line.strip().lower() for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    except OSError as exc:
        raise ProcessingError('configuration', f'Cannot read word list: {path}') from exc
    if not words or any(not tokens(w) for w in words):
        raise ProcessingError('configuration', 'Enter one word or phrase per line, with at least one entry containing words')
    return {' '.join(tokens(word)) for word in words}


def read_subtitles(path, duration):
    import srt
    try:
        subtitles = list(srt.parse(Path(path).read_text(encoding='utf-8-sig')))
    except (OSError, UnicodeError, srt.SRTParseError, ValueError) as exc:
        raise ProcessingError('invalid_subtitles', 'Subtitle file must be readable UTF-8 SRT') from exc
    if not subtitles:
        raise ProcessingError('invalid_subtitles', 'Subtitle file contains no cues')
    for sub in subtitles:
        start, end = sub.start.total_seconds(), sub.end.total_seconds()
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > duration + 2:
            raise ProcessingError('invalid_subtitles', f'Subtitle cue {sub.index} has invalid or out-of-range timing')
    return subtitles


def subtitle_text(sub):
    return re.sub(r'<[^>]+>|\{[^}]+\}', ' ', sub.content)


def masked_dialogue(text, swears):
    """Mask configured words and phrases using the processing match rules."""
    spans = list(re.finditer(r"\w+(?:['’]\w+)*", text))
    merged = []
    for start, end in sorted({(spans[first].start(), spans[after - 1].end())
                             for _, first, after in phrase_matches(tokens(text), swears)}):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in reversed(merged):
        text = text[:start] + '****' + text[end:]
    return ' '.join(text.split())


def matching_sections(subtitles, swears, duration):
    sections = []
    for sub in subtitles:
        matches = list(phrase_matches(tokens(subtitle_text(sub)), swears))
        expected = Counter(entry for entry, _, _ in matches)
        if expected:
            sections.append(dict(start=sub.start.total_seconds(), end=min(sub.end.total_seconds(), duration), expected=expected,
                                 dialogue=masked_dialogue(subtitle_text(sub), swears),
                                 matched_word_count=len({i for _, first, after in matches for i in range(first, after)})))
    return sections


def parse_subtitles(path, swears, duration):
    return matching_sections(read_subtitles(path, duration), swears, duration)


def subtitle_coverage(subtitles, duration):
    # Union intervals so overlapping/duplicate cues cannot inflate coverage.
    ranges = intervals([dict(start=s.start.total_seconds(), end=s.end.total_seconds())
                        for s in subtitles if tokens(subtitle_text(s))], 0, 0, duration)
    words = sum(len(tokens(subtitle_text(s))) for s in subtitles)
    first, last = (ranges[0][0], ranges[-1][1]) if ranges else (0, 0)
    gap = max((b[0] - a[1] for a, b in zip(ranges, ranges[1:])), default=0)
    occupied = sum(end - start for start, end in ranges)
    reasons = []
    if duration >= 600:
        if sum(bool(tokens(subtitle_text(s))) for s in subtitles) / (duration / 60) < 0.5 or words / (duration / 60) < 8 or occupied / duration < 0.05:
            reasons.append('Very sparse dialogue subtitles for the media duration.')
        if first > max(180, duration * 0.10):
            reasons.append('A large opening portion has no subtitle dialogue.')
        if duration - last > max(300, duration * 0.15):
            reasons.append('A large ending portion has no subtitle dialogue.')
        if gap > max(300, duration * 0.15):
            reasons.append('A large gap inside the program has no subtitle dialogue.')
    return dict(duration_seconds=round(duration, 2), first_cue_seconds=round(first, 2),
                last_cue_seconds=round(last, 2), largest_gap_seconds=round(gap, 2),
                dialogue_seconds=round(occupied, 2), dialogue_ratio=round(occupied / duration, 3),
                words_per_minute=round(words / (duration / 60), 2), warnings=reasons)


def language_samples(text):
    # Examine the beginning, middle and ending; an English introduction must not
    # conceal a foreign-language remainder. The bundled model needs no network.
    if len(text) <= 6000:
        return [text]
    width = min(20000, len(text) // 3)
    return [text[:width], text[(len(text)-width)//2:(len(text)+width)//2], text[-width:]]


def inspect_subtitles(path, expected, duration, selection):
    report = dict(subtitle_file=Path(path).name, subtitle_path=str(path), **selection, subtitle_requested_language=expected)
    try:
        subtitles = read_subtitles(path, duration)
    except ProcessingError as exc:
        exc.details.update(report)
        raise
    text = ' '.join(subtitle_text(sub) for sub in subtitles)
    words = tokens(text)
    coverage = subtitle_coverage(subtitles, duration)
    report.update(subtitle_cues=len(subtitles), subtitle_words=len(words), subtitle_coverage=coverage)
    if len(words) < 80:
        raise ProcessingError('subtitle_language_uncertain', 'Too little subtitle text to verify its language; review the selected subtitle.', report)
    try:
        from langid.langid import LanguageIdentifier, model
    except ImportError as exc:
        raise ProcessingError('dependency', 'Install the bundled language detector dependencies before processing.', report) from exc
    identifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    samples = [identifier.classify(sample) for sample in language_samples(text)]
    report['subtitle_language_samples'] = [dict(language=lang, confidence=round(float(score), 3)) for lang, score in samples]
    report['subtitle_language'] = ', '.join(sorted({lang for lang, _ in samples}))
    report['subtitle_language_confidence'] = round(float(min(score for _, score in samples)), 3)
    wanted = canonical_language(expected)
    if any(lang != wanted and score >= 0.8 for lang, score in samples):
        raise ProcessingError('subtitle_language_mismatch', f'Subtitle text includes a likely language mismatch; expected {wanted}, detected {report["subtitle_language"]}.', report)
    if any(lang != wanted or score < 0.8 for lang, score in samples):
        raise ProcessingError('subtitle_language_uncertain', 'Subtitle language could not be verified confidently; review the selected subtitle.', report)
    if coverage['warnings']:
        raise ProcessingError('subtitle_coverage_suspect', 'Subtitle coverage needs review: ' + ' '.join(coverage['warnings']), report)
    return subtitles, report


def declared_language(path):
    parts = Path(path).name.lower().split('.')[:-1]
    for part in reversed(parts):
        if part in {'en', 'eng', 'es', 'spa', 'fr', 'fra', 'fre', 'de', 'deu', 'ger', 'it', 'ita', 'pt', 'por'}:
            return part
    return 'und'


def subtitle_candidates(args, data, scratch, search_events):
    if args.subtitle:
        path = Path(args.subtitle)
        if not path.is_file():
            raise ProcessingError('invalid_subtitles', 'Specified subtitle does not exist')
        yield path, dict(subtitle_source='explicit', subtitle_declared_language=declared_language(path), subtitle_stream_index=None)
        return
    base = Path(args.input).with_suffix('')
    candidates = [Path(str(base) + f'.{lang}{suffix}.srt')
                  for suffix in ('', '.hi', '.sdh') for lang in sorted(language_codes(args.subtitle_lang))]
    candidates += [Path(str(base) + '.srt'), Path(str(base) + '.hi.srt')]
    for path in candidates:
        if path.is_file() and path.stat().st_size:
            yield path, dict(subtitle_source='sidecar', subtitle_declared_language=declared_language(path), subtitle_stream_index=None)
    if args.dry_run:
        return  # Extraction, downloads and speech are disabled in dry runs.
    if not args.no_embedded_subs:
        streams = [s for s in data['streams'] if s['codec_type'] == 'subtitle'
                   and s.get('codec_name') in {'subrip', 'ass', 'ssa', 'mov_text', 'webvtt'}
                   and s.get('tags', {}).get('language', '').lower() in language_codes(args.subtitle_lang)
                   and not s.get('disposition', {}).get('forced', 0)]
        for stream in sorted(streams, key=lambda s: (-s.get('disposition', {}).get('default', 0), s['index'])):
            dest = scratch / f"embedded-{stream['index']}.srt"
            try:
                run(['ffmpeg', '-v', 'error', '-y', '-i', args.input, '-map', f"0:{stream['index']}", '-c:s', 'srt', str(dest)])
                if dest.stat().st_size:
                    yield dest, dict(subtitle_source='embedded', subtitle_declared_language=stream.get('tags', {}).get('language', 'und').lower(), subtitle_stream_index=stream['index'], subtitle_track_title=stream.get('tags', {}).get('title', ''))
            except ProcessingError as exc:
                if exc.code != 'processing':
                    raise
    if not args.no_download_subs:
        # One bounded subprocess searches and downloads ranked alternatives.
        destination = scratch / 'subtitle-search'
        identity = getattr(args, 'subtitle_identity', None) or getattr(args, 'expected_identity', None) or '{}'
        try:
            run([sys.executable, str(Path(__file__).resolve()), '--download-subtitle-candidates',
                 args.input, args.subtitle_lang, str(destination), identity], args.subtitle_timeout)
        except ProcessingError as exc:
            if exc.code not in {'processing', 'timeout'}:
                raise
            search_events.append(dict(subtitle_source='provider_search', status='failed',
                                      error_code=exc.code, error='Subtitle provider search failed or timed out.'))
            print(f'Subtitle search failed ({exc.code})', file=sys.stderr)
        manifest = destination / 'candidates.json'
        if manifest.is_file():
            entries = json.loads(manifest.read_text(encoding='utf-8'))
            for entry in entries[:5]:
                # Only our numbered files may be read; provider text is untrusted.
                name = entry.pop('file')
                if not re.fullmatch(r'candidate-\d+\.srt', name):
                    continue
                path = destination / name
                if path.is_file() and path.stat().st_size:
                    yield path, dict(subtitle_source='downloaded', subtitle_declared_language=args.subtitle_lang,
                                     subtitle_stream_index=None, **entry)


def resolve_subtitle(args, data, scratch):
    """Compatibility helper; processing uses validation-aware selection below."""
    for candidate in subtitle_candidates(args, data, scratch, []):
        return candidate
    raise ProcessingError('subtitle_missing', 'No matching full text subtitles found; image subtitles require OCR or an external SRT')


def select_subtitle(args, data, scratch, audio, duration):
    from cli import quality
    attempts = []
    rejected = None
    recoverable = {'invalid_subtitles', 'subtitle_language_mismatch', 'subtitle_language_uncertain',
                   'subtitle_coverage_suspect', 'subtitle_alignment_review'}
    for path, selection in subtitle_candidates(args, data, scratch, attempts):
        report = {}
        try:
            subtitles, report = inspect_subtitles(path, args.subtitle_lang, duration, selection)
            # Downloaded releases always need independent evidence of a matching
            # cut, even if the user disabled timing checks for local subtitles.
            if not args.dry_run and (args.check_subtitle_timing or selection['subtitle_source'] == 'downloaded'):
                try:
                    report['subtitle_alignment'] = quality.alignment(args, subtitles, scratch, audio, duration,
                        subtitle_text, tokens, load_speech_model, extract_clip)
                except quality.QualityReview as exc:
                    raise ProcessingError(exc.code, str(exc), {**report, **exc.details}) from exc
        except ProcessingError as exc:
            attempt = dict(**selection, subtitle_file=path.name, status='rejected',
                           error_code=exc.code, error=str(exc))
            if exc.details.get('subtitle_alignment'):
                attempt['subtitle_alignment'] = exc.details['subtitle_alignment']
            attempts.append(attempt)
            exc.details['subtitle_attempts'] = list(attempts)
            if exc.code not in recoverable or args.subtitle:
                raise
            rejected = exc
            print(f"Rejected subtitle {path.name}: {exc.code}; trying another candidate", flush=True)
            continue
        attempts.append(dict(**selection, subtitle_file=path.name, status='accepted'))
        report['subtitle_attempts'] = list(attempts)
        # Preserve extracted/downloaded subtitles for the app's retention layer,
        # which runs after the CLI has removed its scratch directory.
        if not args.dry_run and args.temp_dir and selection['subtitle_source'] in {'embedded', 'downloaded'}:
            saved = Path(args.temp_dir) / 'selected-subtitle.srt'
            shutil.copy2(path, saved)
            report['subtitle_path'] = str(saved)
            path = saved
        return path, subtitles, report
    if rejected:
        rejected.details['subtitle_attempts'] = list(attempts)
        raise rejected
    raise ProcessingError('subtitle_missing', 'No suitable full text subtitles found; add a matching SRT or check subtitle providers.',
                          {'subtitle_attempts': attempts})


def download_subtitle(video, language, destination):
    from subliminal import Video, download_best_subtitles, region
    from babelfish import Language
    region.configure('dogpile.cache.memory')
    media = Video.fromname(video)
    found = download_best_subtitles([media], {Language(language)})
    for subtitle in found.get(media, []):
        if subtitle.text:
            Path(destination).write_text(subtitle.text, encoding='utf-8')
            return
    raise ProcessingError('subtitle_missing', 'Subtitle providers returned no matches')


def extract_clip(source, section, target, audio, boost, context, duration):
    start = max(0, section['start'] - context)
    end = min(duration, section['end'] + context)
    run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-xerror', '-ss', str(start), '-i', str(source),
         '-t', str(end - start), '-map', f'0:{audio}', '-vn', '-ac', '1', '-ar', '16000',
         '-af', f'volume={boost}dB', '-c:a', 'pcm_s16le', str(target)])
    return start


def transcribe(model, clip, section, offset, swears):
    segments, _ = model.transcribe(str(clip), beam_size=5, word_timestamps=True, condition_on_previous_text=False)
    hits = []
    timed_words = []
    for segment in segments:
        for word in segment.words or []:
            for normalized in tokens(word.word):
                timed_words.append((normalized, offset + word.start, offset + word.end))
    for entry, first, after in phrase_matches([word[0] for word in timed_words], swears):
        matched = timed_words[first:after]
        if any(not math.isfinite(start) or not math.isfinite(end) or end <= start for _, start, end in matched):
            continue
        start, end = matched[0][1], matched[-1][2]
        if end > start and start < section['end'] and end > section['start']:
            hits.append(dict(start=max(section['start'], start), end=min(section['end'], end), word=entry, fallback=False))
    return hits


def complete(hits, expected):
    heard = Counter(h['word'] for h in hits)
    return all(heard[word] >= count for word, count in expected.items())


def load_speech_model(name, args):
    # Set before importing the Hub library; recognition never downloads models.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    try:
        folder = Path(name) if Path(name).is_dir() else Path(download_model(name, local_files_only=True))
        required = ['config.json', 'model.bin', 'tokenizer.json']
        if any(not (folder / filename).is_file() for filename in required) or not list(folder.glob('vocabulary.*')):
            raise ValueError('The local model is incomplete')
    except (OSError, ValueError) as exc:
        raise ProcessingError('speech_model_missing', f'Local speech model {name} is missing or incomplete. Download it into the model cache during setup; recognition runs offline and will not download it automatically.') from exc
    return WhisperModel(str(folder), device=args.device, compute_type=args.compute_type,
                        cpu_threads=args.cpu_threads, local_files_only=True)


def refine(args, sections, scratch, audio, duration, swears):
    passes = args.bleeptool.split('-')
    hits_by_clip = {}
    model_errors = []
    models = [('S', args.model), ('M', args.fallback_model)]
    for stage, model_name in models:
        pending = [i for i, s in enumerate(sections) if not complete(hits_by_clip.get(i, []), s['expected'])]
        if stage not in passes or not pending:
            continue
        model = None
        try:
            print(f"Loading speech model {model_name} ({args.device}, {args.compute_type}); {len(pending)} clips to analyze", flush=True)
            model = load_speech_model(model_name, args)
            for position, i in enumerate(pending, 1):
                print(f"{model_name}: clip {position}/{len(pending)}", flush=True)
                clip = scratch / f'clip_{i:06d}.wav'
                section = sections[i]
                offset = max(0, section['start'] - args.clip_context)
                if not clip.exists():
                    offset = extract_clip(args.input, section, clip, audio, args.boost_db, args.clip_context, duration)
                found = transcribe(model, clip, section, offset, swears)
                # Do not combine model hypotheses: that can double-count repeated words.
                if complete(found, section['expected']) or len(found) > len(hits_by_clip.get(i, [])):
                    hits_by_clip[i] = found
            print(f"Finished speech model {model_name}", flush=True)
        except ProcessingError as exc:
            if exc.code not in ('speech_model_missing', 'speech_model'):
                raise
            model_errors.append(f'{model_name}: {exc}')
            print(f'Speech model failed: {model_errors[-1]}; trying remaining configured speech models', file=sys.stderr, flush=True)
        except Exception as exc:
            model_errors.append(f'{model_name}: {exc}')
            print(f'Speech model failed: {model_errors[-1]}; trying remaining configured speech models', file=sys.stderr, flush=True)
        finally:
            # Release the small model before loading medium, including after failures.
            del model
            gc.collect()
    unresolved = [i for i, section in enumerate(sections)
                  if not complete(hits_by_clip.get(i, []), section['expected'])]
    if unresolved and model_errors:
        raise ProcessingError('speech_model', 'Speech recognition failed; full-subtitle fallback was blocked. '
                              'Fix the local speech runtime or model cache, then retry. ' + '; '.join(model_errors),
                              {'speech_model_errors': model_errors, 'unresolved_sections': len(unresolved)})
    result = []
    for i, section in enumerate(sections):
        hits = hits_by_clip.get(i, [])
        if complete(hits, section['expected']):
            result.extend(hits)
        elif 'FSM' in passes:
            reason = ('configured speech passes did not locate every expected word'
                      if any(p in passes for p in ('S', 'M')) else 'subtitle-only mode explicitly selected')
            print(f'Full-subtitle fallback: section {i + 1}, {section["start"]:.2f}–{section["end"]:.2f}s; {reason}', flush=True)
            result.append(dict(start=section['start'], end=section['end'], fallback=True))
        else:
            raise ProcessingError('speech_unresolved', 'Expected words were not all located; enable FSM for conservative subtitle muting')
    return result


def intervals(hits, before, after, duration):
    merged = []
    for start, end in sorted((max(0, h['start'] - before / 1000), min(duration, h['end'] + after / 1000)) for h in hits):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def interval_expression(ranges):
    """Keep FFmpeg's recursive expression parser shallow for long movies."""
    if not ranges:
        return '0'
    if len(ranges) == 1:
        start, end = ranges[0]
        return f'between(t,{start:.6f},{end:.6f})'
    middle = len(ranges) // 2
    return f'({interval_expression(ranges[:middle])}+{interval_expression(ranges[middle:])})'


def render(args, hits, audio, duration, staging, scratch):
    ranges = intervals(hits, args.pre_buffer, args.post_buffer, duration)
    expression = interval_expression(ranges)
    chain = f"volume=0:enable='{expression}'" if ranges else 'anull'
    graph = f'[0:{audio}]{chain}[muted]'
    beeps = [h for h in hits if args.beep_mode == 'both' or (args.beep_mode == 'segments') == h['fallback']]
    tone_ranges = intervals(beeps, args.pre_buffer, args.post_buffer, duration) if args.beep else []
    if tone_ranges:
        expression = interval_expression(tone_ranges)
        graph += f";sine=frequency=1000:sample_rate=48000:duration={duration},volume=0.3,volume=0:enable='not({expression})'[tone];[muted][tone]amix=inputs=2:duration=first:normalize=0[out]"
    else:
        graph += ';[muted]anull[out]'
    script = scratch / 'filters.txt'
    script.write_text(graph)
    version = run(['ffmpeg', '-version'], 30).splitlines()[0]
    match = re.search(r'version (\d+)', version)
    filter_option = '-/filter_complex' if match and int(match.group(1)) >= 7 else '-filter_complex_script'
    # Output contains only the censored audio track; retaining other tracks could expose uncensored dialogue.
    data, _ = probe(args.input)
    subtitle_options = []
    for index, stream in enumerate(s for s in data['streams'] if s['codec_type'] == 'subtitle'):
        if stream.get('codec_name') == 'mov_text':
            subtitle_options.extend([f'-c:s:{index}', 'srt'])
    run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-xerror', '-i', args.input,
         filter_option, str(script), '-map', '0:v:0', '-map', '[out]', '-map', '0:s?',
         '-map_metadata', '0', '-map_chapters', '0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
         '-c:s', 'copy', *subtitle_options, str(staging)], args.process_timeout)
    data, output_duration = probe(staging)
    if abs(output_duration - duration) > max(2, duration * 0.001) or not any(s['codec_type'] == 'video' for s in data['streams']) or not any(s['codec_type'] == 'audio' for s in data['streams']):
        raise ProcessingError('output_invalid', 'Output stream or duration validation failed; original retained')
    try:
        run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-i', str(staging), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], args.process_timeout)
    except ProcessingError as exc:
        raise ProcessingError('output_invalid', f'Output decode validation failed: {exc}') from exc


@contextmanager
def output_lock(output):
    import fcntl
    # Persistent lock inode prevents races when another process is waiting on it.
    path = Path(str(output) + '.lock')
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProcessingError('busy', 'Another process is working on this output') from exc
        yield


def match_counts(sections):
    return dict(matched_occurrences=sum(sum(s['expected'].values()) for s in sections),
                matched_word_count=sum(s['matched_word_count'] for s in sections))


def process(args):
    from cli import quality
    source = Path(args.input).resolve()
    if not source.is_file():
        raise ProcessingError('input_missing', 'Input video does not exist')
    args.input = str(source)
    swears = load_swears(args.swears)
    data, duration = probe(source)
    report = {}
    if args.expected_identity:
        try:
            report['title_verification'] = quality.identity(data, duration, json.loads(args.expected_identity))
        except quality.QualityReview as exc:
            raise ProcessingError(exc.code, str(exc), exc.details) from exc
    if not any(s.get('codec_type') == 'video' and s.get('disposition', {}).get('attached_pic', 0) == 0 for s in data['streams']):
        raise ProcessingError('video_missing', 'The input contains no video stream. Obtain a complete video copy; speech processing was not started.')
    audio_tracks = [s for s in data['streams'] if s.get('codec_type') == 'audio'
                    and (args.audio_stream is None or s['index'] == args.audio_stream)]
    audio_languages = {s.get('tags', {}).get('language', 'und').strip().lower() for s in audio_tracks}
    if audio_languages and not audio_languages & (language_codes(args.subtitle_lang) | {'', 'und', 'unknown', 'mul', 'zxx'}):
        message = f'Skipped: no {args.subtitle_lang} audio track; declared audio languages: {", ".join(sorted(audio_languages))}. Original retained.'
        print(message, flush=True)
        return dict(success=True, outcome='skipped_language', dry_run=args.dry_run, output_path=None,
                    audio_languages=sorted(audio_languages), message=message)
    audio = select_audio(data, args.subtitle_lang, args.audio_stream)
    output = Path(args.output).resolve() if args.output else default_output(source, args.output_suffix)
    if output == source or output.suffix.lower() != '.mkv':
        raise ProcessingError('configuration', 'Output must be a separate .mkv file')
    if output.exists() and not args.dry_run:
        raise ProcessingError('output_exists', f'Output already exists: {output}')
    if args.dry_run:
        subtitle, subtitles, subtitle_report = select_subtitle(args, data, None, audio, duration)
        report.update(subtitle_report)
        sections = matching_sections(subtitles, swears, duration)
        return dict(success=True, dry_run=True, candidate_sections=len(sections), output_path=None, audio_stream=audio,
                    **report, **match_counts(sections), outcome='no_matches_found' if not sections else 'matches_found')
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.temp_dir:
        Path(args.temp_dir).mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='bleeparr-', dir=args.temp_dir))
    staging = None
    original_stat = source.stat()
    try:
        with output_lock(output):
            if output.exists():
                raise ProcessingError('output_exists', f'Output already exists: {output}')
            subtitle, subtitles, subtitle_report = select_subtitle(args, data, scratch, audio, duration)
            report.update(subtitle_report)
            print('Subtitle check: ' + json.dumps(report), flush=True)
            sections = matching_sections(subtitles, swears, duration)
            counts = match_counts(sections)
            if not sections:
                if (source.stat().st_size, source.stat().st_mtime_ns) != (original_stat.st_size, original_stat.st_mtime_ns):
                    raise ProcessingError('input_changed', 'Input changed during subtitle analysis')
                print('No matching words found; no cleaned output created.', flush=True)
                return dict(success=True, dry_run=False, outcome='no_matches_found', output_path=None,
                            candidate_sections=0, mute_count=0, merged_mute_count=0,
                            fallback_sections=0, audio_stream=audio, **report, **counts,
                            message='No matching words found in the selected subtitles; no cleaned output was created. This does not prove the audio is free of profanity.')
            hits = refine(args, sections, scratch, audio, duration, swears)
            try:
                report['muting_review'] = quality.muting(args, hits, sections, duration, subtitle, swears,
                    [original_stat.st_dev, original_stat.st_ino, original_stat.st_size, original_stat.st_mtime_ns])
            except quality.QualityReview as exc:
                raise ProcessingError(exc.code, str(exc), {**report, **counts, **exc.details}) from exc
            print(f"Processing summary: {len(sections)} candidate sections; {len(hits)} muted intervals; {sum(hit['fallback'] for hit in hits)} subtitle fallback sections", flush=True)
            fd, stage_name = tempfile.mkstemp(prefix='.bleeparr-', suffix='.mkv', dir=output.parent)
            os.close(fd)
            staging = Path(stage_name)
            render(args, hits, audio, duration, staging, scratch)
            if (source.stat().st_size, source.stat().st_mtime_ns) != (original_stat.st_size, original_stat.st_mtime_ns):
                raise ProcessingError('input_changed', 'Input changed during processing; output not published')
            # Hard-link publication is atomic and refuses to overwrite an existing destination.
            os.link(staging, output)
            staging.unlink()
            warnings = []
            if args.delete_original:
                try:
                    source.unlink()
                except OSError as exc:
                    warnings.append(f'Output saved, but original could not be deleted: {exc}')
            if args.no_keep_subs and subtitle.parent != scratch:
                try:
                    subtitle.unlink()
                except OSError as exc:
                    warnings.append(f'Output saved, but subtitle could not be deleted: {exc}')
            return dict(success=True, dry_run=False, outcome='muted_words', output_path=str(output), candidate_sections=len(sections),
                        mute_count=len(hits), merged_mute_count=len(intervals(hits, args.pre_buffer, args.post_buffer, duration)),
                        fallback_sections=sum(h['fallback'] for h in hits), audio_stream=audio,
                        **report, **counts, warnings=warnings,
                        coverage='subtitle-guided; dialogue absent from subtitles is not analyzed')
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
        if args.retain_clips:
            print(f'Temporary files retained: {scratch}', file=sys.stderr)
        else:
            shutil.rmtree(scratch, ignore_errors=True)


def default_output(source, suffix):
    stem = source.stem
    if suffix == '(profanity removed)':
        stem = re.sub(r'(?:\s*\((?:edited by bleeparr|eddited by bleeparr|profanity removed)\))+$', '', stem, flags=re.I).rstrip() or stem
    return source.with_name(f'{stem} {suffix}.mkv')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--subtitle')
    p.add_argument('--swears', default=str(Path(__file__).with_name('swears.txt')))
    p.add_argument('--output')
    p.add_argument('--output-suffix', default='(profanity removed)')
    p.add_argument('--temp-dir')
    p.add_argument('--retain-clips', '--keep-clips', action='store_true')
    p.add_argument('--delete-original', action='store_true')
    p.add_argument('--no-keep-subs', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-embedded-subs', action='store_true')
    p.add_argument('--no-download-subs', action='store_true')
    p.add_argument('--subtitle-lang', default='eng')
    p.add_argument('--subtitle-timeout', type=int, default=120)
    p.add_argument('--process-timeout', type=int, default=14400)
    p.add_argument('--audio-stream', type=int)
    p.add_argument('--bleeptool', default='S-M-FSM', choices=['S', 'M', 'FSM', 'S-M', 'S-FSM', 'M-FSM', 'S-M-FSM'])
    p.add_argument('--model', default='small.en')
    p.add_argument('--fallback-model', default='medium.en')
    p.add_argument('--device', choices=['cpu', 'cuda', 'auto'], default='cpu')
    p.add_argument('--compute-type', default='int8')
    p.add_argument('--cpu-threads', type=int, default=2)
    p.add_argument('--clip-context', type=float, default=0.5)
    p.add_argument('--boost-db', type=float, default=0)
    p.add_argument('--pre-buffer', type=int, default=100)
    p.add_argument('--post-buffer', type=int, default=100)
    p.add_argument('--beep', action='store_true')
    p.add_argument('--beep-mode', choices=['words', 'segments', 'both'], default='words')
    p.add_argument('--alert-censoring-off', action='store_true', help='Compatibility option; words are no longer printed in logs')
    p.add_argument('--result-json', help='Write a structured result for automation (also on failure)')
    p.add_argument('--expected-identity', help='JSON title/year/episode/runtime metadata from the manager')
    p.add_argument('--subtitle-identity', help='JSON manager identity for subtitle discovery independent of title verification')
    p.add_argument('--check-subtitle-timing', action='store_true')
    p.add_argument('--review-broad-muting', action='store_true')
    p.add_argument('--max-fallback-percent', type=float, default=25)
    p.add_argument('--max-muted-percent', type=float, default=3)
    p.add_argument('--max-fallback-seconds', type=float, default=10)
    p.add_argument('--muting-approval', default='', help='Approval token for one unchanged reviewed muting plan')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    started = time.time()
    if args.result_json:
        result_path = Path(args.result_json).resolve()
        protected = [Path(args.input).resolve(), Path(args.swears).resolve()]
        if args.subtitle:
            protected.append(Path(args.subtitle).resolve())
        output_path = Path(args.output).resolve() if args.output else default_output(Path(args.input).resolve(), args.output_suffix)
        protected.append(output_path)
        if result_path in protected or result_path.suffix.lower() != '.json':
            print('Result path must be a separate .json file', file=sys.stderr)
            return 1
    try:
        if min(args.pre_buffer, args.post_buffer, args.clip_context) < 0 or not math.isfinite(args.clip_context) or not math.isfinite(args.boost_db) or min(args.subtitle_timeout, args.process_timeout, args.cpu_threads) <= 0:
            raise ProcessingError('configuration', 'Buffers must be nonnegative; timeouts and threads must be positive')
        if any(not math.isfinite(v) or not 0 <= v <= 100 for v in [args.max_fallback_percent, args.max_muted_percent]) or not math.isfinite(args.max_fallback_seconds) or args.max_fallback_seconds <= 0:
            raise ProcessingError('configuration', 'Review percentages must be 0–100 and the fallback duration must be positive')
        result = process(args)
    except ProcessingError as exc:
        result = dict(success=False, error_code=exc.code, error=str(exc), **exc.details)
    except OSError as exc:
        result = dict(success=False, error_code='disk_full' if exc.errno == errno.ENOSPC else 'filesystem', error=str(exc))
    except Exception as exc:
        result = dict(success=False, error_code='internal', error=str(exc))
    result['elapsed_seconds'] = round(time.time() - started, 2)
    if args.result_json:
        try:
            destination = Path(args.result_json)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, delete=False) as handle:
                json.dump(result, handle, indent=2)
            os.replace(handle.name, destination)
        except OSError as exc:
            print(f'Could not save result: {exc}', file=sys.stderr)
            return 1
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--download-subtitle':
        download_subtitle(*sys.argv[2:])
    elif len(sys.argv) == 6 and sys.argv[1] == '--download-subtitle-candidates':
        from cli.subtitle_search import download_candidates
        download_candidates(sys.argv[2], sys.argv[3], sys.argv[4], json.loads(sys.argv[5]))
    else:
        sys.exit(main())
