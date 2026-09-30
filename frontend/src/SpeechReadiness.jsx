import {useEffect, useState} from 'react';

export default function SpeechReadiness({api, action, busy, save}) {
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  useEffect(()=>{
    let active=true;
    const load=()=>api('/speech-readiness').then(result=>{if(active)setData(result);}).catch(e=>{if(active)setError(e.message);});
    load();const timer=setInterval(load,5000);
    return ()=>{active=false;clearInterval(timer);};
  },[api]);
  const labels={passed:'Runtime check passed',failed:'Runtime check failed',running:'Checking models…',not_checked:'Runtime not checked yet'};
  return <section className="panel"><h2>Speech-model readiness</h2>
    {error && <p role="alert">{error}</p>}
    {data && <><ul>{data.models.map(model=><li key={model.name}>{model.name} · {model.cached?'Local files available':'Local files missing or unconfirmed'}</li>)}</ul>
      <p role="status">{labels[data.latest.status] || 'Runtime not checked yet'}{data.outdated && data.latest.status!=='not_checked'?' · settings changed; check again':''}</p>
      {data.latest.error && <p>{data.latest.error}</p>}
      {data.latest.models?.map(model=><p key={model.name}>{model.name}: {model.status==='passed'?'Passed':'Needs attention'}{model.error && ` · ${model.error}`}</p>)}
      {data.latest.checked_at && <p className="help">Last check: {new Date(data.latest.checked_at*1000).toLocaleString()}</p>}
      <p className="help">{data.explanation}</p>
      {data.worker_busy && data.latest.status!=='running' && <p>A file is processing. Run the runtime check when processing is idle.</p>}
      <details><summary>Installed speech runtime</summary>{Object.entries(data.dependencies).map(([name,version])=><p key={name}>{name}: {version || 'Not installed'}</p>)}</details>
    </>}
    <button type="button" disabled={busy || data?.worker_busy || data?.latest.status==='running'} onClick={()=>action(async()=>{await save();return api('/speech-readiness','POST');})}>Save & check models</button>
    <p className="help">Checks run locally without downloading models or sending audio anywhere.</p>
  </section>;
}
