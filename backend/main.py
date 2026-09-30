from contextlib import asynccontextmanager
import fcntl
import hmac
import json
import os
import re
from pathlib import Path
import threading
import time
import uuid
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from backend import store, service, plex, notifications, selection
from cli.bleeparr import tokens, ProcessingError


@asynccontextmanager
async def lifespan(app):
    lock = (store.data_dir() / 'worker.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError('Another Bleeparr worker is already using this data directory')
    store.init()
    service.STOP.clear()
    thread = None
    mail_thread = None
    if os.getenv('DISABLE_WORKER') != '1':
        thread = threading.Thread(target=service.worker, daemon=True)
        thread.start()
        mail_thread = threading.Thread(target=notifications.worker, args=(service.STOP,), daemon=True)
        mail_thread.start()
    try:
        yield
    finally:
        service.STOP.set()
        service.WAKE.set()
        if thread:
            thread.join(timeout=45)
        if mail_thread:
            mail_thread.join(timeout=25)
        lock.close()


app = FastAPI(title='Bleeparr', version='3.0.0', lifespan=lifespan)


@app.middleware('http')
async def protect(request: Request, call_next):
    if request.url.path.startswith('/api/') and request.url.path != '/api/health':
        token = os.getenv('BLEEPARR_TOKEN', '')
        if token and not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + token):
            return JSONResponse({'detail': 'Enter your Bleeparr access token'}, status_code=401)
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD') and origin and urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Cross-origin changes are not allowed'}, status_code=403)
    return await call_next(request)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=400)


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sonarr_url: str = ''
    sonarr_api_key: str = ''
    radarr_url: str = ''
    radarr_api_key: str = ''
    sonarr_path_from: str = ''
    sonarr_path_to: str = ''
    radarr_path_from: str = ''
    radarr_path_to: str = ''
    plex_enabled: bool = False
    plex_url: str = ''
    plex_token: str = ''
    plex_libraries: list[int] = Field(default_factory=list, max_length=50)
    plex_path_from: str = ''
    plex_path_to: str = ''
    plex_note: str = Field(default='(Profanity removed by AI)', min_length=1, max_length=300)
    plex_series_note_enabled: bool = True
    plex_series_note: str = Field(default='(Includes episodes with profanity removed)', min_length=1, max_length=300)
    email_enabled: bool = False
    notify_completed: bool = True
    notify_failed: bool = True
    notify_retry: bool = False
    smtp_host: str = Field(default='', max_length=253)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal['starttls','ssl','none'] = 'starttls'
    smtp_username: str = Field(default='', max_length=320)
    smtp_password: str = Field(default='', max_length=1000)
    smtp_from: str = Field(default='', max_length=254)
    smtp_to: str = Field(default='', max_length=254)
    cleanvid_enabled: bool = False
    cleanvid_roots: str = Field(default='', max_length=10000)
    output_mode: Literal['separate', 'alongside', 'replace'] = 'separate'
    output_directory: str = Field(default='', max_length=1000)
    auto_process: bool = False
    poll_seconds: int = Field(default=300, ge=60, le=86400)
    model: str = Field(default='small.en', min_length=1, max_length=200)
    fallback_model: str = Field(default='medium.en', min_length=1, max_length=200)
    bleeptool: Literal['S-FSM', 'S-M-FSM', 'S-M', 'FSM'] = 'S-M-FSM'
    cpu_threads: int = Field(default=2, ge=1, le=32)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_minutes: int = Field(default=60, ge=1, le=1440)
    auto_search: bool = False
    auto_blocklist: bool = False
    replacement_limit: int = Field(default=3, ge=1, le=10)
    replacement_cooldown_hours: int = Field(default=24, ge=24, le=720)
    swears: str = Field(default='damn\nshit\nfuck', min_length=1, max_length=100000)
    device: Literal['cpu', 'cuda', 'auto'] = 'cpu'
    compute_type: Literal['int8', 'float32', 'float16', 'int8_float16'] = 'int8'
    verify_title: bool = True
    check_subtitle_timing: bool = True
    review_broad_muting: bool = True
    max_fallback_percent: float = Field(default=25, ge=0, le=100)
    max_muted_percent: float = Field(default=3, ge=0, le=100)
    max_fallback_seconds: float = Field(default=10, gt=0, le=120)
    retain_originals: bool = False
    original_retention_days: int = Field(default=7, ge=1, le=90)
    original_storage_gb: int = Field(default=100, ge=1, le=10000)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/speech-readiness')
def speech_readiness():
    from backend import speech_health
    return speech_health.status()


@app.post('/api/speech-readiness')
def check_speech_readiness():
    from backend import speech_health
    return speech_health.start()


