import {useState} from 'react';

export default function QualitySummary({result={}}) {
  const [showDialogue,setShowDialogue]=useState(true);
  const title=result.title_verification, timing=result.subtitle_alignment, muting=result.muting_review, attempts=result.subtitle_attempts;
  if (!title && !timing && !muting && !attempts?.length && !result.original_retained_until) return null;
  const time=seconds=>`${Math.floor(seconds/3600)}:${String(Math.floor(seconds/60)%60).padStart(2,'0')}:${String(Math.floor(seconds)%60).padStart(2,'0')}`;
  return <section className="panel"><h3>Processing checks</h3>
    {title && <><p>Title check: {title.status} · expected {title.expected_title}{title.declared_title && ` · file says ${title.declared_title}`}</p>{title.warnings?.map(w=><p key={w}>{w}</p>)}</>}
    {attempts?.length > 0 && <><p>Subtitle selection: {result.subtitle_source ?? 'no suitable candidate'}{result.subtitle_provider && ` · ${result.subtitle_provider}`}{result.subtitle_file && ` · ${result.subtitle_file}`}</p><details><summary>Subtitle candidates ({attempts.length})</summary><ul>{attempts.map((attempt,i)=><li key={i}>{attempt.subtitle_file ?? 'Online search'} · {attempt.subtitle_source}{attempt.subtitle_provider && ` · ${attempt.subtitle_provider}`} · {attempt.status}{attempt.error && <p>{attempt.error}</p>}{attempt.subtitle_matches?.length > 0 && <p>Release matches: {attempt.subtitle_matches.join(', ')}</p>}</li>)}</ul></details></>}
    {timing && <><p>Subtitle timing: {timing.status} · {timing.confirmed_samples ?? 0} of {timing.sampled_sections ?? timing.samples.length} dialogue samples confirmed</p><p className="help">{timing.limitations}</p></>}
    {muting && <><p>{muting.muted_seconds} seconds muted ({muting.muted_percent}% of the program) · {muting.fallback_sections} whole-subtitle sections ({muting.fallback_percent}% of matching sections)</p><p>Longest whole-subtitle mute: {muting.longest_fallback_seconds} seconds{muting.approved?' · reviewed and approved':''}</p>{muting.reasons?.map(reason=><p key={reason}>{reason}</p>)}{muting.fallback_intervals?.length>0 && <details><summary>Whole-subtitle mute locations</summary><label><input type="checkbox" checked={showDialogue} onChange={event=>setShowDialogue(event.target.checked)}/> Show dialogue (profanity masked)</label><ul>{muting.fallback_intervals.slice(0,50).map(([start,end],i)=><li key={i}>{time(start)} – {time(end)}{showDialogue && <p>{muting.fallback_dialogue?.[i]?.dialogue || 'Dialogue unavailable for this saved plan.'}</p>}</li>)}</ul>{muting.fallback_intervals.length>50 && <p>Showing 50 of {muting.fallback_intervals.length}; the processing log contains the complete plan.</p>}</details>}</>}
    {result.original_retained_until && <p>Original retention expires {new Date(result.original_retained_until*1000).toLocaleString()}. Reprocess checks whether that original is still available.</p>}
  </section>;
}
