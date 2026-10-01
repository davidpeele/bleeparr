"""Bounded provider discovery; release similarity ranks candidates, speech verifies them."""
import json
from pathlib import Path
import re


MAX_DOWNLOADS = 5


def search_video(filename, identity):
    from subliminal import Video
    from subliminal.video import Episode, Movie

    # Keep release information inferred from the actual basename. Manager identity
    # supplies the canonical title/episode when names have been renamed locally.
    try:
        video = Video.fromname(Path(filename).name)
    except ValueError:
        if not identity.get('title'):
            raise
        title = identity['title']
        name = (f"{title}.S{identity['season']:02}E{identity['episode']:02}.mkv"
                if 'season' in identity and 'episode' in identity else f'{title}.mkv')
        video = Video.fromname(name)
    if identity.get('title') and 'season' in identity and 'episode' in identity and not isinstance(video, Episode):
        release = video
        video = Video.fromname(f"{identity['title']}.S{identity['season']:02}E{identity['episode']:02}.mkv")
        for field in ('source', 'format', 'release_group', 'resolution', 'video_codec', 'audio_codec', 'fps'):
            if hasattr(release, field):
                setattr(video, field, getattr(release, field))
    if identity.get('title'):
        title = re.sub(r'\s*\(\d{4}\)$', '', identity['title']).strip()
        if isinstance(video, Episode):
            video.series = title
            video.alternative_series = identity.get('aliases', [])
            video.season = identity.get('season', video.season)
            # Accommodate both episode representations in provider libraries.
            if 'episode' in identity:
                if hasattr(video, 'episodes'):
                    if identity['episode'] not in video.episodes:
                        video.episodes = [identity['episode']]
                else:
                    video.episode = identity['episode']
        elif isinstance(video, Movie):
            video.title = title
            video.alternative_titles = identity.get('aliases', [])
        if identity.get('year'):
            video.year = identity['year']
    return video


def candidate_rank(subtitle, video):
    from subliminal.video import Episode

    matches = set(subtitle.get_matches(video))
    required = {'series', 'season', 'episode'} if isinstance(video, Episode) else {'title'}
    # A remake must match its year. A hash match is also sufficient evidence of
    # identity, but still must pass language, coverage and speech checks later.
    if getattr(video, 'year', None):
        required.add('year')
    if not required <= matches and 'hash' not in matches:
        return None
    if getattr(subtitle, 'foreign_only', False):
        return None
    weights = {'hash': 1000, 'release_group': 30, 'fps': 20,
               'source': 15, 'format': 15, 'streaming_service': 10,
               'video_codec': 5, 'audio_codec': 3, 'resolution': 2}
    return sum(weights.get(match, 1) for match in matches), sorted(matches)


def download_candidates(filename, language, destination, identity=None):
    from babelfish import Language
    from subliminal import region
    from subliminal.core import ProviderPool

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / 'candidates.json'
    region.configure('dogpile.cache.memory')
    video = search_video(filename, identity or {})
    wanted = Language.fromalpha2(language) if len(language) == 2 else Language(language)
    entries = []
    manifest.write_text('[]', encoding='utf-8')
    with ProviderPool() as pool:
        ranked = []
        for subtitle in pool.list_subtitles(video, {wanted}):
            if subtitle.language != wanted:
                continue
            try:
                rank = candidate_rank(subtitle, video)
            except Exception:
                continue  # One broken provider's metadata must not abort other results.
            if rank is not None:
                ranked.append((rank[0], rank[1], subtitle))
        seen = set()
        attempts = 0
        for score, matches, subtitle in sorted(ranked, key=lambda item: -item[0]):
            key = (subtitle.provider_name, str(subtitle.id))
            if key in seen:
                continue
            seen.add(key)
            attempts += 1
            if attempts > MAX_DOWNLOADS:
                break
            if not pool.download_subtitle(subtitle) or not subtitle.text:
                continue
            name = f'candidate-{len(entries)}.srt'
            (destination / name).write_text(subtitle.text, encoding='utf-8')
            entries.append(dict(file=name, subtitle_provider=subtitle.provider_name,
                                subtitle_provider_id=str(subtitle.id), subtitle_match_score=score,
                                subtitle_matches=matches))
            # Publish incrementally: a later provider timeout can still leave
            # earlier downloads available for the parent's validation.
            pending = manifest.with_suffix('.tmp')
            pending.write_text(json.dumps(entries), encoding='utf-8')
            pending.replace(manifest)
    return entries
