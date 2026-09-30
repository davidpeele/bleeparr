import {useEffect, useState} from 'react';

export default function QualityControls({config, field, api}) {
  const [archive,setArchive] = useState(null);
  useEffect(()=>{api('/originals').then(setArchive).catch(()=>{});},[api]);
  return <>
    <section className="panel"><h2>Review before publishing</h2>
      <label className="check"><input type="checkbox" checked={config.verify_title ?? true} onChange={e=>field('verify_title',e.target.checked)}/> Check the downloaded title and runtime</label>
      <p className="help">Compare internal file details with the selected movie or episode. Missing internal details are reported; they cannot prove a file is the right title.</p>
      <label className="check"><input type="checkbox" checked={config.check_subtitle_timing ?? true} onChange={e=>field('check_subtitle_timing',e.target.checked)}/> Check subtitle text against sampled speech</label>
      <p className="help">Speech models check dialogue from several points in the program before cleaning. Uncertain or mismatched samples stop for review. Passing does not verify every subtitle.</p>
      <label className="check"><input type="checkbox" checked={config.review_broad_muting ?? true} onChange={e=>field('review_broad_muting',e.target.checked)}/> Hold unusually broad muting for review</label>
      <div className="form-grid">
        <label>Maximum whole-subtitle fallback (%)<input type="number" min="0" max="100" step="0.1" value={config.max_fallback_percent ?? 25} onChange={e=>field('max_fallback_percent',Number(e.target.value))}/><span className="help">Applies when at least three matching sections need fallback.</span></label>
        <label>Maximum portion of the program muted (%)<input type="number" min="0" max="100" step="0.1" value={config.max_muted_percent ?? 3} onChange={e=>field('max_muted_percent',Number(e.target.value))}/></label>
        <label>Maximum whole-subtitle mute (seconds)<input type="number" min="0.1" max="120" step="0.1" value={config.max_fallback_seconds ?? 10} onChange={e=>field('max_fallback_seconds',Number(e.target.value))}/></label>
      </div><p className="help">Held files keep their original audio. Activity shows the planned mute duration and reasons. Approval applies to one unchanged result.</p>
    </section>
    <section className="panel"><h2>Temporary originals</h2>
      <label className="check"><input type="checkbox" checked={config.retain_originals ?? false} onChange={e=>field('retain_originals',e.target.checked)}/> Retain unmuted originals when replacing files</label>
      <p>Off by default. When enabled, an original is verified in the archive before its cleaned replacement is published. Reprocess can use that original while it remains available.</p>
      <div className="form-grid"><label>Keep for (days)<input type="number" min="1" max="90" value={config.original_retention_days ?? 7} onChange={e=>field('original_retention_days',Number(e.target.value))}/></label>
      <label>Archive limit (GB)<input type="number" min="1" max="10000" value={config.original_storage_gb ?? 100} onChange={e=>field('original_storage_gb',Number(e.target.value))}/></label></div>
      {archive && <p>{archive.retained_count} originals retained · {(archive.used_bytes/1024**3).toFixed(1)} GB used</p>}
      <p className="help">An archive at its limit holds new replacements for attention. Originals expire after their retention period; changed backups are preserved for review. Save changes before the next job starts.</p>
    </section>
  </>;
}
