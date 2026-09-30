import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse
import requests
from backend import store, plex, selection

STOP = threading.Event()
WAKE = threading.Event()
INFERENCE_LOCK = threading.Lock()
SCAN_LOCK = threading.Lock()
RETRYABLE_MEDIA = {'invalid_media'}


class Arr:
    def __init__(self, kind, config=None):
        if kind not in ('sonarr', 'radarr'):
            raise ValueError('Unknown media manager')
        self.kind = kind
        self.config = config or store.settings()
        self.url = self.config[kind + '_url'].rstrip('/')
        self.key = self.config[kind + '_api_key']
        parsed = urlparse(self.url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not self.key:
            raise ValueError(f'Configure a valid {kind.title()} URL and API key in Settings')

    def request(self, method, resource, **kwargs):
        try:
            response = requests.request(method, self.url + '/api/v3/' + resource, headers={'X-Api-Key': self.key}, timeout=(5, 30), allow_redirects=False, **kwargs)
            if response.status_code >= 300:
                raise ValueError(f'{self.kind.title()} returned HTTP {response.status_code}')
            return response.json() if response.content else {}
        except requests.RequestException:
            raise ValueError(f'{self.kind.title()} could not be reached') from None

    def library(self):
        return self.request('GET', 'series' if self.kind == 'sonarr' else 'movie')

    def files(self, item_id):
        if self.kind == 'radarr':
            movie = self.request('GET', f'movie/{item_id}')
            file = movie.get('movieFile')
            if file:
                file['_identity'] = dict(title=movie['title'], year=movie.get('year'),
                    runtime_seconds=(movie.get('runtime') or 0) * 60,
                    aliases=[a['title'] for a in movie.get('alternativeTitles', []) if a.get('title')])
            return [(item_id, movie['title'], file)] if file else []
        series = self.request('GET', f'series/{item_id}')
        episodes = self.request('GET', 'episode', params={'seriesId': item_id})
        files = {f['id']: f for f in self.request('GET', 'episodefile', params={'seriesId': item_id})}
        # Multi-episode files are processed once, using the file ID in the fingerprint.
        found = {}
        for ep in episodes:
            file = files.get(ep.get('episodeFileId'))
            if file and file['id'] not in found:
                file['_identity'] = dict(title=series['title'], year=series.get('year'),
                    season=ep['seasonNumber'], episode=ep['episodeNumber'],
                    runtime_seconds=(ep.get('runtime') or 0) * 60,
                    aliases=[a['title'] for a in series.get('alternateTitles', []) if a.get('title')])
                found.setdefault(file['id'], (ep['id'], f"{series['title']} · S{ep['seasonNumber']:02}E{ep['episodeNumber']:02}", file))
        return list(found.values())


def local_path(remote, kind, config):
    source, target = config[kind + '_path_from'], config[kind + '_path_to']
    path = Path(remote)
    if source:
        if not target:
            raise ValueError('Both path mapping fields must be set')
        try:
            path = Path(target) / path.relative_to(source)
        except ValueError:
            raise ValueError('Media path does not match the configured remote prefix') from None
    path = path.resolve()
    roots = [Path(p).resolve() for p in os.getenv('MEDIA_ROOTS', '/media').split(os.pathsep) if p]
    if not any(path.is_relative_to(root) for root in roots):
        raise ValueError('Media path is outside MEDIA_ROOTS; check volume mounts and path mapping')
    return path


def queue_item(kind, parent_id, config=None):
    config = config or store.settings()
    count = 0
    for item_id, title, file in Arr(kind, config).files(parent_id):
        if selection.audio_skip_reason(file):
            continue
        remote = file.get('path')
        if not remote:
            continue
        path = local_path(remote, kind, config)
        from backend import retention
        if retention.recovery_source(path):
            # Retained originals are available only through explicit Reprocess.
            continue
        from backend.output import recovery_input
        path = recovery_input(path)
        if not path.is_file():
            store.event(f'{title}: file is not visible inside Bleeparr; check path mapping')
            continue
        from backend.output import is_processed
        if is_processed(path):
            continue
        stat = path.stat()
        if time.time() - stat.st_mtime < 120:
            continue
        # Same physical file shared by episodes yields one job; upgraded releases get a new identity.
        identity = hashlib.sha256(repr((kind, str(path), stat.st_size, stat.st_mtime_ns)).encode()).hexdigest()
        count += store.enqueue(dict(fingerprint=identity, kind=kind, item_id=item_id, parent_id=parent_id,
                                   title=title, path=str(path), remote_path=remote, identity=file.get('_identity', {})))
    WAKE.set()
    return count


def scan():
    if not SCAN_LOCK.acquire(blocking=False):
        return 0
    try:
        config = store.settings()
        with store.db() as conn:
            selected = [dict(r) for r in conn.execute('SELECT * FROM monitored')]
        selected = {(item['kind'], item['item_id']): item for item in selected}
        if config.get('cleanvid_enabled'):
            for kind in ('sonarr', 'radarr'):
                if not config.get(kind + '_url') or not config.get(kind + '_api_key'):
                    continue
                try:
                    manual, excluded = selection.preferences(kind)
                    for item in Arr(kind, config).library():
                        if selection.state(item, config, manual, excluded) == 'cleanvid':
                            selected[(kind, item['id'])] = dict(kind=kind, item_id=item['id'], title=item['title'])
                except Exception as exc:
                    store.event(f'{kind.title()} automatic selection: {exc}')
        count = 0
        for item in selected.values():
            try:
                count += queue_item(item['kind'], item['item_id'], config)
            except Exception as exc:
                store.event(f"{item['title']}: {exc}")
        return count
    finally:
        SCAN_LOCK.release()


def request_search(job, config=None):
    """Bound searches without deleting or blocklisting library media automatically."""
    config = config or store.settings()
    if job['result'].get('error_code') not in RETRYABLE_MEDIA:
        raise ValueError('Alternative-release search is only offered for invalid media, not local processing failures')
    key = (job['kind'], job['item_id'])
    now = time.time()
    with store.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM searches WHERE kind=? AND item_id=?', key).fetchone()
        if row and now - row['requested'] < config['replacement_cooldown_hours'] * 3600:
            raise ValueError('A search was already requested within the cooldown period')
        # Reserve before network I/O: an ambiguous timeout must not cause repeated commands.
        conn.execute('INSERT OR REPLACE INTO searches VALUES (?,?,?,?)', (*key, now, 'requested'))
    name, id_key = ('EpisodeSearch', 'episodeIds') if job['kind'] == 'sonarr' else ('MoviesSearch', 'movieIds')
    try:
        response = Arr(job['kind'], config).request('POST', 'command', json={'name': name, id_key: [job['item_id']]})
    except Exception:
        store.event(f"{job['title']}: search failed or outcome unknown; cooldown retained")
        raise
    store.event(f"{job['title']}: search requested. Existing quality rules may prevent a replacement; no files deleted or release blocklisted.")
    return {'command_id': response.get('id'), 'message': 'Search requested; replacement depends on manager quality rules. Existing file retained.'}


def oom_kills():
    """Read the current container's cgroup v2 counter when available."""
    try:
        values = dict(line.split() for line in Path('/sys/fs/cgroup/memory.events').read_text().splitlines())
        return int(values['oom_kill'])
    except (OSError, ValueError, KeyError):
        return None


def worker_failure(returncode, before, after):
    if returncode == -signal.SIGKILL and before is not None and after is not None and after > before:
        code = 'out_of_memory'
        message = 'Worker was killed while the container reported an out-of-memory kill. Increase the memory allowance or select a smaller speech model; original retained.'
    else:
        code = 'worker_exit'
        reason = f'signal {-returncode}' if returncode < 0 else f'exit code {returncode}'
        message = f'Worker exited without a usable result ({reason}); original retained. See the processing log for preceding messages.'
    return {'success': False, 'error_code': code, 'error': message, 'returncode': returncode}


def refresh_renamed_media(result, job, config):
    kind = job.get('kind')
    if (result.get('output_mode') != 'replace' or result.get('output_path') == job['path']
            or kind not in ('sonarr', 'radarr') or not config.get(kind + '_url') or not config.get(kind + '_api_key')):
        return result
    command = {'name': 'RescanSeries', 'seriesId': job['parent_id']} if kind == 'sonarr' else {'name': 'RescanMovie', 'movieId': job['item_id']}
    try:
        Arr(kind, config).request('POST', 'command', json=command)
        result['library_refresh'] = 'requested'
    except ValueError as exc:
        result['library_refresh'] = 'failed'
        store.event(f"{job['title']}: cleaned file saved with its new name, but library refresh failed: {exc}")
    return result


def run_job(job, config):
    from backend import output as delivery
    from backend.retention import RetentionFull
    root = store.data_dir()
    job_dir = root / 'jobs' / str(job['id'])
    job_dir.mkdir(parents=True, exist_ok=True)
    words = job_dir / 'words.txt'
    words.write_text(config['swears'], encoding='utf-8')
    result_path = job_dir / 'result.json'
    cli = Path(os.getenv('BLEEPARR_CLI', '/app/cli/bleeparr.py'))
    receipt_path = job_dir / 'delivery.json'
    if receipt_path.exists():
        try:
            recovered = delivery.publish(json.loads(receipt_path.read_text()))
            recovered = refresh_renamed_media(recovered, job, config)
            delivery.write_receipt(result_path, recovered)
            return recovered
        except RetentionFull as exc:
            return {'success':False,'error_code':'original_storage_full','error':str(exc)}
        except (ValueError, OSError) as exc:
            return {'success': False, 'error_code': 'delivery_failed', 'error': str(exc)}
    try:
        delivery_job = dict(job)
        if config.get('output_mode') == 'replace' and job.get('remote_path') and job.get('kind'):
            managed = local_path(job['remote_path'], job['kind'], config)
            if managed != Path(job['path']).resolve() and delivery.recovery_input(managed) == Path(job['path']).resolve():
                delivery_job['replacement_path'] = str(managed)
        plan = delivery.plan(delivery_job, config)
    except RetentionFull as exc:
        return {'success':False,'error_code':'original_storage_full','error':str(exc)}
    except delivery.DestinationNotWritable as exc:
        return {'success': False, 'error_code': 'output_unwritable', 'error': str(exc)}
    except (ValueError, OSError) as exc:
        return {'success': False, 'error_code': 'output_configuration', 'error': str(exc)}
    output = Path(plan['stage'])
    if output.exists():
        return {'success': False, 'error_code': 'output_exists', 'error': 'Staged output needs review before retry; original retained'}
    result_path.unlink(missing_ok=True)
    command = [sys.executable, '-u', str(cli), '--input', job['path'], '--swears', str(words), '--output', str(output),
               '--result-json', str(result_path), '--temp-dir', str(job_dir), '--model', config['model'],
               '--fallback-model', config['fallback_model'], '--bleeptool', config['bleeptool'],
               '--cpu-threads', str(config['cpu_threads']), '--device', config['device'], '--compute-type', config['compute_type']]
    if config.get('verify_title', True) and job.get('item_id', 0) > 0:
        identity = job.get('identity') or {}
        if isinstance(identity, str):
            identity = json.loads(identity)
        if not identity:
            try:
                identity=next((file.get('_identity', {}) for item_id,_,file in Arr(job['kind'],config).files(job['parent_id'])
                               if item_id==job['item_id']),{})
            except ValueError:
                pass
        identity = identity or {'title':job['title'].split(' · ')[0]}
        command += ['--expected-identity', json.dumps(identity)]
    if config.get('check_subtitle_timing', True):
        command += ['--check-subtitle-timing']
    if config.get('review_broad_muting', True):
        command += ['--review-broad-muting']
    command += ['--max-fallback-percent', str(config.get('max_fallback_percent',25)),
                '--max-muted-percent', str(config.get('max_muted_percent',3)),
                '--max-fallback-seconds', str(config.get('max_fallback_seconds',10))]
    previous = job.get('result') or {}
    if isinstance(previous, str):
        previous = json.loads(previous)
    if previous.get('approved_review_token'):
        command += ['--muting-approval', previous['approved_review_token']]
    with (job_dir / 'worker.log').open('w') as log:
        memory_before = oom_kills()
        process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + int(os.getenv('JOB_TIMEOUT_SECONDS', '18000'))
        while process.poll() is None:
            if STOP.wait(.5) or time.monotonic() >= deadline:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                return {'success': False, 'error_code': 'interrupted' if STOP.is_set() else 'timeout', 'error': 'Processing interrupted or time limit reached; original retained'}
        try:
            result = json.loads(result_path.read_text())
        except (OSError, ValueError):
            result = worker_failure(process.returncode, memory_before, oom_kills())
        if process.returncode != 0:
            if result.get('success'):
                result = worker_failure(process.returncode, memory_before, oom_kills())
            result['success'] = False
        if not result.get('success'):
            print(f"Processing failed [{result.get('error_code', 'unknown')}]: {result.get('error', 'Unknown error')}", file=log, flush=True)
        if result.get('success') and result.get('outcome') in ('no_matches_found', 'skipped_language'):
            return result
        if result.get('success'):
            try:
                result = delivery.finish(plan, result, receipt_path)
                result = refresh_renamed_media(result, job, config)
                delivery.write_receipt(result_path, result)
            except RetentionFull as exc:
                return {'success':False,'error_code':'original_storage_full','error':str(exc)}
            except (ValueError, OSError) as exc:
                return {'success': False, 'error_code': 'delivery_failed', 'error': str(exc)}
        return result


def resume_writable_jobs(config):
    from backend import output
    with store.db() as conn:
        jobs = [dict(row) for row in conn.execute("SELECT * FROM jobs WHERE status='blocked'")]
    for job in jobs:
        if json.loads(job['result']).get('error_code') not in ('output_unwritable','original_storage_full'):
            continue
        try:
            output.plan(job, config)
        except (ValueError, OSError):
            continue
        with store.db() as conn:
            conn.execute("UPDATE jobs SET status='queued', attempts=0, next_try=0, result='{}' WHERE id=? AND status='blocked'", (job['id'],))
    if jobs:
        WAKE.set()


def process_next_job(config):
    if not INFERENCE_LOCK.acquire(blocking=False):
        return False
    try:
        job = store.claim(config['max_attempts'])
        if job:
            try:
                result = run_job(job, config)
            except Exception as exc:
                result = {'success': False, 'error_code': 'worker_error', 'error': str(exc)}
            status = store.finish(job, result, config)
            recovery_config = store.settings()
            if status == 'failed' and recovery_config.get('auto_blocklist') and result.get('error_code') in RETRYABLE_MEDIA:
                try:
                    from backend import replacement
                    replacement.request({**job, 'result': result}, recovery_config)
                except ValueError as exc:
                    store.event(f"{job['title']}: automatic replacement skipped: {exc}")
            elif status == 'failed' and config['auto_search'] and result.get('error_code') in RETRYABLE_MEDIA:
                try:
                    request_search({**job, 'result': result}, config)
                except Exception as exc:
                    store.event(str(exc))
            return True
        return False
    finally:
        INFERENCE_LOCK.release()


def worker():
    last_scan = 0
    last_plex_sync = 0
    last_cleanup = 0
    while not STOP.is_set():
        try:
            config = store.settings()
            if time.monotonic() - last_cleanup >= 300:
                from backend import retention
                retention.cleanup()
                last_cleanup = time.monotonic()
            if config['auto_process'] and time.monotonic() - last_scan >= config['poll_seconds']:
                last_scan = time.monotonic()
                resume_writable_jobs(config)
                scan()
            if config['plex_enabled'] and time.monotonic() - last_plex_sync >= 300:
                last_plex_sync = time.monotonic()
                try:
                    plex.sync(config)
                except ValueError:
                    pass  # Plex errors are tracked separately and never fail media jobs.
            if process_next_job(config):
                continue
        except Exception as exc:
            store.event(f'Worker error: {exc}')
        WAKE.wait(2)
        WAKE.clear()