@app.get('/api/originals')
def originals():
    from backend import retention
    return retention.summary()


@app.get('/api/settings')
def settings():
    config = store.settings()
    for kind in ('sonarr', 'radarr'):
        config[kind + '_key_configured'] = bool(config[kind + '_api_key'])
        config[kind + '_api_key'] = ''
    config['plex_token_configured'] = bool(config['plex_token'])
    config['plex_token'] = ''
    config['smtp_password_configured'] = bool(config['smtp_password'])
    config['smtp_password'] = ''
    return config


@app.put('/api/settings')
def save_settings(body: Settings):
    values = body.model_dump(exclude_unset=True)
    for key in ('sonarr_api_key', 'radarr_api_key', 'plex_token', 'smtp_password'):
        if values.get(key) == '':
            values.pop(key, None)  # blank preserves an existing secret
    merged = {**store.settings(), **values}
    for kind in ('sonarr', 'radarr', 'plex'):
        if merged[kind + '_url']:
            parsed = urlparse(merged[kind + '_url'])
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Use a plain HTTP(S) manager URL without credentials or query parameters')
        if bool(merged[kind + '_path_from']) != bool(merged[kind + '_path_to']):
            raise ValueError('Fill in both path mapping fields or leave both blank')
    for key in ('plex_note', 'plex_series_note'):
        if not merged[key].strip() or '\n' in merged[key] or '\r' in merged[key]:
            raise ValueError('Plex notes must be a nonempty single line')
        if key in values:
            values[key] = values[key].strip()
    if any(i <= 0 for i in merged['plex_libraries']):
        raise ValueError('Plex library IDs must be positive')
    if merged['plex_enabled'] and not (merged['plex_url'] and merged['plex_token'] and merged['plex_libraries']):
        raise ValueError('Connect Plex and select libraries before enabling synopsis updates')
    for key in ('smtp_host', 'smtp_username', 'smtp_from', 'smtp_to'):
        if '\r' in merged[key] or '\n' in merged[key]:
            raise ValueError('Email settings cannot contain line breaks')
    if merged['smtp_host'] and not re.fullmatch(r'[A-Za-z0-9_.:-]+', merged['smtp_host']):
        raise ValueError('Enter an SMTP hostname or IP address without a URL or port')
    for key in ('smtp_from', 'smtp_to'):
        if merged[key] and not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+', merged[key]):
            raise ValueError('Use one plain email address for sender and recipient')
    if merged['smtp_security'] == 'none' and merged['smtp_username']:
        raise ValueError('Use STARTTLS or TLS when sending SMTP credentials')
    if merged['email_enabled'] and not all(merged[key] for key in ('smtp_host','smtp_from','smtp_to')):
        raise ValueError('Set the mail server, sender and recipient before enabling email')
    paths = [p.strip() for p in merged['cleanvid_roots'].splitlines() if p.strip()]
    if merged['cleanvid_enabled'] and not paths:
        raise ValueError('Enter at least one CleanVid folder')
    if any(not p.startswith('/') or p.strip('/') == '' or '..' in p.split('/') or '\\' in p for p in paths):
        raise ValueError('CleanVid folders must be absolute manager paths, without parent-directory traversal or a filesystem root')
    from backend.output import separate_root
    separate_root(merged)
    words = [w.strip() for w in merged['swears'].splitlines() if w.strip() and not w.lstrip().startswith('#')]
    if not words or any(not tokens(w) for w in words):
        raise ValueError('Enter one word or phrase per line, containing at least one word')
    store.save_settings(values)
    service.WAKE.set()
    return {'saved': True}


@app.post('/api/plex/test')
def test_plex():
    return {'libraries': plex.libraries(store.settings()), 'message': 'Connected to Plex; choose the libraries to update'}


@app.post('/api/plex/sync')
def sync_plex():
    return plex.sync(manual=True)


@app.get('/api/notifications')
def notification_history():
    return {'items': notifications.history(), 'worker_enabled': os.getenv('DISABLE_WORKER') != '1'}


@app.post('/api/notifications/test')
def test_notification():
    result = notifications.queue_test()
    if os.getenv('DISABLE_WORKER') == '1':
        result['message'] += ' Sending is paused in this local preview.'
    return result


@app.post('/api/notifications/{notification_id}/retry')
def retry_notification(notification_id: str):
    return notifications.retry(notification_id)


Kind = Literal['sonarr', 'radarr']


@app.post('/api/connections/{kind}/test')
def test_connection(kind: Kind):
    result = service.Arr(kind).request('GET', 'system/status')
    return {'connected': True, 'version': result.get('version')}


@app.get('/api/library/{kind}')
def library(kind: Kind):
    from backend import catalog
    return catalog.library(kind)


