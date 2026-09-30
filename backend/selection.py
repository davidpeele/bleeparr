"""Monitoring rules use manager paths, independent of local volume mappings."""
import posixpath
import re
from pathlib import PurePosixPath
from backend import store


def audio_skip_reason(file):
    """Prefer audio metadata; release languages are a fallback, never subtitles."""
    raw = (file.get('mediaInfo') or {}).get('audioLanguages')
    values = re.split(r'[/,;|+]', raw) if isinstance(raw, str) and raw.strip() else [
        value.get('name', '') if isinstance(value, dict) else str(value)
        for value in (file.get('languages') or [])
    ]
    languages = {value.strip().lower() for value in values}
    if not languages or languages & {'', 'und', 'unknown', 'undefined', 'mul', 'multiple', 'multi', 'zxx'}:
        return None
    if languages & {'en', 'eng', 'english'}:
        return None
    return 'Skipped: non-English audio (' + ', '.join(sorted(languages)) + '). English subtitles do not change audio eligibility.'


def skip_reason(item):
    return audio_skip_reason(item.get('movieFile') or {})


def roots(config):
    return [PurePosixPath(posixpath.normpath(p.strip())) for p in config.get('cleanvid_roots', '').splitlines() if p.strip()]


def matches(item, config):
    raw = item.get('path') or ''
    if not config.get('cleanvid_enabled') or not raw.startswith('/'):
        return False
    path = PurePosixPath(posixpath.normpath(raw))
    return any(path.is_relative_to(root) for root in roots(config))


def preferences(kind):
    with store.db() as db:
        manual = {r[0] for r in db.execute('SELECT item_id FROM monitored WHERE kind=?', (kind,))}
        excluded = {r[0] for r in db.execute('SELECT item_id FROM monitoring_exclusions WHERE kind=?', (kind,))}
    return manual, excluded


def state(item, config, manual, excluded):
    if skip_reason(item):
        return 'foreign_audio'
    if item['id'] in manual:
        return 'manual'
    if item['id'] in excluded:
        return 'excluded'
    return 'cleanvid' if matches(item, config) else 'off'
