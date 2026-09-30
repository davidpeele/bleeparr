"""Read legacy per-run logs without changing media or completion records."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def inspect_log(path):
    selected = None
    no_matches = False
    renamed = None
    examined = 0
    truncated = False
    with path.open(encoding='utf-8', errors='replace') as handle:
        for line in handle:
            examined += len(line)
            if '[INFO] Running Plex summary update' in line or line.startswith('Scanning library:'):
                break
            if examined > 8_000_000:
                truncated = True
                break
            if 'Extracted embedded subtitle' in line or 'Found existing subtitle:' in line or 'Downloaded and saved subtitle:' in line:
                selected = line.strip()
            if 'No bad words found in subtitles. Skipping Whisper and FFmpeg.' in line:
                no_matches = True
            if 'Renamed input file to:' in line:
                renamed = line.split('Renamed input file to:', 1)[1].strip()
    match = re.search(r'\.embedded\.([a-zA-Z]+)\.srt', selected or '')
    language = match.group(1).lower() if match else 'unknown'
    foreign = language not in ('eng', 'en', 'und', 'unknown')
    if no_matches or foreign or truncated:
        return dict(log=path.name, selected_subtitle=selected, declared_language=language,
                    foreign_declared=foreign, no_matches=no_matches, renamed_path=renamed,
                    truncated=truncated)


def audit(directory):
    records = []
    errors = []
    scanned = 0
    for path in sorted(Path(directory).glob('*.log')):
        if path.name == 'bleeparr_run.log':
            continue
        scanned += 1
        try:
            record = inspect_log(path)
            if record:
                records.append(record)
        except OSError as exc:
            errors.append(dict(log=path.name, error=str(exc)))
    return dict(logs_scanned=scanned, no_match_runs=sum(r['no_matches'] for r in records),
                foreign_no_match_runs=sum(r['foreign_declared'] and r['no_matches'] for r in records),
                foreign_languages=dict(Counter(r['declared_language'] for r in records if r['foreign_declared'])),
                records=records, errors=errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.log_dir), indent=2))
