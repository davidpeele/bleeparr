"""Library presentation: manager metadata and current Bleeparr history."""
import json
import os
from collections import defaultdict
from pathlib import Path
from backend import store, selection, service, output


def library(kind):
    config = store.settings()
    manual, excluded = selection.preferences(kind)
    with store.db() as conn:
        jobs = [dict(row) for row in conn.execute('SELECT * FROM jobs WHERE kind=? ORDER BY id DESC', (kind,))]
        records = list(conn.execute('SELECT path, signature FROM processed_outputs UNION SELECT path, signature FROM legacy_completions'))
    cleaned = set()
    for row in records:
        try:
            if output.matches(row['path'], json.loads(row['signature'])):
                cleaned.add(Path(row['path']))
        except (ValueError, OSError):
            continue
    by_folder = defaultdict(set)
    for path in cleaned:
        for parent in path.parents:
            by_folder[parent].add(path)
    flags = defaultdict(set)
    outputs = defaultdict(set)
    seen = set()
    for job in jobs:
        title_id = job['parent_id'] if kind == 'sonarr' else job['item_id']
        identity = (title_id, job['path'])
        if identity in seen:
            continue
        seen.add(identity)
        if job['status'] in ('queued', 'retry', 'running', 'failed', 'blocked'):
            flags[title_id].add('queued' if job['status'] == 'retry' else job['status'])
        result = json.loads(job['result'])
        if job['status'] in ('no_matches', 'skipped'):
            flags[title_id].add(job['status'])
        dest = result.get('output_path')
        if job['status'] == 'completed' and dest and Path(dest) in cleaned:
            outputs[title_id].add(Path(dest))
    result = []
    for item in service.Arr(kind).library():
        item_flags = set(flags[item['id']])
        done = set(outputs[item['id']])
        try:
            # Presentation only: avoid filesystem traversal for every library title.
            # Job submission still validates real paths and allowed mounts.
            root = Path(item['path'])
            prefix = config[kind + '_path_from']
            if prefix:
                root = Path(config[kind + '_path_to']) / root.relative_to(prefix)
            root = Path(os.path.normpath(root))
            done.update(by_folder.get(root, set()))
        except (KeyError, ValueError, OSError):
            pass
        if done:
            item_flags.add('processed')
        elif not item_flags:
            item_flags.add('unprocessed')
        source = selection.state(item, config, manual, excluded)
        reason = selection.skip_reason(item)
        if reason:
            item_flags.discard('unprocessed')
            item_flags.add('skipped')
        result.append(dict(id=item['id'], title=item['title'], year=item.get('year'),
                           status=item.get('status'), path=item.get('path'),
                           content_rating=(item.get('certification') or '').strip() or 'Not rated',
                           added=item.get('added'), selected=source in ('manual', 'cleanvid'),
                           monitoring_source=source, skip_reason=reason, processing_states=sorted(item_flags),
                           processed_files=len(done),
                           available=item.get('hasFile', item.get('statistics', {}).get('episodeFileCount', 0))))
    return result
