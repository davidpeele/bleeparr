// Real UI, synthetic API responses, and no connections to a media server.
import {mkdir, readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const moduleName=process.env.BLEEPARR_PLAYWRIGHT_MODULE;
const {chromium}=await import(moduleName ? pathToFileURL(moduleName).href : 'playwright');
const base=process.env.BLEEPARR_SCREENSHOT_URL || 'http://127.0.0.1:5054';
const target=new URL(base);
if (!['127.0.0.1','localhost','[::1]'].includes(target.hostname)) throw Error('Screenshots require a local synthetic preview.');
const browser=await chromium.launch({headless:true,...(process.env.BLEEPARR_BROWSER ? {executablePath:process.env.BLEEPARR_BROWSER} : {})});
const config=JSON.parse(await readFile(new URL('../docs/assets/demo-settings.json',import.meta.url),'utf8'));
const now=Date.UTC(2026,8,30,12)/1000;
const jobs=[
 {id:24,kind:'sonarr',item_id:101,parent_id:1,title:'Northbound · S01E03',status:'running',attempts:1,path:'/media/TV/Northbound/episode.mkv',created:now,updated:now,result:{}},
 {id:23,kind:'radarr',item_id:2,parent_id:2,title:'The Quiet Harbor',status:'review',attempts:1,path:'/media/Movies/The Quiet Harbor/movie.mkv',created:now,updated:now,result:{error_code:'muting_review',error:'Planned muting needs review before publication.',review_token:'a'.repeat(64),title_verification:{status:'passed',expected_title:'The Quiet Harbor',declared_title:'The Quiet Harbor (2026)'},subtitle_alignment:{status:'passed',confirmed_samples:6,sampled_sections:6,samples:[],limitations:'Sampled dialogue only; passing does not verify every cue.'},muting_review:{muted_seconds:94,muted_percent:3.8,fallback_sections:8,fallback_percent:40,longest_fallback_seconds:11.2,reasons:['Whole-subtitle fallback exceeds the configured limit.'],fallback_intervals:[[416.8,428],[920.3,925.1],[1304,1310.2]]}}},
 {id:22,kind:'sonarr',item_id:102,parent_id:3,title:'Orchard Street · S02E01',status:'completed',attempts:1,path:'/media/TV/Orchard Street/episode.mkv',created:now,updated:now,result:{success:true,matched_word_count:12,fallback_sections:0,output_path:'/output/orchard.mkv'}},
 {id:21,kind:'radarr',item_id:4,parent_id:4,title:'A Summer Map',status:'no_matches',attempts:1,path:'/media/Movies/A Summer Map/movie.mkv',created:now,updated:now,result:{success:true,outcome:'no_matches_found',matched_word_count:0}},
 {id:20,kind:'radarr',item_id:5,parent_id:5,title:'Paper Satellites',status:'queued',attempts:0,path:'/media/Movies/Paper Satellites/movie.mkv',created:now,updated:now,result:{}}
];
const titles=['Northbound','Orchard Street','The Weather Room','Second Light','Cedar House','The Long Weekend'];
const library=titles.map((title,i)=>({id:i+1,title,year:2024+i%3,status:'continuing',path:`/media/TV/${title}`,content_rating:['TV-14','TV-PG','TV-MA'][i%3],selected:i<3,available:8+i,processed_files:i<2?5+i:0,processing_states:[i===0?'running':i===1?'processed':'unprocessed'],monitoring_source:i<3?'manual':'off'}));
await mkdir(new URL('./../docs/assets/',import.meta.url),{recursive:true});
try {
 for(const width of [1440,390]) {
  const page=await browser.newPage({viewport:{width,height:960},deviceScaleFactor:1});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!==target.origin){await route.abort();return;}
   if(!url.pathname.startsWith('/api/')){await route.continue();return;}
   if(route.request().method()!=='GET')throw Error('Screenshot capture must not submit changes.');
   let data;
   switch(url.pathname) {
    case '/api/status':data={jobs,counts:{completed:18,running:1,queued:3,review:1,no_matches:4},events:[],auto_process:true,auto_blocklist:false};break;
    case '/api/settings':data=config;break;
    case '/api/library/sonarr':case '/api/library/radarr':data=library;break;
    case '/api/notifications':data={items:[],worker_enabled:false};break;
    case '/api/originals':data={enabled:false,used_bytes:0,retained_count:0,limit_bytes:100*1024**3,days:7};break;
    case '/api/speech-readiness':data={models:[{name:'small.en',cached:true},{name:'medium.en',cached:true}],dependencies:{'faster-whisper':'1.2.1',av:'18.1.0',ctranslate2:'4.8.2'},latest:{status:'passed',checked_at:now,models:[{name:'small.en',status:'passed'},{name:'medium.en',status:'passed'}]},outdated:false,worker_busy:false,explanation:'Checks local model loading, audio decoding, and inference. Compatibility is not recognition accuracy.'};break;
    default:throw Error(`Unexpected synthetic endpoint: ${url.pathname}`);
   }
   await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  const shot=async name=>page.screenshot({path:`docs/assets/${name}${width===390?'-mobile':''}.png`,fullPage:true});
  await page.goto(base);await page.getByText('Northbound · S01E03',{exact:true}).waitFor();await shot('overview');
  await page.getByRole('button',{name:'TV shows',exact:true}).click();await page.getByRole('heading',{name:'Northbound',exact:true}).waitFor();await shot('library');
  await page.getByRole('button',{name:'Activity',exact:true}).click();await page.getByRole('button',{name:'Review muting',exact:true}).click();await page.getByRole('dialog',{name:'Review planned muting'}).waitFor();await page.getByText('Whole-subtitle mute locations',{exact:true}).click();await shot('review');await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByRole('heading',{name:'Review before publishing',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Review before publishing',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`docs/assets/safeguards${width===390?'-mobile':''}.png`});
  if(errors.length)throw Error(errors.join('\n'));
  console.log(`Synthetic screenshots captured at ${width}px.`);await page.close();
 }
} finally {await browser.close();}
