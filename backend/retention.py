"""Bounded, opt-in retention of unmuted originals outside media libraries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from backend import store

LOCK = threading.RLock()


class RetentionFull(ValueError):
    pass


def root():
    return Path(os.getenv('ORIGINALS_DIR', str(store.data_dir() / 'originals'))).resolve()


def signature(path):
    stat = Path(path).stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def matches(path, expected):
    try:
        return signature(path) == expected
    except OSError:
        return False


def managed_path(path):
    return Path(path).resolve().is_relative_to(root()) and not Path(path).is_symlink()


def records():
    with store.db() as db:
        return [dict(row) for row in db.execute('SELECT * FROM original_backups ORDER BY created DESC')]


def processing(path):
    with store.db() as db:
        return bool(db.execute("SELECT 1 FROM jobs WHERE path=? AND status='running' LIMIT 1",(str(path),)).fetchone())


def valid_record(row):
    return bool(row and row['status'] == 'ready' and (row['expires'] > time.time() or processing(row['path'])) and managed_path(row['path'])
                and matches(row['path'], json.loads(row['signature'])))


def retained_source(path):
    with store.db() as db:
        row = db.execute('SELECT * FROM original_backups WHERE path=?', (str(Path(path).resolve()),)).fetchone()
    return dict(row) if valid_record(row) else None


def recovery_source(cleaned):
    for row in records():
        if row['output_path'] == str(Path(cleaned).resolve()) and row['output_signature']:
            if valid_record(row) and matches(cleaned, json.loads(row['output_signature'])):
                return Path(row['path'])
    return None


def usage():
    folder = root()
    # Count unregistered/incomplete files too; never delete those to make space.
    return sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) if folder.exists() else 0


def capacity(size, config):
    limit = config.get('original_storage_gb', 100) * 1024 ** 3
    if usage() + size > limit:
        raise RetentionFull('The original archive is full. Wait for expiry, increase its storage limit, or turn retention off. Original retained; no replacement published.')
    folder = root()
    folder.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(folder).free < size + 64 * 1024 ** 2:
        raise RetentionFull('The original archive has insufficient free space. Original retained; no replacement published.')


def cleanup(now=None):
    now = time.time() if now is None else now
    with LOCK:
        for row in records():
            if row['status'] != 'ready' or row['expires'] > now:
                continue
            if processing(row['path']):
                continue
            path = Path(row['path'])
            subtitle = Path(row['subtitle_path']) if row.get('subtitle_path') else None
            subtitle_ok = not subtitle or not subtitle.exists() or (managed_path(subtitle) and matches(subtitle,json.loads(row['subtitle_signature'])))
            if managed_path(path) and matches(path, json.loads(row['signature'])) and subtitle_ok:
                path.unlink()
                if subtitle and subtitle.exists():
                    subtitle.unlink()
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
                state = 'expired'
            elif not path.exists() and subtitle_ok:
                if subtitle and subtitle.exists():
                    subtitle.unlink()
                state = 'expired'
            else:
                state = 'changed'
                store.event('An expired original backup changed; it was preserved for review.')
            with store.db() as db:
                db.execute('UPDATE original_backups SET status=? WHERE id=?', (state, row['id']))


def plan(source, source_signature, config, job_id):
    existing = retained_source(source)
    if existing:
        return dict(id=existing['id'], reused=True)
    if not config.get('retain_originals', False):
        return None
    identity = hashlib.sha256(repr((str(source), source_signature)).encode()).hexdigest()
    spec = dict(id=identity, path=str(root() / identity / source.name), days=config.get('original_retention_days',7),
                limit_gb=config.get('original_storage_gb',100), job_id=job_id, reused=False)
    with store.db() as db:
        already=db.execute('SELECT * FROM original_backups WHERE id=?',(identity,)).fetchone()
    if valid_record(already):
        return spec
    cleanup()
    capacity(source_signature[2], config)
    return spec


def ensure(receipt):
    spec = receipt.get('original_retention')
    if not spec:
        return None
    with LOCK:
        with store.db() as db:
            row = db.execute('SELECT * FROM original_backups WHERE id=?', (spec['id'],)).fetchone()
        if valid_record(row):
            return dict(row)
        if spec['reused']:
            raise ValueError('The retained original expired or changed; replacement was cancelled.')
        # Publication may already have completed before the worker restarted.
        if not Path(receipt['source']).exists() and matches(receipt['destination'], receipt['cleaned_signature']):
            return dict(row) if row else None
        source, dest = Path(receipt['source']), Path(spec['path'])
        if not matches(source, receipt['source_signature']):
            raise ValueError('Original changed before archiving; replacement was cancelled.')
        if not managed_path(dest):
            raise ValueError('Original archive path is outside its configured root.')
        if dest.exists():
            # A crash can leave a complete archive copy before its DB record.
            with source.open('rb') as a, dest.open('rb') as b:
                if hashlib.file_digest(a, 'sha256').digest() != hashlib.file_digest(b, 'sha256').digest():
                    raise ValueError('An incomplete archive copy needs review; original retained.')
        else:
            cleanup()
            capacity(receipt['source_signature'][2], {'original_storage_gb':spec['limit_gb']})
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_name(dest.name + '.copying')
            if temp.exists():
                raise ValueError('An interrupted original backup needs review; original retained.')
            shutil.copy2(source, temp)
            with source.open('rb') as a, temp.open('rb') as b:
                if hashlib.file_digest(a, 'sha256').digest() != hashlib.file_digest(b, 'sha256').digest():
                    raise ValueError('Original backup verification failed; original retained.')
            if not matches(source, receipt['source_signature']):
                raise ValueError('Original changed while archiving; replacement cancelled.')
            with temp.open('rb') as f:
                os.fsync(f.fileno())
            os.replace(temp, dest)
            from backend.output import sync_directory
            sync_directory(dest.parent)
        now = time.time()
        subtitle_path = receipt['result'].get('subtitle_path')
        archived_subtitle = None
        if subtitle_path and Path(subtitle_path).is_file():
            archived_subtitle = dest.with_suffix('.srt')
            if not archived_subtitle.exists():
                capacity(Path(subtitle_path).stat().st_size, {'original_storage_gb':spec['limit_gb']})
                shutil.copy2(subtitle_path,archived_subtitle)
            with Path(subtitle_path).open('rb') as a, archived_subtitle.open('rb') as b:
                if hashlib.file_digest(a,'sha256').digest()!=hashlib.file_digest(b,'sha256').digest():
                    raise ValueError('Archived subtitle verification failed; original retained.')
            with archived_subtitle.open('rb') as f:
                os.fsync(f.fileno())
            from backend.output import sync_directory
            sync_directory(dest.parent)
        with store.db() as db:
            db.execute('''INSERT OR REPLACE INTO original_backups
                (id,source_path,path,size,source_signature,signature,created,expires,status,job_id,subtitle_path,subtitle_signature)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (spec['id'], str(source), str(dest), dest.stat().st_size,
                json.dumps(receipt['source_signature']), json.dumps(signature(dest)), now, now + spec['days'] * 86400,
                'ready', spec['job_id'],str(archived_subtitle) if archived_subtitle else None,
                json.dumps(signature(archived_subtitle)) if archived_subtitle else None))
            return dict(db.execute('SELECT * FROM original_backups WHERE id=?', (spec['id'],)).fetchone())


def delivered(receipt, result, row):
    if not row:
        return result
    with store.db() as db:
        db.execute('UPDATE original_backups SET output_path=?,output_signature=? WHERE id=?',
                   (result['output_path'], json.dumps(result['output_signature']), row['id']))
        subtitle = Path(result['subtitle_path']) if result.get('subtitle_path') else None
        if subtitle and subtitle.is_file() and managed_path(subtitle) and subtitle.parent==Path(row['path']).parent:
            db.execute('UPDATE original_backups SET subtitle_path=?,subtitle_signature=? WHERE id=?',
                       (str(subtitle),json.dumps(signature(subtitle)),row['id']))
    return {**result, 'original_backup_id':row['id'], 'original_retained_until':row['expires']}


def summary():
    config = store.settings()
    active = [row for row in records() if valid_record(row)]
    return dict(enabled=config['retain_originals'], used_bytes=usage(), limit_bytes=config['original_storage_gb'] * 1024 ** 3,
                retained_count=len(active), days=config['original_retention_days'])
