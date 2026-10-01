"""Durable queue and settings. A separate database leaves the legacy app's data intact."""
import json
import os
from pathlib import Path
import sqlite3
import time
from contextlib import contextmanager

DEFAULTS = dict(sonarr_url='', sonarr_api_key='', radarr_url='', radarr_api_key='',
                sonarr_path_from='', sonarr_path_to='', radarr_path_from='', radarr_path_to='',
                cleanvid_enabled=False, cleanvid_roots='', output_mode='separate', output_directory='', auto_process=False, poll_seconds=300, model='small.en', fallback_model='medium.en',
                bleeptool='S-M-FSM', cpu_threads=2, max_attempts=3, retry_minutes=60, download_subtitles=True,
                auto_search=False, auto_blocklist=False, replacement_limit=3, replacement_cooldown_hours=24, swears='damn\nshit\nfuck',
                device='cpu', compute_type='int8', plex_enabled=False, plex_url='', plex_token='',
                plex_libraries=[], plex_path_from='', plex_path_to='', plex_note='(Profanity removed by AI)',
                plex_series_note_enabled=True, plex_series_note='(Includes episodes with profanity removed)',
                email_enabled=False, notify_completed=True, notify_failed=True, notify_retry=False,
                smtp_host='', smtp_port=587, smtp_security='starttls', smtp_username='', smtp_password='',
                smtp_from='', smtp_to='')

DEFAULTS.update(verify_title=True, check_subtitle_timing=True, review_broad_muting=True,
                max_fallback_percent=25, max_muted_percent=3, max_fallback_seconds=10,
                retain_originals=False, original_retention_days=7, original_storage_gb=100)


