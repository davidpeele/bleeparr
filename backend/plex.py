"""Optional synopsis updates for completed outputs already indexed by Plex."""
import json
import os
from pathlib import Path, PurePosixPath
import threading
import time
from backend import store

SYNC_LOCK = threading.Lock()


def connect(config):
    from plexapi.server import PlexServer
    if not config['plex_url'] or not config['plex_token']:
        raise ValueError('Configure the Plex URL and token first')
    return PlexServer(config['plex_url'], config['plex_token'], timeout=15)


def libraries(config):
    try:
        server = connect(config)
        return [{'id': str(s.key), 'title': s.title, 'type': s.type} for s in server.library.sections() if s.type in ('movie', 'show')]
    except Exception:
        raise ValueError('Could not connect to Plex; check its URL and token') from None


def mapped_output(output, config):
    source = Path(output).resolve()
    root = Path(os.getenv('OUTPUT_DIR', str(store.data_dir() / 'cleaned'))).resolve()
    roots = [root] + [Path(p).resolve() for p in os.getenv('MEDIA_ROOTS', '/media').split(os.pathsep) if p]
    if not any(source.is_relative_to(p) for p in roots) or not source.is_file():
        return None
    before, after = config['plex_path_from'], config['plex_path_to']
    if before:
        try:
            return str(PurePosixPath(after) / source.relative_to(Path(before).resolve()).as_posix())
        except ValueError:
            return None
    return source.as_posix()


def media_paths(item):
    # Check every version/part: never label a mixed clean/unclean item as wholly clean.
    return [str(PurePosixPath(p.file)) if getattr(p, 'file', None) else None
            for media in getattr(item, 'media', []) for p in getattr(media, 'parts', [])]


def edit_note(server, item, note):
    item.reload()  # Preserve the latest synopsis, including manual edits.
    identity = f'{server.machineIdentifier}:{item.ratingKey}'
    with store.db() as db:
        previous = db.execute('SELECT note FROM plex_notes WHERE identity=?', (identity,)).fetchone()
    summary = item.summary or ''
    updated = summary
    if previous and updated.startswith(previous['note']):
        updated = updated[len(previous['note']):].lstrip()
    if not (updated == note or updated.startswith(note + ' ') or updated.startswith(note + '\n')):
        updated = (note + ' ' + updated).strip()
    if updated != summary:
        item.editSummary(updated)  # PlexAPI locks edited summary fields, like the existing script.
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO plex_notes VALUES (?,?)', (identity, note))
    return updated != summary


def sync(config=None, manual=False):
    config = config or store.settings()
    if not config['plex_enabled']:
        return {'message': 'Plex synopsis updates are disabled', 'updated': 0}
    if not config['plex_libraries']:
        raise ValueError('Select at least one Plex library')
    if not SYNC_LOCK.acquire(blocking=False):
        return {'message': 'A Plex update is already running', 'updated': 0}
    try:
        return _sync(config, manual)
    finally:
        SYNC_LOCK.release()


def _sync(config, manual):
    now = time.time()
    with store.db() as db:
        rows = list(db.execute("SELECT id,result FROM jobs WHERE status='completed'"))
        history = {r['job_id']: dict(r) for r in db.execute('SELECT * FROM plex_updates')}
    known = {}
    pending = {}
    for row in rows:
        result = json.loads(row['result'])
        if not result.get('success') or result.get('dry_run') or not result.get('output_path'):
            continue
        from backend.output import matches
        if result.get('output_signature') and not matches(result['output_path'], result['output_signature']):
            continue
        path = mapped_output(result['output_path'], config)
        if not path:
            continue
        known.setdefault(path, []).append(row['id'])
        state = history.get(row['id'])
        if manual or not state or (state['status'] != 'done' and state['attempts'] < 12 and state['next_try'] <= now):
            pending[row['id']] = path
    if not pending:
        return {'updated': 0, 'message': 'No completed outputs waiting for Plex. Cleaned files must still exist in the output folder.'}
    # Persist attempts before the network call. A restart cannot create an unbounded retry loop.
    with store.db() as db:
        for job_id in pending:
            attempts = 1 if manual else history.get(job_id, {}).get('attempts', 0) + 1
            db.execute('INSERT OR REPLACE INTO plex_updates VALUES (?,?,?,?,?)', (job_id, attempts, now + 300, 'pending', 'Waiting for Plex to index the cleaned output'))
    updated = 0
    matched = set()
    try:
        server = connect(config)
        series = {}
        for section_id in config['plex_libraries']:
            section = server.library.sectionByID(int(section_id))
            if section.type not in ('movie', 'show'):
                continue
            items = section.search(libtype='episode') if section.type == 'show' else section.all()
            for item in items:
                paths = media_paths(item)
                if not paths or any(p not in known for p in paths):
                    continue
                ids = {job_id for path in paths for job_id in known[path]} & pending.keys()
                if not ids:
                    continue
                updated += edit_note(server, item, config['plex_note'])
                matched.update(ids)
                if section.type == 'show' and config['plex_series_note_enabled']:
                    series[str(item.grandparentRatingKey)] = item
        for episode in series.values():
            updated += edit_note(server, episode.show(), config['plex_series_note'])
        with store.db() as db:
            for job_id in matched:
                db.execute("UPDATE plex_updates SET status='done', error='' WHERE job_id=?", (job_id,))
        message = f'Plex: {updated} synopsis update(s); {len(pending) - len(matched)} output(s) awaiting an unambiguous cleaned-file match.'
        store.event(message)
        return {'updated': updated, 'waiting': len(pending) - len(matched), 'message': message}
    except Exception:
        # Third-party errors can include URLs/tokens. Never persist or expose their raw text.
        with store.db() as db:
            for job_id in pending:
                db.execute("UPDATE plex_updates SET error=? WHERE job_id=?", ('Plex update failed; check connection, libraries and permissions', job_id))
        store.event('Plex synopsis update failed; media processing remains completed. Check Plex settings or retry Sync now.')
        raise ValueError('Plex update failed; check connection, libraries and permissions. Your cleaned media is unaffected.') from None
