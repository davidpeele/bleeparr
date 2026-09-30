import { useEffect, useState } from 'react';
import { activityDefaults, actionLabels, filterActivity } from './activityFilters';

export default function Activity({status, states, jobsComponent, busy, action, setLog, scan}) {
  const Jobs = jobsComponent;
  const [filters, setFilters] = useState(() => { try { return {...activityDefaults, ...JSON.parse(localStorage.getItem('bleeparr-activity-filters') || '{}')}; } catch { return activityDefaults; } });
  useEffect(() => { try { localStorage.setItem('bleeparr-activity-filters', JSON.stringify(filters)); } catch { /* Filtering still works without browser storage. */ } }, [filters]);
  const field = (key, value) => setFilters(f => ({...f, [key]:value}));
  const jobs = filterActivity(status.jobs, filters, status.auto_blocklist);
  return <>
    <div className="section-head"><p>Track completed files, inspect failures, and retry when you’re ready.</p><button disabled={busy} onClick={scan}>Scan monitored titles</button></div>
    <div className="panel library-controls">
      <label>Search activity<input placeholder="Filter by title…" value={filters.search} onChange={e=>field('search',e.target.value)}/></label>
      <label>Job status<select value={filters.status} onChange={e=>field('status',e.target.value)}><option value="">All statuses</option>{Object.entries(states).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Available action<select value={filters.action} onChange={e=>field('action',e.target.value)}><option value="">Any action</option>{Object.entries(actionLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <div className="library-control-footer"><span role="status">{jobs.length} of {status.jobs.length} recent jobs · latest 300 maximum</span><button onClick={()=>setFilters(activityDefaults)}>Reset activity filters</button></div>
    </div>
    {!jobs.length && status.jobs.length ? <div className="empty"><h3>No matching jobs.</h3><p>Change or reset your filters to see more activity.</p></div> : <Jobs jobs={jobs} busy={busy} action={action} setLog={setLog} blocklistEnabled={status.auto_blocklist}/>}
    <h2>System events</h2><div className="panel">{status.events.length ? status.events.map(event=><p key={event.id}><small>{new Date(event.created*1000).toLocaleString()}</small><br/>{event.message}</p>) : <p className="muted">No system events yet.</p>}</div>
  </>;
}
