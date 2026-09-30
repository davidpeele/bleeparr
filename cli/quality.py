"""Local evidence checks. Missing evidence is reported, never treated as proof."""
from collections import Counter
from difflib import SequenceMatcher
import gc
import hashlib
import json
import math
from pathlib import Path
import re


class QualityReview(Exception):
    def __init__(self, code, message, details):
        super().__init__(message)
        self.code, self.details = code, details


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def identity(data, duration, expected):
    declared = str(data.get('format', {}).get('tags', {}).get('title', '')).strip()
    report = dict(expected_title=expected.get('title'), declared_title=declared or None,
                  expected_runtime_seconds=expected.get('runtime_seconds'), duration_seconds=duration,
                  status='unavailable', warnings=[])
    problems = []
    if expected.get('title') and declared:
        candidate = declared.rsplit('|', 1)[-1].strip()
        marker = re.search(r'(?:[. _(-])((?:19|20)\d{2})\b|[. _-]S\d{1,2}E\d{1,3}', candidate, re.I)
        title = candidate[:marker.start()] if marker else candidate
        # Skip encoder labels and generic container labels rather than guess.
        technical = re.search(r'encoded|encoder|rip by|www\.|https?://|^video$|^movie$', title, re.I)
        aliases = [expected['title'], *expected.get('aliases', [])]
        if normalized(title) and not technical:
            scores = [SequenceMatcher(None, normalized(alias), normalized(title)).ratio() for alias in aliases]
            if max(scores) < .65:
                problems.append('The internal movie/series title differs from the selected title.')
            else:
                report['status'] = 'passed'
            if marker and marker.group(1) and expected.get('year') and expected.get('season') is None:
                if abs(int(marker.group(1)) - int(expected['year'])) > 1:
                    problems.append('The internal release year differs from the selected movie.')
        episode = re.search(r'S(\d{1,2})E(\d{1,3})((?:E\d{1,3})*)', candidate, re.I)
        if episode and expected.get('season') is not None:
            numbers = [int(episode.group(2)), *map(int, re.findall(r'E(\d+)', episode.group(3), re.I))]
            if int(episode.group(1)) != expected['season'] or expected.get('episode') not in numbers:
                problems.append('The internal season/episode differs from the queued episode.')
    runtime = expected.get('runtime_seconds')
    if runtime and math.isfinite(float(runtime)) and float(runtime) > 0:
        if abs(duration - float(runtime)) > max(300, float(runtime) * .15):
            problems.append('The runtime differs substantially; this may be another title or a different cut.')
    if report['status'] == 'unavailable':
        report['warnings'].append('No usable internal title; title identity could not be independently confirmed.')
    if problems:
        raise QualityReview('title_review', 'Download identity needs review. Original retained.',
                            {'title_verification': {**report, 'status': 'review', 'warnings': problems}})
    return report


def muting(args, hits, sections, duration, subtitle, swears, source_signature):
    from cli.bleeparr import intervals
    ranges = intervals(hits, args.pre_buffer, args.post_buffer, duration)
    fallback = [hit for hit in hits if hit['fallback']]
    seconds = sum(end - start for start, end in ranges)
    longest = max((hit['end'] - hit['start'] for hit in fallback), default=0)
    share = len(fallback) / len(sections) if sections else 0
    report = dict(candidate_sections=len(sections), fallback_sections=len(fallback),
                  fallback_percent=round(share * 100, 2), muted_seconds=round(seconds, 2),
                  muted_percent=round(seconds / duration * 100, 2), longest_fallback_seconds=round(longest, 2))
    report['fallback_intervals'] = [[hit['start'],hit['end']] for hit in fallback]
    report['mute_intervals'] = ranges
    reasons = []
    if len(fallback) >= 3 and share * 100 > args.max_fallback_percent:
        reasons.append('Too many matching sections require whole-subtitle muting.')
    if seconds / duration * 100 > args.max_muted_percent:
        reasons.append('The planned mutes cover an unusually large portion of the program.')
    if longest > args.max_fallback_seconds:
        reasons.append('A whole-subtitle mute is unusually long.')
    payload = dict(source=source_signature, subtitle=hashlib.sha256(Path(subtitle).read_bytes()).hexdigest(),
                   swears=sorted(swears), strategy=args.bleeptool, model=args.model, fallback_model=args.fallback_model,
                   ranges=ranges, fallback=fallback, before=args.pre_buffer, after=args.post_buffer,
                   limits=[args.max_fallback_percent, args.max_muted_percent, args.max_fallback_seconds])
    token = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    report.update(reasons=reasons, approved=bool(reasons and args.muting_approval == token))
    if args.review_broad_muting and reasons and not report['approved']:
        raise QualityReview('muting_review', 'Planned muting needs review. No output was created.',
                            dict(muting_review=report, review_token=token, candidate_sections=len(sections),
                                 fallback_sections=len(fallback), mute_count=len(hits),review_source_signature=source_signature))
    return report


