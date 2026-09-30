import pytest
from test_output import setup
from backend import store,output
from scripts.import_legacy_history import import_history


def test_import_keeps_media_and_queue_unchanged(setup):
    good=setup/'media'/'good.mkv';good.write_bytes(b'old success')
    bad=setup/'media'/'bad.mkv';bad.write_bytes(b'bad')
    original=setup/'media'/'original.mkv';original.write_bytes(b'original')
    changed=setup/'media'/'changed.mkv';changed.write_bytes(b'old');sig=output.signature(changed);changed.write_bytes(b'upgrade')
    report={'files':[
        dict(path=str(good),signature=output.signature(good),status='legacy_reported_success',recorded_success=123),
        dict(path=str(bad),signature=output.signature(bad),status='recorded_failure',alternate_path=str(original)),
        dict(path=str(changed),signature=sig,status='legacy_reported_success',recorded_success=123)]}
    assert import_history(report)==dict(imported=1,recovered=1,changed=1,accepted=0)
    assert output.is_processed(good) and not output.is_processed(bad)
    assert not output.is_processed(changed)
    assert output.recovery_input(bad)==original
    assert store.jobs()==[] and original.read_bytes()==b'original'
    # Later contrary evidence must remove an inherited success.
    report['files'][0]['status']='recorded_failure'
    import_history(report);assert not output.is_processed(good)


def test_import_requires_paused_processing(setup):
    store.save_settings({'auto_process':True})
    with pytest.raises(ValueError,match='Pause'):import_history({'files':[]})


def test_operator_acceptance_never_skips_failed_tagged_files(setup):
    rows=[]
    for name,status in [('old CleanedWithCleanVid.mkv','unprocessed_or_other_cleaner'),('old (edited by Bleeparr).mkv','no_success_record'),('bad (edited by Bleeparr).mkv','recorded_failure'),('raw.mkv','unprocessed_or_other_cleaner')]:
        p=setup/'media'/name;p.write_bytes(b'media')
        rows.append(dict(path=str(p),signature=output.signature(p),status=status))
    assert import_history({'files':rows})['imported']==0
    result=import_history({'files':rows},accept_tagged=True)
    assert result['imported']==2 and result['accepted']==2
    assert all(output.is_processed(r['path']) for r in rows[:2])
    assert not any(output.is_processed(r['path']) for r in rows[2:])
