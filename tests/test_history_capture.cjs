const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'..','capture_history.js'),'utf8');
async function run(opt={}){
 const output=[];let urls=0,counts=0,reads=0;
 const card=kind=>({getAttribute:()=> 'ProfileBookingCard.'+kind,querySelector:s=> s==='h3'?{textContent:'Example Item'}:s.includes('star-rating')?{getAttribute:()=> 'Rated 5 stars out of 5'}:{textContent:s.includes('date-time')?'Jan 1, 1:00 PM':s.includes('credits')?'4 credits':'Example'}});
 const context={Date,tab:{url:async()=> (++urls>1&&opt.navigate)?'https://classpass.com/':(opt.url||'https://classpass.com/profile/past'),playwright:{getByRole:()=>({innerText:async()=>{reads++;return ++counts>1&&opt.change?'Past (5)':'Past (4)';}}),locator:()=>({evaluateAll:async fn=>{reads++;return fn(opt.empty?[]:[card('reservation'),card('order')]);}})}},nodeRepl:{write:x=>output.push(x)}};
 try{await vm.runInNewContext('(async()=>{'+script+'})()',context);return{output,reads};}catch(error){return{output,reads,error};}
}
test('both variants capture only allowed fields',async()=>{const r=await run();assert.equal(r.error,undefined);const x=JSON.parse(r.output[0]);assert.deepEqual(x.rows.map(i=>i.kind),['reservation','order']);assert.equal(x.displayed_total,4);assert.ok(!r.output[0].includes('booking_id'));});
test('reject source before reading DOM',async()=>{const r=await run({url:'https://classpass.com/profile/past?secret=SECRET'});assert.ok(r.error);assert.equal(r.reads,0);assert.equal(r.output.length,0);assert.ok(!r.error.message.includes('SECRET'));});
test('fail closed on empty rows or page changes',async()=>{for(const opt of [{empty:true},{change:true},{navigate:true}]){const r=await run(opt);assert.ok(r.error);assert.equal(r.output.length,0);}});
