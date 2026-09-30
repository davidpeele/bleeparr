import { test } from 'node:test';
import assert from 'node:assert/strict';
import { processingHelp } from '../src/processingHelp.js';
test('new review holds and archive capacity have specific recovery guidance',()=>{
 for(const code of ['muting_review','subtitle_alignment_review','title_review','original_storage_full']) {
  const help=processingHelp({error_code:code});assert.ok(help.steps.length);assert.match(help.explanation,/No|no|original/);
 }
 assert.match(processingHelp({error_code:'muting_review'}).steps.join(' '),/only/);
});
test('damaged MKV with backward timestamps has useful next steps', () => {
 const help = processingHelp({error_code:'invalid_media',error:'Element exceeds containing master element; Non-monotonous DTS in output stream'});
 assert.match(help.explanation,/MKV container/); assert.match(help.explanation,/timestamps jump backward/);
 assert.match(help.steps.join(' '),/different release/); assert.match(help.steps.join(' '),/does not delete or blocklist/);
});
test('unknown kill does not assert memory cause, timing alone does not assert corruption', () => {
 assert.match(processingHelp({error_code:'worker_exit'}).explanation,/does not confirm/);
 assert.match(processingHelp({error_code:'processing',error:'Non-monotonous DTS'}).explanation,/without proving/);
 assert.equal(processingHelp({success:true}),null);
});
test('missing offline model and publication failure give distinct recovery steps', () => {
 assert.match(processingHelp({error_code:'speech_model_missing'}).steps.join(' '),/will not download/);
 assert.match(processingHelp({error_code:'delivery_failed'}).explanation,/may already exist/);
 assert.match(processingHelp({error_code:'unknown',error:'something new'}).explanation,/cannot confidently/);
});
test('subtitle review explains uncertainty without claiming audio was clean', () => {
 for (const code of ['subtitle_language_mismatch', 'subtitle_language_uncertain', 'subtitle_coverage_suspect']) {
  const result = processingHelp({error_code:code});
  assert.ok(result.steps.length);
  assert.match(result.title,/subtitles|Subtitle/i);
 }
 assert.match(processingHelp({error_code:'subtitle_coverage_suspect'}).explanation,/Quiet scenes/);
});
test('speech failures explain blocked fallback and unresolved words separately', () => {
 const failed=processingHelp({error_code:'speech_model'});
 assert.match(failed.explanation,/fallback was blocked/);
 assert.match(failed.explanation,/no cleaned output/);
 assert.match(failed.steps.join(' '),/dependency error/);
 const unresolved=processingHelp({error_code:'speech_unresolved'});
 assert.match(unresolved.explanation,/fallback is disabled/);
 assert.match(unresolved.steps.join(' '),/larger fallback speech model/);
});
