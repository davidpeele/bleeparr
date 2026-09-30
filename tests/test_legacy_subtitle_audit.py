from scripts.audit_legacy_subtitles import audit


def test_audit_distinguishes_foreign_no_match_from_failed_rename_and_plex_debug(tmp_path):
    (tmp_path/'one.log').write_text('Extracted embedded subtitle → /tmp/Lanterns.embedded.fre.srt\nNo bad words found in subtitles. Skipping Whisper and FFmpeg.\nRenamed input file to: /media/Lanterns (edited by Bleeparr).mkv\n[INFO] Running Plex summary update...\nFound existing subtitle: /other/movie.en.srt\n')
    (tmp_path/'two.log').write_text('Extracted embedded subtitle → /tmp/Night Agent.embedded.fre.srt\nNo bad words found in subtitles. Skipping Whisper and FFmpeg.\nPermissionError: rename failed\n')
    (tmp_path/'three.log').write_text('[INFO] Running Plex summary update...\nNo bad words found in subtitles. Skipping Whisper and FFmpeg.\n')
    (tmp_path/'bleeparr_run.log').write_text('scheduler')
    result=audit(tmp_path)
    assert result['logs_scanned']==3 and result['no_match_runs']==2
    assert result['foreign_no_match_runs']==2
    one,two=result['records']
    assert one['renamed_path']=='/media/Lanterns (edited by Bleeparr).mkv'
    assert two['renamed_path'] is None
    assert one['declared_language']=='fre'
    assert result['errors']==[]
