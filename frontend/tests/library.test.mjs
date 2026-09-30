import assert from 'node:assert/strict';
import { test } from 'node:test';
import { selectItems, defaults } from '../src/libraryFilters.js';
const items = [
  { id:1,title:'Zebra',selected:true,content_rating:'R',year:2024,added:'2025-01-01',processing_states:['processed','queued'] },
  { id:2,title:'Alpha',selected:false,content_rating:'PG',year:2020,added:'2026-01-01',processing_states:['unprocessed'] },
  { id:3,title:'Missing',selected:true,content_rating:'Not rated',year:null,added:null,processing_states:['failed'] },
];
test('combined filters preserve mixed processing states', () => {
  assert.deepEqual(selectItems(items,{...defaults,monitoring:'monitored',rating:'R',processing:'queued'}).map(i=>i.id),[1]);
  assert.equal(selectItems(items,{...defaults,search:'  ALP ',monitoring:'unmonitored'}).length,1);
  assert.equal(selectItems(items,{...defaults,rating:'TV-MA'}).length,0);
});
test('sort dates and years with missing values last in either direction', () => {
  assert.deepEqual(selectItems(items,{...defaults,sort:'added',direction:'desc'}).map(i=>i.id),[2,1,3]);
  assert.deepEqual(selectItems(items,{...defaults,sort:'year',direction:'asc'}).map(i=>i.id),[2,1,3]);
  assert.deepEqual(selectItems(items,{...defaults,sort:'year',direction:'desc'}).map(i=>i.id),[1,2,3]);
  assert.deepEqual(items.map(i=>i.id),[1,2,3]);
});