STOPWORDS = set('a an the and or but i you he she it we they to of in on at for with is are was were be that this'.split())


def alignment(args, subtitles, scratch, audio, duration, text, tokenize, load_model, extract_clip):
    candidates = []
    for sub in subtitles:
        words = [w for w in tokenize(re.sub(r'\[[^]]*\]|\([^)]*\)', ' ', text(sub))) if w not in STOPWORDS]
        start, end = sub.start.total_seconds(), sub.end.total_seconds()
        if len(words) >= 4 and 1 <= end - start <= 12 and start > duration * .02 and end < duration * .96:
            candidates.append((sub, words))
    if len(candidates) < 3:
        raise QualityReview('subtitle_alignment_review', 'Not enough dialogue to verify subtitle timing. Original retained.',
                            {'subtitle_alignment': {'status': 'uncertain', 'samples': []}})
    chosen = [candidates[round(i * (len(candidates) - 1) / (min(6, len(candidates)) - 1))]
              for i in range(min(6, len(candidates)))]
    pending = list(range(len(chosen)))
    samples, errors = {}, []
    for name in dict.fromkeys([args.model, args.fallback_model]):
        if not pending:
            break
        model = None
        try:
            print(f'Checking subtitle timing with {name}; {len(pending)} dialogue samples', flush=True)
            model = load_model(name, args)
            for i in pending:
                sub, expected = chosen[i]
                start, end = sub.start.total_seconds(), sub.end.total_seconds()
                clip = scratch / f'alignment_{i}.wav'
                offset = extract_clip(args.input, {'start': start, 'end': end}, clip, audio, 0, 2, duration)
                segments, _ = model.transcribe(str(clip), beam_size=5, word_timestamps=True,
                                                condition_on_previous_text=False)
                heard = [(w, offset + word.start, offset + word.end) for segment in segments
                         for word in segment.words or [] for w in tokenize(word.word) if w not in STOPWORDS
                         and math.isfinite(word.start) and math.isfinite(word.end) and word.end > word.start]
                in_time = Counter(w for w, a, b in heard if a < end + .75 and b > start - .75)
                score = sum((Counter(expected) & in_time).values()) / len(expected)
                sample = dict(start_seconds=start, end_seconds=end, agreement=round(score, 3), model=name)
                if score > samples.get(i, {}).get('agreement', -1):
                    samples[i] = sample
            pending = [i for i in pending if samples.get(i, {}).get('agreement', 0) < .5]
        except Exception as exc:
            errors.append(f'{name}: {exc}')
        finally:
            del model
            gc.collect()
    good = sum(sample['agreement'] >= .5 for sample in samples.values())
    report = dict(status='passed' if good >= math.ceil(len(chosen) * 2 / 3) else 'review',
                  samples=[samples.get(i, dict(start_seconds=chosen[i][0].start.total_seconds(), agreement=0))
                           for i in range(len(chosen))], confirmed_samples=good, sampled_sections=len(chosen),
                  limitations='Sampled dialogue only; passing does not verify every cue or automatically correct timing.')
    if errors and good < math.ceil(len(chosen) * 2 / 3):
        raise QualityReview('speech_model', 'Speech runtime failed during subtitle timing verification. Original retained.',
                            {'speech_model_errors': errors, 'subtitle_alignment': report})
    if report['status'] != 'passed':
        raise QualityReview('subtitle_alignment_review', 'Subtitle text did not reliably match speech at its timestamps. Review the subtitle/cut before retrying.',
                            {'subtitle_alignment': report})
    return report
