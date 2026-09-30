"""Read-only completion audit; run inside Bleeparr with its existing DATA_DIR."""
import argparse
import json
import re
from backend import store, output


def audit():
    with store.db() as db:
        jobs = [dict(r) for r in db.execute("SELECT * FROM jobs WHERE status='completed' ORDER BY id")]
    rows = []
    missing = 0
    for job in jobs:
        result = json.loads(job['result'])
        path = store.data_dir()/'jobs'/str(job['id'])/'worker.log'
        missing += not path.exists()
        log = path.read_text(errors='replace') if path.exists() else ''
        errors = [line for line in log.splitlines() if re.search(
            r'unavailable.*fallback|speech model failed|metadata_errors|speech recognition failed', line, re.I)]
        fallback = result.get('fallback_sections', 0)
        if not fallback and not errors:
            continue
        finished = re.findall(r'Finished speech model ([^\n]+)', log)
        category = ('model_failure' if errors else 'speech_completed_with_fallback' if finished
                    else 'fallback_cause_unverified')
        current = bool(result.get('output_path') and result.get('output_signature') and
                       output.matches(result['output_path'], result['output_signature']))
        rows.append(dict(job_id=job['id'], kind=job['kind'], item_id=job['item_id'], parent_id=job['parent_id'],
                         title=job['title'], completed=job['updated'], category=category,
                         fallback_sections=fallback, candidate_sections=result.get('candidate_sections'),
                         mute_count=result.get('mute_count'), model_errors=errors, finished_models=finished,
                         log_present=path.exists(), current_output_matches=current,
                         output_path=result.get('output_path')))
    return dict(completed_jobs=len(jobs), missing_logs=missing, findings=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Optional JSON report path; does not alter the database or media')
    args = parser.parse_args()
    report = json.dumps(audit(), indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(report+'\n')
    else:
        print(report)
