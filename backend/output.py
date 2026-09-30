"""Publish validated CLI outputs, retaining a receipt for interrupted publication."""
import json
import os
import re
import tempfile
from pathlib import Path
from backend import store


class DestinationNotWritable(ValueError):
    pass


def cleaned_name(source, max_stem=None):
    stem = re.sub(r'(?:\s*\((?:edited by bleeparr|eddited by bleeparr|profanity removed)\))+$', '', source.stem, flags=re.I).rstrip()
    return (stem or source.stem)[:max_stem] + ' (profanity removed).mkv'


def signature(path):
    s = Path(path).stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def matches(path, expected):
    try:
        return signature(path) == expected
    except OSError:
        return False


def separate_root(config):
    root = Path(os.getenv('OUTPUT_DIR', str(store.data_dir() / 'cleaned'))).resolve()
    value = config.get('output_directory', '').strip()
    selected = (root / value).resolve() if value else root
    if not selected.is_relative_to(root):
        raise ValueError(f'Separate output folder must be inside {root}; mount your chosen storage there')
    return selected


def plan(job, config):
    from backend import retention
    source = Path(job['path']).resolve()
    mode = config.get('output_mode', 'separate')
    if mode == 'separate':
        dest = separate_root(config) / f"{job['fingerprint'][:16]}-{cleaned_name(source, 160)}"
    else:
        roots = [Path(p).resolve() for p in os.getenv('MEDIA_ROOTS', '/media').split(os.pathsep) if p]
        if not any(source.is_relative_to(p) for p in roots) and not retention.retained_source(source):
            raise ValueError('Source is outside the allowed media folders')
        dest = source.with_name(cleaned_name(source))
    if mode == 'alongside' and dest == source:
        raise ValueError('Source already has the profanity removed tag; use replacement or a separate output folder')
    target_signature = None
    recovery_target = None
    if mode == 'replace' and job.get('replacement_path'):
        target = Path(job['replacement_path']).resolve()
        if recovery_input(target) != source or target.suffix.lower() != '.mkv':
            raise ValueError('Recovery replacement target no longer matches the audited failed output')
        recovery_target = str(target)
        dest = target.with_name(cleaned_name(target))
        target_signature = signature(target)
    if dest != source and dest.exists() and str(dest) != recovery_target:
        raise ValueError('Cleaned destination already exists; choose another folder or review the existing file')
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Probe real filesystem permissions; os.access can be misleading inside containers.
    stage = dest.parent / f'.bleeparr-job-{job["fingerprint"]}.mkv'
    try:
        with tempfile.TemporaryFile(dir=dest.parent):
            pass
    except OSError as exc:
        raise DestinationNotWritable('Destination is not writable. Same-folder and replacement modes require a writable media mount.') from exc
    original_retention = retention.plan(source, signature(source), config, job.get('id')) if mode == 'replace' else None
    return dict(mode=mode, source=str(source), source_signature=signature(source), destination=str(dest), stage=str(stage),
                target_signature=target_signature, recovery_target=recovery_target, original_retention=original_retention,
                preserve_source=bool(retention.retained_source(source)))


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_receipt(path, receipt):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as f:
        json.dump(receipt, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    sync_directory(path.parent)


def publish(receipt):
    from backend import retention
    source = Path(receipt['source'])
    dest = Path(receipt['destination'])
    stage = Path(receipt['stage'])
    expected = receipt['cleaned_signature']
    target = Path(receipt.get('recovery_target') or dest)
    backup = retention.ensure(receipt)
    # Register before publication so a restart scan cannot enqueue our replacement.
    # A planned file is considered cleaned only when its actual signature matches.
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO processed_outputs VALUES (?,?)', (str(dest), json.dumps(expected)))
    if not matches(dest, expected):
        if not matches(stage, expected):
            raise ValueError('Validated cleaned file changed or is missing; original retained')
        if not matches(source, receipt['source_signature']):
            raise ValueError('Original changed during processing; replacement cancelled')
        if receipt.get('target_signature') and not matches(target, receipt['target_signature']):
            raise ValueError('Failed output changed during recovery; replacement cancelled')
        if receipt['mode'] == 'replace' and (dest == source or (receipt.get('target_signature') and dest == target)):
            os.replace(stage, dest)
        else:
            # Atomic no-clobber publication, including non-MKV replacement.
            os.link(stage, dest)
    sync_directory(dest.parent)
    if receipt['mode'] == 'replace' and dest != source and source.exists() and not receipt.get('preserve_source'):
        if not matches(source, receipt['source_signature']):
            raise ValueError('Original changed before deletion; both files retained for review')
        source.unlink()
        sync_directory(source.parent)
    if receipt['mode'] == 'replace' and receipt.get('target_signature') and target not in (source, dest) and target.exists():
        if not matches(target, receipt['target_signature']):
            raise ValueError('Failed output changed before deletion; cleaned and changed files retained for review')
        target.unlink()
        sync_directory(target.parent)
    if stage.exists() and matches(stage, expected):
        stage.unlink()
    result = {**receipt['result'], 'output_path': str(dest), 'output_mode': receipt['mode'], 'output_signature': expected}
    return retention.delivered(receipt, result, backup)


def finish(plan, result, receipt_path):
    source_stat = Path(plan['source']).stat()
    os.chmod(plan['stage'], source_stat.st_mode & 0o777)
    if os.geteuid() == 0:
        os.chown(plan['stage'], source_stat.st_uid, source_stat.st_gid)
    with open(plan['stage'], 'rb') as f:
        os.fsync(f.fileno())
    receipt = {**plan, 'result': result, 'cleaned_signature': signature(plan['stage'])}
    write_receipt(receipt_path, receipt)
    return publish(receipt)


def is_processed(path):
    with store.db() as db:
        row = db.execute('SELECT signature FROM processed_outputs WHERE path=?', (str(Path(path).resolve()),)).fetchone()
    if row and matches(path, json.loads(row['signature'])):
        return True
    with store.db() as db:
        legacy = db.execute('SELECT signature FROM legacy_completions WHERE path=?', (str(Path(path).resolve()),)).fetchone()
    return bool(legacy and matches(path, json.loads(legacy['signature'])))


def recovery_input(path):
    from backend import retention
    retained = retention.recovery_source(path)
    if retained:
        return retained
    with store.db() as db:
        row = db.execute('SELECT * FROM legacy_recovery_inputs WHERE path=?', (str(Path(path).resolve()),)).fetchone()
    if not row or not matches(path, json.loads(row['signature'])):
        return path
    alternate = Path(row['alternate_path']).resolve()
    roots = [Path(p).resolve() for p in os.getenv('MEDIA_ROOTS', '/media').split(os.pathsep) if p]
    if any(alternate.is_relative_to(root) for root in roots) and alternate.is_file():
        return alternate
    return path
