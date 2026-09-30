import { test } from 'node:test';
import assert from 'node:assert/strict';
import { activityDefaults, filterActivity, jobActions } from '../src/activityFilters.js';
const jobs=[{id:1,title:'Silo',status:'failed',result:{error_code:'invalid_media'}},{id:2,title:'The Studio',status:'blocked',result:{error_code:'output_unwritable'}},{id:3,title:'Silo',status:'completed',result:{}},{id:4,title:'Other',status:'retry',result:{}},{id:5,title:'Running',status:'running',result:{error_code:'invalid_media'}}];
test('filters combine status, action and case-insensitive title without changing order',()=>{
 assert.deepEqual(filterActivity(jobs,{search:' SILO ',status:'failed',action:'search'},true).map(j=>j.id),[1]);
 assert.deepEqual(filterActivity(jobs,{...activityDefaults,action:'retry'},true).map(j=>j.id),[1,2,4]);
 assert.equal(filterActivity(jobs,{...activityDefaults,status:'completed',action:'retry'},true).length,0);
 assert.equal(filterActivity(jobs,activityDefaults,false).length,5);
});
test('actions match job status and blocklist setting',()=>{
 assert.equal(filterActivity(jobs,{...activityDefaults,action:'replace'},false).length,0);
 assert.equal(filterActivity(jobs,{...activityDefaults,action:'replace'},true).length,1);
 assert.deepEqual(jobActions(jobs[4],true),[]);
 assert.deepEqual(jobActions(jobs[1],true),['retry']);
});
test('review only offers approval for broad muting, never replacement searches',()=>{
 const muting={title:'Example',status:'review',result:{error_code:'muting_review'}};
 const timing={...muting,result:{error_code:'subtitle_alignment_review'}};
 assert.deepEqual(jobActions(muting,true),['retry','review']);
 assert.deepEqual(jobActions(timing,true),['retry']);
 assert.deepEqual(filterActivity([muting,timing],{...activityDefaults,action:'review'},true),[muting]);
});
test('no matches is retryable and never offers replacement actions', () => {
 const entry={status:'no_matches',title:'Example',result:{outcome:'no_matches_found'}};
 assert.deepEqual(jobActions(entry,true),['retry']);
 assert.deepEqual(filterActivity([entry],{search:'',status:'no_matches',action:'retry'},true),[entry]);
});
test('skips and speech failures never offer replacement actions', () => {
 const skipped={title:'French movie',status:'skipped',result:{outcome:'skipped_language'}};
 assert.deepEqual(jobActions(skipped,true),[]);
 assert.deepEqual(filterActivity([skipped],{...activityDefaults,status:'skipped'},true),[skipped]);
 for (const error_code of ['speech_model','speech_model_missing','speech_unresolved','subtitle_language_mismatch','subtitle_coverage_suspect']) {
  assert.deepEqual(jobActions({status:'failed',result:{error_code}},true),['retry']);
 }
});