@app.get('/api/monitoring/preview')
def monitoring_preview():
    config = store.settings()
    result = {'items': [], 'errors': [], 'auto_process': config['auto_process']}
    for kind in ('sonarr', 'radarr'):
        if not config[kind + '_url'] or not config[kind + '_api_key']:
            continue
        try:
            manual, excluded = selection.preferences(kind)
            for item in service.Arr(kind).library():
                if selection.matches(item, config):
                    result['items'].append(dict(kind=kind, id=item['id'], title=item['title'], path=item['path'],
                                               monitoring_source=selection.state(item, config, manual, excluded)))
        except ValueError as exc:
            result['errors'].append(str(exc))
    return result


class Monitor(BaseModel):
    enabled: bool


@app.put('/api/library/{kind}/{item_id}/monitor')
def monitor(kind: Kind, item_id: int, body: Monitor):
    api = service.Arr(kind)
    item = api.request('GET', ('series/' if kind == 'sonarr' else 'movie/') + str(item_id))
    if body.enabled and selection.skip_reason(item):
        raise HTTPException(400, selection.skip_reason(item))
    with store.db() as conn:
        if body.enabled:
            conn.execute('DELETE FROM monitoring_exclusions WHERE kind=? AND item_id=?', (kind, item_id))
            conn.execute('INSERT OR REPLACE INTO monitored VALUES (?,?,?)', (kind, item_id, item['title']))
        else:
            conn.execute('DELETE FROM monitored WHERE kind=? AND item_id=?', (kind, item_id))
            conn.execute('INSERT OR IGNORE INTO monitoring_exclusions VALUES (?,?)', (kind, item_id))
    return {'monitored': body.enabled}


@app.post('/api/library/{kind}/{item_id}/queue')
def queue(kind: Kind, item_id: int):
    count = service.queue_item(kind, item_id)
    return {'queued': count, 'message': f'{count} new file(s) queued. Files must be mounted, stable, and not already queued. Known non-English audio is skipped.'}


@app.get('/api/discover/{kind}')
def discover(kind: Kind, term: str):
    if len(term.strip()) < 2:
        raise ValueError('Enter at least two characters')
    resource = 'series/lookup' if kind == 'sonarr' else 'movie/lookup'
    results = service.Arr(kind).request('GET', resource, params={'term': term})
    return [{'title': r['title'], 'year': r.get('year'), 'external_id': r.get('tvdbId' if kind == 'sonarr' else 'tmdbId'),
             'overview': r.get('overview', '')[:400]} for r in results][:30]


@app.get('/api/options/{kind}')
def options(kind: Kind):
    api = service.Arr(kind)
    return {'profiles': api.request('GET', 'qualityprofile'), 'roots': api.request('GET', 'rootfolder')}


class AddTitle(BaseModel):
    external_id: int = Field(gt=0)
    quality_profile_id: int = Field(gt=0)
    root_folder: str
    search: bool = False


@app.post('/api/discover/{kind}')
def add_title(kind: Kind, body: AddTitle):
    api = service.Arr(kind)
    resource = 'series' if kind == 'sonarr' else 'movie'
    prefix = 'tvdb' if kind == 'sonarr' else 'tmdb'
    id_key = 'tvdbId' if kind == 'sonarr' else 'tmdbId'
    candidates = api.request('GET', resource + '/lookup', params={'term': f'{prefix}:{body.external_id}'})
    item = next((r for r in candidates if r.get(id_key) == body.external_id), None)
    if not item:
        raise ValueError('Title no longer exists in manager lookup')
    opts = options(kind)
    if body.quality_profile_id not in {p['id'] for p in opts['profiles']} or body.root_folder not in {r['path'] for r in opts['roots']}:
        raise ValueError('Choose a valid quality profile and root folder')
    item.update(qualityProfileId=body.quality_profile_id, rootFolderPath=body.root_folder, monitored=True)
    item.pop('id', None)
    item.pop('path', None)
    item['addOptions'] = {'searchForMissingEpisodes': body.search} if kind == 'sonarr' else {'searchForMovie': body.search}
    if kind == 'sonarr':
        item['seasonFolder'] = True
        for season in item.get('seasons', []):
            season['monitored'] = season.get('seasonNumber', 0) > 0
    added = api.request('POST', resource, json=item)
    with store.db() as conn:
        conn.execute('INSERT OR REPLACE INTO monitored VALUES (?,?,?)', (kind, added['id'], added['title']))
    return {'added': True, 'title': added['title']}


