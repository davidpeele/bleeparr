"""Opt-in, bounded blocklisting of unambiguously matched damaged downloads."""
import hashlib
import time
from datetime import datetime
from pathlib import Path
from backend import store, service


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (TypeError, AttributeError, ValueError):
        raise ValueError('Download history is missing a usable import date') from None


def unchanged(job):
    try:
        path = Path(job['path']).resolve()
        stat = path.stat()
        current = hashlib.sha256(repr((job['kind'], str(path), stat.st_size, stat.st_mtime_ns)).encode()).hexdigest()
        if current == job['fingerprint']:
            return stat
    except OSError:
        pass
    raise ValueError('The failed file has changed or disappeared; no release was blocklisted')


def history(arr, **filters):
    rows = []
    for page in range(1, 11):
        data = arr.request('GET', 'history', params=dict(page=page, pageSize=100, sortKey='date', sortDirection='descending', **filters))
        batch = data.get('records', [])
        rows.extend(batch)
        if len(rows) >= data.get('totalRecords', len(rows)):
            return rows
        if not batch:
            break
    raise ValueError('Download history is too large or incomplete to safely identify this release')


def prepare(job, config):
    if job.get('result', {}).get('error_code') != 'invalid_media':
        raise ValueError('Blocklisting is only available for damaged-media failures, not local processing problems')
    stat = unchanged(job)
    kind = job['kind']
    arr = service.Arr(kind, config)
    if kind == 'sonarr':
        episode = arr.request('GET', f"episode/{job['item_id']}")
        if episode.get('seriesId') != job['parent_id'] or not episode.get('episodeFileId'):
            raise ValueError('The episode no longer identifies the failed file')
        file = arr.request('GET', f"episodefile/{episode['episodeFileId']}")
        episodes = arr.request('GET', 'episode', params={'seriesId': job['parent_id']})
        if sum(e.get('episodeFileId') == file.get('id') for e in episodes) != 1:
            raise ValueError('This is a shared multi-episode file; review replacement in Sonarr')
        item_key, params = 'episodeId', {'episodeId': job['item_id']}
    else:
        movie = arr.request('GET', f"movie/{job['item_id']}")
        file = movie.get('movieFile') or {}
        item_key, params = 'movieId', {'movieIds': job['item_id']}
    if not file.get('id') or file.get('path') != job.get('remote_path') or file.get('size') != stat.st_size:
        raise ValueError('The manager file no longer matches the failed file; replacement needs review')
    if service.local_path(file['path'], kind, config) != Path(job['path']).resolve():
        raise ValueError('An alternate recovery input was processed; its release cannot be blocklisted automatically')
    added = timestamp(file.get('dateAdded'))
    records = history(arr, **params)
    imports = [r for r in records if r.get('eventType') == 'downloadFolderImported' and r.get(item_key) == job['item_id']]
    # The newest import must match; never reach back to an older release sharing a filename.
    imports.sort(key=lambda r: timestamp(r.get('date')), reverse=True)
    if not imports:
        raise ValueError('No import history exists for this file; select a replacement in the media manager')
    imported = imports[0]
    if imported.get('data', {}).get('importedPath') != file['path'] or abs(timestamp(imported.get('date')) - added) > 120 or not imported.get('downloadId'):
        raise ValueError('Import history does not identify the current file unambiguously; no release was blocklisted')
    download_id = imported['downloadId']
    download_history = history(arr, downloadId=download_id)
    grabs = [r for r in download_history if r.get('eventType') == 'grabbed']
    if not grabs or any(r.get(item_key) != job['item_id'] for r in grabs):
        raise ValueError('This download contains other titles or episodes, or its grab history is missing; review it manually')
    matches = [r for r in grabs if r.get('sourceTitle') == imported.get('sourceTitle') and r.get('downloadId') == download_id]
    if len(matches) != 1 or not matches[0].get('id') or not matches[0].get('sourceTitle'):
        raise ValueError('The originating release could not be identified uniquely')
    grab = matches[0]
    settings = arr.request('GET', 'config/downloadclient')
    source = str(grab.get('data', {}).get('releaseSource', '')).lower()
    native_search = settings.get('autoRedownloadFailed') is True
    if source.isdigit() or not isinstance(settings.get('autoRedownloadFailed'), bool):
        raise ValueError('Manager redownload behavior could not be verified; review this release manually')
    if source == 'interactivesearch':
        native_search = native_search and settings.get('autoRedownloadFailedFromInteractiveSearch') is True
    unchanged(job)
    return dict(history_id=grab['id'], download_id=download_id, release=grab['sourceTitle'],
                file_id=file['id'], native_search=native_search)


def request(job, config=None):
    config = config or store.settings()
    if not config.get('auto_blocklist'):
        raise ValueError('Enable automatic blocklisting in Settings first')
    plan = prepare(job, config)
    kind, item_id = job['kind'], job['item_id']
    now = time.time()
    with store.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM replacements WHERE kind=? AND download_id=?', (kind, plan['download_id'])).fetchone():
            raise ValueError('This download already has a replacement request or uncertain outcome; review its history before further action')
        recent = conn.execute('SELECT count(*) AS n, max(created) AS latest FROM replacements WHERE kind=? AND item_id=? AND created>?', (kind, item_id, now - 30*86400)).fetchone()
        if recent['n'] >= config['replacement_limit']:
            raise ValueError('The replacement limit for this title in 30 days has been reached')
        previous = conn.execute('SELECT requested FROM searches WHERE kind=? AND item_id=?', (kind,item_id)).fetchone()
        latest = max(recent['latest'] or 0, previous['requested'] if previous else 0)
        if latest and now - latest < config['replacement_cooldown_hours'] * 3600:
            raise ValueError('A replacement/search request is still within its cooldown period')
        conn.execute('INSERT INTO replacements VALUES (?,?,?,?,?,?,?,?)', (kind, plan['download_id'], item_id, job['id'], plan['history_id'], now, 'outcome_unknown', plan['release']))
        conn.execute('INSERT OR REPLACE INTO searches VALUES (?,?,?,?)', (kind,item_id,now,'blocklist_requested'))
    arr = service.Arr(kind, config)
    try:
        unchanged(job)
        current = arr.request('GET', f"episode/{item_id}" if kind == 'sonarr' else f"movie/{item_id}")
        file_id = current.get('episodeFileId') if kind == 'sonarr' else (current.get('movieFile') or {}).get('id')
        if file_id != plan['file_id']:
            raise ValueError('Manager now points to a different file')
        arr.request('POST', f"history/failed/{plan['history_id']}")
        if not plan['native_search']:
            name, key = ('EpisodeSearch','episodeIds') if kind == 'sonarr' else ('MoviesSearch','movieIds')
            arr.request('POST', 'command', json={'name':name, key:[item_id]})
    except Exception:
        store.event(f"{job['title']}: replacement outcome uncertain; check {kind.title()} history. Automatic resending is stopped.")
        raise ValueError('Replacement request failed or its outcome is uncertain; review the manager history before retrying') from None
    with store.db() as conn:
        conn.execute("UPDATE replacements SET status='requested' WHERE kind=? AND download_id=?", (kind,plan['download_id']))
    message = 'Release marked failed and replacement search requested. The current file is retained; availability and manager quality rules determine whether a replacement downloads.'
    store.event(f"{job['title']}: {message}")
    return {'message':message, 'release':plan['release']}
