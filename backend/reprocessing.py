"""Preview and queue one manager episode/file, preserving previous completion evidence."""
import hashlib
import json
import tempfile
import time
import uuid
from pathlib import Path
from backend import store, service, selection, output
from cli import bleeparr as cli


def preview(job_id):
    with store.db() as db:
        row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not row or row['item_id']<=0:
        raise ValueError('A manager episode or movie job is required')
    job=dict(row)
    if job['status']=='running':
        raise ValueError('This job is already processing')
    config=store.settings()
    files=[item for item in service.Arr(job['kind'],config).files(job['parent_id']) if item[0]==job['item_id']]
    if len(files)!=1:
        raise ValueError('The manager does not identify one current file for this episode/movie')
    item_id,title,file=files[0]
    managed=service.local_path(file['path'],job['kind'],config)
    source=output.recovery_input(managed)
    result=dict(eligible=False,title=title,source=str(source),kind=job['kind'],item_id=item_id,parent_id=job['parent_id'],remote_path=file['path'],
                identity=file.get('_identity', {}), retained_original=source != managed)
    if selection.audio_skip_reason(file):
        return {**result,'reason':selection.audio_skip_reason(file)}
    if not source.is_file():
        return {**result,'reason':'The current manager file is not mounted in Bleeparr.'}
    if output.is_processed(source) or source.name.lower().endswith(('(profanity removed).mkv','(edited by bleeparr).mkv','(eddited by bleeparr).mkv')):
        return {**result,'reason':'This is an already cleaned copy. Muted audio cannot be restored by processing again. Download a fresh copy in Sonarr/Radarr, then reopen this preview.'}
    stat=source.stat()
    if time.time()-stat.st_mtime<120:
        return {**result,'reason':'Wait until the new file has been stable for two minutes.'}
    fingerprint=hashlib.sha256(repr((job['kind'],str(source),stat.st_size,stat.st_mtime_ns)).encode()).hexdigest()
    with store.db() as db:
        active=db.execute("SELECT id FROM jobs WHERE fingerprint=? AND status IN ('queued','retry','running')",(fingerprint,)).fetchone()
    if active:
        return {**result,'reason':f'This file is already queued or processing as job {active[0]}.'}
    delivery_job=dict(job,path=str(source),fingerprint=fingerprint)
    if source != managed and config['output_mode']=='replace':
        delivery_job['replacement_path']=str(managed)
    output.plan(delivery_job,config)
    data,duration=cli.probe(source)
    if config.get('verify_title',True):
        from cli import quality
        try:
            quality.identity(data,duration,file.get('_identity') or {'title':title.split(' · ')[0]})
        except quality.QualityReview as exc:
            raise cli.ProcessingError(exc.code,str(exc),exc.details) from exc
    audio=cli.select_audio(data,'eng')
    args=cli.parser().parse_args(['--input',str(source),'--no-download-subs'])
    with tempfile.TemporaryDirectory(prefix='reprocess-preview-',dir=store.data_dir()) as scratch:
        subtitle,chosen=cli.resolve_subtitle(args,data,Path(scratch))
        subtitles,report=cli.inspect_subtitles(subtitle,'eng',duration,chosen)
        counts=cli.match_counts(cli.matching_sections(subtitles,{' '.join(cli.tokens(word)) for word in config['swears'].splitlines() if cli.tokens(word)},duration))
    if output.signature(source)!=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns]:
        raise ValueError('The source changed during preview; refresh and review again')
    return {**result,**report,**counts,'eligible':True,'fingerprint':fingerprint,'audio_stream':audio,
            'reason':'Queue only this episode/movie using the current speech strategy. Original retained until output validation passes.'}


def enqueue(job_id,expected):
    plan=preview(job_id)
    if not plan['eligible']:
        raise ValueError(plan['reason'])
    if plan['fingerprint']!=expected:
        raise ValueError('The source changed since preview; refresh and review again')
    backup=store.data_dir()/'audits'/f'reprocess-{uuid.uuid4().hex}.json'
    backup.parent.mkdir(parents=True,exist_ok=True)
    now=time.time()
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM jobs WHERE fingerprint=?',(expected,)).fetchone()
        reviewed=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if previous and previous['status'] in ('queued','retry','running'):
            raise ValueError('This file is already queued or processing')
        previous_directory=store.data_dir()/'jobs'/str(previous['id']) if previous else None
        archived_directory=backup.with_suffix('') if previous_directory and previous_directory.exists() else None
        output.write_receipt(backup,dict(reviewed_job=dict(reviewed),previous_source_job=dict(previous) if previous else None,
                                        previous_artifacts=str(archived_directory) if archived_directory else None))
        if previous:
            # A fresh analysis must not resume an earlier delivery receipt.
            if archived_directory:
                previous_directory.rename(archived_directory)
            db.execute("UPDATE jobs SET status='queued',attempts=0,next_try=0,result='{}',identity=?,updated=? WHERE id=?",
                       (json.dumps(plan['identity']),now,previous['id']))
            queued=previous['id']
        else:
            queued=db.execute('INSERT INTO jobs(fingerprint,kind,item_id,parent_id,title,path,remote_path,created,updated,identity) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (expected,plan['kind'],plan['item_id'],plan['parent_id'],plan['title'],plan['source'],plan['remote_path'],now,now,
                 json.dumps(plan['identity']))).lastrowid
    service.WAKE.set()
    store.event(f'{plan["title"]}: targeted reprocessing queued as job {queued}; previous job evidence backed up.')
    return dict(job_id=queued,message=f'Only {plan["title"]} queued for reprocessing as job {queued}.')