@app.get('/api/status')
def status():
    jobs = store.jobs()
    with store.db() as conn:
        events = [dict(r) for r in conn.execute('SELECT * FROM events ORDER BY id DESC LIMIT 20')]
        counts = {r['status']: r['n'] for r in conn.execute('SELECT status, count(*) AS n FROM jobs GROUP BY status')}
    return {'jobs': jobs, 'counts': counts, 'events': events, 'auto_process': store.settings()['auto_process'], 'auto_blocklist': store.settings()['auto_blocklist']}


@app.post('/api/scan')
def scan():
    return {'queued': service.scan()}


@app.post('/api/jobs/{job_id}/retry')
def retry(job_id: int):
    with store.db() as conn:
        if not conn.execute("UPDATE jobs SET status='queued', attempts=0, next_try=0 WHERE id=? AND status IN ('failed','retry','blocked','no_matches','review')", (job_id,)).rowcount:
            raise HTTPException(409, 'Only failed, blocked, review, no-match or waiting jobs can be retried')
    service.WAKE.set()
    return {'queued': True}


class MutingApproval(BaseModel):
    token: str = Field(pattern='^[a-f0-9]{64}$')


@app.post('/api/jobs/{job_id}/approve-muting')
def approve_muting(job_id: int, body: MutingApproval):
    from backend import output
    with store.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        result = json.loads(row['result']) if row else {}
        if not row or row['status']!='review' or result.get('error_code')!='muting_review' or result.get('review_token')!=body.token:
            raise HTTPException(409,'This muting review changed or is no longer awaiting approval.')
        if not output.matches(row['path'],result.get('review_source_signature')):
            raise HTTPException(409,'The source changed; retry analysis before approving.')
        backup=store.data_dir()/'audits'/f'muting-approval-{job_id}-{uuid.uuid4().hex}.json'
        backup.parent.mkdir(parents=True,exist_ok=True);output.write_receipt(backup,dict(row))
        result['approved_review_token']=body.token
        conn.execute("UPDATE jobs SET status='queued',attempts=0,next_try=0,result=?,updated=? WHERE id=?",
                     (json.dumps(result),time.time(),job_id))
    service.WAKE.set()
    return {'message':'Only this reviewed muting plan approved. The source and analysis must still match before publication.'}


class ReprocessRequest(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]+$')


@app.get('/api/jobs/{job_id}/reprocess-preview')
def reprocess_preview(job_id: int):
    from backend import reprocessing
    try:
        return reprocessing.preview(job_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except ProcessingError as exc:
        raise HTTPException(409, str(exc)) from None


@app.post('/api/jobs/{job_id}/reprocess')
def reprocess(job_id: int, body: ReprocessRequest):
    from backend import reprocessing
    try:
        return reprocessing.enqueue(job_id, body.fingerprint)
    except (ValueError, ProcessingError) as exc:
        raise HTTPException(409, str(exc)) from None


@app.post('/api/jobs/{job_id}/search')
def search(job_id: int):
    job = next((j for j in store.jobs() if j['id'] == job_id), None)
    if not job or job['status'] != 'failed':
        raise HTTPException(404, 'Failed job not found')
    return service.request_search(job)


@app.get('/api/jobs/{job_id}/replacement-preview')
def replacement_preview(job_id: int):
    from backend import replacement
    job = next((j for j in store.jobs() if j['id'] == job_id), None)
    if not job or job['status'] != 'failed':
        raise HTTPException(404, 'Failed job not found')
    plan = replacement.prepare(job, store.settings())
    return {'release': plan['release'], 'message': 'Download history matched. No changes made.'}


@app.post('/api/jobs/{job_id}/replacement')
def replace_release(job_id: int):
    from backend import replacement
    job = next((j for j in store.jobs() if j['id'] == job_id), None)
    if not job or job['status'] != 'failed':
        raise HTTPException(404, 'Failed job not found')
    return replacement.request(job)


@app.get('/api/jobs/{job_id}/log')
def job_log(job_id: int):
    job = next((j for j in store.jobs() if j['id'] == job_id), None)
    result = (job or {}).get('result') or {}
    prefix = f"Processing failed [{result.get('error_code', 'unknown')}]: {result['error']}\n\n" if result.get('error') else ''
    path = store.data_dir() / 'jobs' / str(job_id) / 'worker.log'
    if not path.is_file():
        return {'log': prefix + 'No log yet'}
    with path.open('rb') as handle:
        handle.seek(max(0, path.stat().st_size - 32000))
        return {'log': prefix + handle.read().decode('utf-8', errors='replace')}


static = Path(os.getenv('FRONTEND_DIR', str(Path(__file__).parents[1] / 'frontend' / 'dist')))
if (static / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=static / 'assets'), name='assets')


@app.get('/')
def index():
    if not (static / 'index.html').exists():
        return JSONResponse({'detail': 'Build the frontend first, or use its development server'}, status_code=503)
    return FileResponse(static / 'index.html')
