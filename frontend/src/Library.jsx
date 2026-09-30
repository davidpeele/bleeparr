import { useCallback, useEffect, useState } from 'react';
import { defaults, processingLabels, selectItems } from './libraryFilters';

export default function Library({ kind, api, action, busy, Discover }) {
  const Discovery = Discover;
  const storageKey = `bleeparr-library-${kind}`;
  const [prefs, setPrefs] = useState(() => { try { return { ...defaults, ...JSON.parse(localStorage.getItem(storageKey) || '{}') }; } catch { return defaults; } });
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [discover, setDiscover] = useState(false);
  const load = useCallback(async () => { try { setItems(await api(`/library/${kind}`)); setError(''); } catch (e) { setError(e.message); } finally { setLoaded(true); } }, [kind, api]);
  useEffect(() => { load(); const timer = setInterval(load, 30000); return () => clearInterval(timer); }, [load]);
  useEffect(() => { try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch { /* Storage may be unavailable in private browsing. */ } }, [prefs, storageKey]);
  const field = (key, value) => setPrefs(p => ({ ...p, [key]: value }));
  const ratings = [...new Set(items.map(i => i.content_rating || 'Not rated'))].sort();
  const visible = selectItems(items, prefs);
  const monitor = item => <label className="check"><input type="checkbox" checked={item.selected} disabled={busy || !!item.skip_reason} onChange={() => action(async () => { await api(`/library/${kind}/${item.id}/monitor`, 'PUT', {enabled: !item.selected}); await load(); }, 'Monitoring updated')}/> Monitor with Bleeparr</label>;
  const source = item => item.skip_reason || (item.monitoring_source === 'cleanvid' ? 'Automatically selected · CleanVid' : item.monitoring_source === 'excluded' ? 'Excluded from automatic selection' : '');
  const process = item => <button disabled={busy || !item.available || !!item.skip_reason} onClick={() => action(async () => { const result = await api(`/library/${kind}/${item.id}/queue`, 'POST'); await load(); return result; })}>Process available files →</button>;
  const badges = item => <div className="media-badges">{(item.processing_states || []).map(state => <span key={state} className={`badge ${state === 'processed' ? 'completed' : state}`}>{state === 'processed' ? `${item.processed_files} processed file${item.processed_files === 1 ? '' : 's'}` : processingLabels[state]}</span>)}</div>;
  return <>
    <div className="section-head"><p>Choose which {kind === 'sonarr' ? 'shows' : 'movies'} Bleeparr should clean.</p><button className="primary" onClick={() => setDiscover(!discover)}>{discover ? 'Back to library' : '+ Add a title'}</button></div>
    {discover ? <Discovery kind={kind} action={action} busy={busy} onAdded={() => { load(); setDiscover(false); }}/> : <>
      <div className="panel library-controls">
        <label className="library-search">Search your library<input placeholder="Filter by title…" value={prefs.search} onChange={e => field('search', e.target.value)}/></label>
        <label>Bleeparr monitoring<select value={prefs.monitoring} onChange={e => field('monitoring', e.target.value)}><option value="">All titles</option><option value="monitored">Monitored</option><option value="unmonitored">Unmonitored</option></select></label>
        <label>Processing status<select value={prefs.processing} onChange={e => field('processing', e.target.value)}><option value="">Any status</option>{Object.entries(processingLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Content rating<select value={prefs.rating} onChange={e => field('rating', e.target.value)}><option value="">All ratings</option>{[...new Set([...ratings, ...(prefs.rating ? [prefs.rating] : [])])].map(r => <option key={r}>{r}</option>)}</select></label>
        <label>Sort by<select value={prefs.sort} onChange={e => field('sort', e.target.value)}><option value="name">Name</option><option value="year">Year</option><option value="added">Date added</option></select></label>
        <label>Sort direction<select value={prefs.direction} onChange={e => field('direction', e.target.value)}><option value="asc">{prefs.sort === 'name' ? 'A to Z' : 'Oldest first'}</option><option value="desc">{prefs.sort === 'name' ? 'Z to A' : 'Newest first'}</option></select></label>
        <div className="library-control-footer"><span aria-live="polite">{visible.length} of {items.length} titles</span><div className="view-switch" role="group" aria-label="Library view"><button aria-pressed={prefs.view === 'cards'} onClick={() => field('view', 'cards')}>Cards</button><button aria-pressed={prefs.view === 'table'} onClick={() => field('view', 'table')}>Table</button></div><button onClick={() => setPrefs(p => ({...defaults, view:p.view}))}>Reset filters & sort</button><button onClick={load}>Refresh</button></div>
      </div>
      <p className="help">Ratings and date added come from {kind === 'sonarr' ? 'Sonarr' : 'Radarr'}. Processed counts include inherited completions; a show may also have queued or failed episodes.</p>
      {error && <div role="alert" className="alert error">{error}</div>}
      {!loaded ? <p>Loading library…</p> : !items.length ? <div className="empty"><h3>Your library will appear here.</h3><p>Connect {kind === 'sonarr' ? 'Sonarr' : 'Radarr'} in Settings or add a title.</p></div> : !visible.length ? <div className="empty"><h3>No matching titles.</h3><p>Try changing or resetting your filters.</p></div> : prefs.view === 'table' ?
        <div className="table-wrap"><table className="media-table"><caption className="sr-only">{kind === 'sonarr' ? 'TV shows' : 'Movies'} library</caption><thead><tr>{['Title','Year','Content rating','Date added','Processing','Monitoring','Actions'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{visible.map(item => <tr key={item.id}><td><strong>{item.title}</strong><small>{item.available ? 'Files available' : 'Awaiting download'}</small></td><td>{item.year || '—'}</td><td><span className="rating">{item.content_rating || 'Not rated'}</span></td><td>{item.added && !isNaN(Date.parse(item.added)) ? new Date(item.added).toLocaleDateString() : '—'}</td><td>{badges(item)}</td><td>{monitor(item)}<small>{source(item)}</small></td><td>{process(item)}</td></tr>)}</tbody></table></div>
        : <div className="library-grid">{visible.map(item => <article className="library-card" key={item.id}><div className="cover-mark" aria-hidden="true">{item.title.slice(0,1)}</div><div className="card-body"><div className="card-meta"><small>{item.year || 'Year unknown'} · {item.available ? 'Files available' : 'Awaiting download'}</small><span className="rating">{item.content_rating || 'Not rated'}</span></div><h3>{item.title}</h3>{badges(item)}{monitor(item)}<small>{source(item)}</small>{process(item)}</div></article>)}</div>}
    </>}
  </>;
}
