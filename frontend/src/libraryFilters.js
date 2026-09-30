export const processingLabels = { skipped: 'Skipped · non-English audio', blocked: 'Blocked · folder access', processed: 'Has processed files', queued: 'Queued / waiting to retry', running: 'Processing', failed: 'Needs attention', no_matches: 'No matching words found', unprocessed: 'No processing recorded' };
export const defaults = { search: '', monitoring: '', processing: '', rating: '', sort: 'name', direction: 'asc', view: 'cards' };
export function selectItems(items, prefs) {
  const filtered = items.filter(item => item.title.toLowerCase().includes(prefs.search.trim().toLowerCase())
    && (!prefs.monitoring || item.selected === (prefs.monitoring === 'monitored'))
    && (!prefs.processing || (item.processing_states || []).includes(prefs.processing))
    && (!prefs.rating || (item.content_rating || 'Not rated') === prefs.rating));
  const value = item => prefs.sort === 'name' ? item.title : prefs.sort === 'year' ? (item.year || null) : (Date.parse(item.added) || null);
  return filtered.sort((a, b) => {
    const av = value(a), bv = value(b);
    if (av === null && bv !== null) return 1;
    if (bv === null && av !== null) return -1;
    const order = typeof av === 'string' ? av.localeCompare(bv, undefined, { numeric: true, sensitivity: 'base' }) : (av ?? 0) - (bv ?? 0);
    return order * (prefs.direction === 'desc' ? -1 : 1) || a.title.localeCompare(b.title) || a.id - b.id;
  });
}