def data_dir():
    path = Path(os.getenv('DATA_DIR', 'data'))
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def db():
    connection = sqlite3.connect(data_dir() / 'bleeparr-v3.sqlite3', timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init():
    with db() as conn:
        conn.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS monitored (kind TEXT, item_id INTEGER, title TEXT, PRIMARY KEY(kind,item_id));
        CREATE TABLE IF NOT EXISTS monitoring_exclusions (kind TEXT, item_id INTEGER, PRIMARY KEY(kind,item_id));
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, kind TEXT, item_id INTEGER, parent_id INTEGER,
            title TEXT, path TEXT, remote_path TEXT, status TEXT DEFAULT 'queued', attempts INTEGER DEFAULT 0,
            next_try REAL DEFAULT 0, created REAL, updated REAL, result TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS replacements (kind TEXT, download_id TEXT, item_id INTEGER, job_id INTEGER,
            history_id INTEGER, created REAL, status TEXT, release TEXT, PRIMARY KEY(kind,download_id));
        CREATE TABLE IF NOT EXISTS searches (kind TEXT, item_id INTEGER, requested REAL, status TEXT,
            PRIMARY KEY(kind,item_id));
        CREATE TABLE IF NOT EXISTS plex_updates (job_id INTEGER PRIMARY KEY, attempts INTEGER,
            next_try REAL, status TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS plex_notes (identity TEXT PRIMARY KEY, note TEXT);
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY, job_id INTEGER, event TEXT, subject TEXT, body TEXT, recipient TEXT,
            sender TEXT, message_id TEXT, status TEXT, attempts INTEGER, next_try REAL, created REAL,
            updated REAL, error TEXT DEFAULT '');
        CREATE INDEX IF NOT EXISTS notifications_due ON notifications(status,next_try);
        CREATE TABLE IF NOT EXISTS legacy_completions (path TEXT PRIMARY KEY, signature TEXT NOT NULL, recorded_success REAL);
        CREATE TABLE IF NOT EXISTS legacy_recovery_inputs (path TEXT PRIMARY KEY, signature TEXT NOT NULL, alternate_path TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS processed_outputs (path TEXT PRIMARY KEY, signature TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created REAL, message TEXT);
        ''')
        if 'identity' not in {row['name'] for row in conn.execute('PRAGMA table_info(jobs)')}:
            conn.execute("ALTER TABLE jobs ADD COLUMN identity TEXT NOT NULL DEFAULT '{}'")
        conn.execute('''CREATE TABLE IF NOT EXISTS original_backups (
            id TEXT PRIMARY KEY, source_path TEXT, path TEXT UNIQUE, size INTEGER,
            source_signature TEXT, signature TEXT, created REAL, expires REAL,
            status TEXT, output_path TEXT, output_signature TEXT, job_id INTEGER)''')
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(original_backups)')}
        for column in ('subtitle_path','subtitle_signature'):
            if column not in columns:
                conn.execute(f'ALTER TABLE original_backups ADD COLUMN {column} TEXT')
        for key, value in DEFAULTS.items():
            value = os.getenv(key.upper(), value) if key.endswith(('_url', '_api_key')) else value
            conn.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (key, json.dumps(value)))
        conn.execute("UPDATE notifications SET status='unknown',error='Delivery interrupted; email may already have been accepted. Review before retrying.' WHERE status='sending'")
        conn.execute("UPDATE jobs SET status='retry', next_try=?, result=? WHERE status='running'", (time.time(), json.dumps({'error': 'Worker interrupted; retry scheduled', 'error_code': 'interrupted'})))


def settings():
    with db() as conn:
        return {row['key']: json.loads(row['value']) for row in conn.execute('SELECT * FROM settings')}


def save_settings(values):
    with db() as conn:
        for key, value in values.items():
            conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))


def event(message):
    with db() as conn:
        conn.execute('INSERT INTO events(created,message) VALUES (?,?)', (time.time(), message))
        conn.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 200)')


def enqueue(item):
    now = time.time()
    with db() as conn:
        return conn.execute('''INSERT OR IGNORE INTO jobs(fingerprint,kind,item_id,parent_id,title,path,remote_path,created,updated,identity)
            VALUES (:fingerprint,:kind,:item_id,:parent_id,:title,:path,:remote_path,:created,:updated,:identity)''',
            {**item, 'identity':json.dumps(item.get('identity', {})), 'created': now, 'updated': now}).rowcount


def claim(max_attempts):
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT * FROM jobs WHERE status IN ('queued','retry') AND next_try<=? AND attempts<? ORDER BY next_try, id LIMIT 1", (time.time(), max_attempts)).fetchone()
        if row:
            conn.execute("UPDATE jobs SET status='running', attempts=attempts+1, updated=? WHERE id=?", (time.time(), row['id']))
            return {**dict(row), 'identity':json.loads(row['identity']), 'attempts': row['attempts'] + 1}


def finish(job, result, config):
    retryable = result.get('error_code') in {'subtitle_missing', 'timeout', 'busy', 'input_changed', 'input_missing', 'interrupted'}
    if result.get('success'):
        status = {'no_matches_found': 'no_matches', 'skipped_language': 'skipped'}.get(result.get('outcome'), 'completed')
    elif result.get('error_code') in {'output_unwritable','original_storage_full'}:
        status = 'blocked'
    elif result.get('error_code') in {'muting_review','title_review','subtitle_alignment_review'}:
        status = 'review'
    else:
        status = 'retry' if retryable and job['attempts'] < config['max_attempts'] else 'failed'
    from backend.notifications import enqueue as enqueue_notification
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        previous = conn.execute('SELECT status FROM jobs WHERE id=?', (job['id'],)).fetchone()
        if not previous or previous['status'] != 'running':
            return previous['status'] if previous else status
        conn.execute('UPDATE jobs SET status=?, result=?, next_try=?, updated=? WHERE id=?',
                     (status, json.dumps(result), time.time() + config['retry_minutes'] * 60 * 2 ** (job['attempts'] - 1), time.time(), job['id']))
        if status == 'completed' and result.get('output_signature'):
            conn.execute('INSERT OR REPLACE INTO processed_outputs VALUES (?,?)', (result['output_path'], json.dumps(result['output_signature'])))
        enqueue_notification(conn, job, result, status, config)
    return status


def jobs():
    with db() as conn:
        return [{**dict(row), 'result': json.loads(row['result']), 'identity':json.loads(row['identity'])} for row in conn.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 300')]
