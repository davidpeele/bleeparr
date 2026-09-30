export const activityDefaults = { search: '', status: '', action: '' };
export const actionLabels = { retry: 'Retry', review:'Review muting', search: 'Search releases', match: 'Check release match', replace: 'Blocklist & search' };
export function jobActions(job, blocklistEnabled) {
  const actions = [];
  if (['failed', 'retry', 'blocked', 'no_matches','review'].includes(job.status)) actions.push('retry');
  if (job.status==='review' && job.result?.error_code==='muting_review') actions.push('review');
  if (job.status === 'failed' && job.result?.error_code === 'invalid_media') {
    actions.push('search', 'match');
    if (blocklistEnabled) actions.push('replace');
  }
  return actions;
}
export function filterActivity(jobs, filters, blocklistEnabled) {
  return jobs.filter(job => (!filters.status || job.status === filters.status)
    && (!filters.action || jobActions(job, blocklistEnabled).includes(filters.action))
    && job.title.toLowerCase().includes(filters.search.trim().toLowerCase()));
}
