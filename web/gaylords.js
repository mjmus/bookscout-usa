(function(){
'use strict';
const SOURCES=window.BOOKSCOUT_GAYLORD_SOURCES||[];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const usd=n=>Number(n).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});
const stateOptions=[['all','All regions'],['VA','Virginia'],['US','Nationwide'],...Array.from(new Set(SOURCES.map(x=>x.state))).filter(x=>!['VA','US'].includes(x)).sort().map(x=>[x,x])];
const scanLabel={seller_claim_unscanned:'Seller CLAIMS unscanned',raw_not_verified:'Raw; scan status unproven',upstream_scanned:'Upstream scanning disclosed',processed_unknown:'Curated; scan status unknown',unknown:'Scan status unknown'};
const scanClass={seller_claim_unscanned:'good',raw_not_verified:'warn',upstream_scanned:'bad',processed_unknown:'warn',unknown:'warn'};
const typeLabel={direct:'Direct wholesaler',industrial:'Truckload / industrial',marketplace:'Auction or marketplace',historical:'Closed example · seller to track',relationship:'Contact-only prospect'};
function prefs(data){data.gayPrefs||={query:'',scan:'all',type:'all',ship:'all',region:'all',sort:'priority'};data.gayCalc||={source:'',qty:'',purchase:'',freight:'',liftgate:'',other:'',premium:'0',reject:'25',sold:'',net:'',};return data.gayPrefs;}
function option(values,value){return values.map(x=>'<option value="'+esc(x[0])+'" '+(String(x[0])===String(value)?'selected':'')+'>'+esc(x[1])+'</option>').join('')}
function selected(data){const p=prefs(data);const r=SOURCES.filter(s=>{
 if(p.query&&![s.title,s.source,s.evidence,s.screening_note,s.state,s.format].join(' ').toLowerCase().includes(p.query.toLowerCase()))return false;
 if(p.scan!=='all'&&s.screening!==p.scan)return false;
 if(p.type!=='all'&&s.type!==p.type)return false;
 if(p.ship==='yes'&&!['yes','ask'].includes(s.shipping))return false;
 if(p.ship==='pickup'&&s.shipping!=='no')return false;
 if(p.region!=='all'&&s.state!==p.region)return false;
 return true;
});
r.sort((a,b)=>p.sort==='price'?(a.price==null?Infinity:a.price)-(b.price==null?Infinity:b.price):p.sort==='source'?a.source.localeCompare(b.source):a.priority-b.priority);
return r;}
function checkStatus(s,LIVE){const c=(LIVE.checks||[]).find(x=>x.url===s.url);if(!c)return 'Offer snapshot '+s.reviewed_at+' · not stock checked';
return c.status==='ok'?'Page reachable · '+(c.last_success||'').slice(0,10)+' · stock NOT confirmed':'Automated access failed · source link still available';}
function card(s,data,LIVE){const watched=!!data.watch?.[s.id],historical=s.type==='historical',price=s.price==null?'Quote / bid needed':usd(s.price)+' (excludes freight)',badge=scanLabel[s.screening]||'Unknown',cls=scanClass[s.screening]||'warn';
return '<article class="gay-card"><div class="gay-head"><div><small class="gay-muted">'+esc(typeLabel[s.type]||s.type)+' · '+esc(s.state||'USA')+'</small><h3>'+esc(s.title)+'</h3></div><button class="star '+(watched?'on':'')+'" data-gay-watch="'+esc(s.id)+'" title="Save to watchlist">'+(watched?'★':'☆')+'</button></div>'+
'<div class="tags"><span class="tag '+cls+'">'+esc(badge)+'</span>'+ (historical?'<span class="tag bad">CLOSED / HISTORICAL</span>':'')+'<span class="tag">'+(s.shipping==='yes'?'Freight offered':s.shipping==='no'?'Pickup only':s.shipping==='ask'?'Freight: ask seller':'Shipping varies')+'</span></div>'+
'<p class="gay-evidence">'+esc(s.evidence)+'</p>'+
'<div class="gay-metrics"><div><small>Publicly stated price</small><b>'+esc(price)+'</b></div><div><small>Reported lot size</small><b>'+esc(s.format||'Unknown')+'</b></div></div>'+
'<p class="gay-muted">'+esc(s.screening_note)+'</p>'+
'<div class="gay-status">◷ '+esc(checkStatus(s,LIVE))+'</div>'+
'<div class="gay-actions"><a class="btn slim" href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">Open source ↗</a><button class="btn slim" data-gay-est="'+esc(s.id)+'">Compare landed cost</button><button class="btn slim" data-gay-copy="'+esc(s.id)+'">Copy seller questions</button></div>'+
'<details><summary>Condition, shipping & evidence</summary><p><b>Condition:</b> '+esc(s.condition)+'</p><p><b>Freight:</b> '+esc(s.shipping_note)+'</p><p><b>Access:</b> '+esc(s.access)+'</p><p><b>ISBN evidence:</b> No manifest attached. No Amazon/eBay rank can be inferred.</p>'+(s.secondary?'<a href="'+esc(s.secondary)+'" target="_blank" rel="noopener noreferrer">Additional supplier evidence ↗</a>':'')+
'<label class="gay-note-label">Private sourcing notes</label><textarea class="gay-note" data-gay-note="'+esc(s.id)+'" placeholder="Contact, raw-stream assurance, quoted freight, sample scan yield...">'+esc(data.notes?.[s.id]||'')+'</textarea></details></article>';}
function calcHtml(data){
const c=data.gayCalc;const fields=[['qty','Books in lot'],['purchase','Price / winning bid ($)'],['premium','Buyers premium (%)'],['freight','Delivery freight ($)'],['liftgate','Liftgate / handling ($)'],['other','Tax / travel / other ($)'],['reject','Rejected or damaged (%)'],['sold','Books likely to sell (optional)'],['net','Net realized per sold book after marketplace fees/shipping ($, optional)']];
return '<div class="gay-calc-grid">'+fields.map(([k,l])=>'<label>'+l+'<input class="input" data-gay-calc="'+k+'" type="number" step="any" min="0" value="'+esc(c[k]??'')+'" placeholder="Enter actual / assumption"></label>').join('')+'</div><div id="gay-calc-result">'+calcResult(c)+'</div>';
}
function calcResult(c){
const qty=Number(c.qty),price=Number(c.purchase),freight=Number(c.freight),lift=Number(c.liftgate),other=Number(c.other),premium=Number(c.premium),reject=Number(c.reject),sold=Number(c.sold),net=Number(c.net),valid=String(c.qty).trim()!==''&&qty>0&&String(c.purchase).trim()!==''&&price>=0&&[freight,lift,other,premium,reject].every(Number.isFinite)&&reject>=0&&reject<100;
if(!valid)return '<p class="gay-muted">Enter a real lot count and purchase price. Freight and fees default to $0 only if you leave them blank; confirm the delivered amount before buying.</p>';
const landed=price*(1+premium/100)+freight+lift+other,usable=Math.max(0,qty*(1-reject/100)),cpu=landed/usable,profit=String(c.sold).trim()!==''&&String(c.net).trim()!==''&&sold>=0&&net>=0&&sold<=qty?usd(sold*net-landed):'Not calculated (resale assumptions missing)';
return '<div class="gay-calc-stats"><div><small>All-in landed</small><b>'+usd(landed)+'</b></div><div><small>Usable copies (assumed)</small><b>'+Math.floor(usable)+'</b></div><div><small>Cost / usable copy</small><b>'+usd(cpu)+'</b></div><div><small>Projected net</small><b>'+profit+'</b></div></div><p class="gay-muted">Illustrative only. Net revenue per sold book must be supported by actual sold comps and fees. Unsold copies, storage, returns and labor can reduce profit.</p>';
}
function page({data,LIVE}){
const p=prefs(data),rows=selected(data);
const headline='<div class="section-note"><b>Gaylords & raw-book leads:</b> Different from BookSaleFinder. These are first-party wholesale offerings, marketplace entry points, and historical institutional sellers. Unscanned status is <b>seller-claimed only</b> unless backed by your own inspection. No book ISBN list = no automatic sales-rank claim.</div>'+
'<div class="stats"><div class="stat"><small>Researched bulk channels</small><b>'+SOURCES.length+'</b><em>Not all currently purchasable lots</em></div><div class="stat"><small>Seller unscanned claims</small><b>'+SOURCES.filter(x=>x.screening==='seller_claim_unscanned').length+'</b><em>None independently audited</em></div><div class="stat"><small>Documented historical sellers</small><b>'+SOURCES.filter(x=>x.type==='historical').length+'</b><em>Not active auctions</em></div><div class="stat"><small>Linked ISBN manifests</small><b>0</b><em>No invented rank / profit</em></div></div>';
const filters='<section class="panel"><div class="panelhead"><h2>Find bulk inventory</h2><span class="small muted">Filter raw claims separately from screened supply.</span></div><div class="gay-filters">'+
'<input class="input" id="gayQuery" placeholder="Supplier, gaylord, school, bulk, state..." value="'+esc(p.query)+'">'+
'<select id="gayScan" class="select">'+option([['all','Any screening evidence'],['seller_claim_unscanned','Seller claims unscanned'],['raw_not_verified','Raw; not proven unscanned'],['unknown','Unknown screening'],['processed_unknown','Curated / processed'],['upstream_scanned','Upstream scanning disclosed']],p.scan)+'</select>'+
'<select id="gayType" class="select">'+option([['all','All channels'],...Object.entries(typeLabel)],p.type)+'</select>'+
'<select id="gayRegion" class="select">'+option(stateOptions,p.region)+'</select>'+
'<select id="gayShip" class="select">'+option([['all','Any freight'],['yes','Shipping offered / ask'],['pickup','Pickup only']],p.ship)+'</select>'+
'<select id="gaySort" class="select">'+option([['priority','Sourcing fit first'],['price','Advertised price low to high'],['source','Supplier name A-Z']],p.sort)+'</select>'+
'</div></section>';
const calc='<section class="panel gay-calc" id="gay-calculator"><div class="panelhead"><h2>Delivered-cost & resale reality check</h2><span class="small muted">Use a real quote or bid. Blank ISBN comps are never filled with guesses.</span></div>'+calcHtml(data)+'</section>';
return headline+filters+'<div class="statline"><strong>'+rows.length+' matching sources</strong><span>Inventory status must be rechecked on the original seller site.</span></div><div class="gay-grid">'+rows.map(x=>card(x,data,LIVE)).join('')+'</div>'+calc+
'<section class="panel"><h2>Before paying for an “unscanned” pallet</h2><p class="gay-muted">Request written confirmation that neither the seller nor its upstream donors/partners used ISBN scanning or removed high-value titles. Ask for 20 randomly selected ISBNs photographed from top, middle and bottom; duplicate/defect rate; load weight; and an all-in freight quote including liftgate. A supplier claim is evidence of their marketing, not independent proof of profitable contents.</p><button class="btn" id="gayExport">Export supplier research & private notes (CSV)</button></section>';
}
function question(s){return 'Hello, I am evaluating a book gaylord from '+s.source+'. Before ordering, could you confirm:\n\n1. Were any books ISBN-scanned, price-checked, cherry-picked, or high-value titles removed, either by you or an upstream supplier?\n2. Is this original first-pass donation/library inventory or leftovers after sorting?\n3. Can you provide 20 RANDOM ISBNs/photos from the top, middle, and bottom of the exact lot, plus duplicate and damage estimates?\n4. Exact book count/weight, category mix, edition age and ex-library percentage?\n5. Total price delivered to Richmond, VA (freight, liftgate, pallet, taxes and handling), and pickup alternatives?\n6. Are these photos of the actual shipment, and what remedies apply if the lot differs materially from the description?\n\nThank you.';}
function bind({data,LIVE,persist,go,notice}){
const p=prefs(data);
for(const [id,key] of [['gayScan','scan'],['gayType','type'],['gayRegion','region'],['gayShip','ship'],['gaySort','sort']]){
const el=document.getElementById(id);if(el)el.onchange=()=>{p[key]=el.value;persist();go('gaylords')};
}
const q=document.getElementById('gayQuery');if(q)q.onchange=()=>{p.query=q.value;persist();go('gaylords')};
document.querySelectorAll('[data-gay-watch]').forEach(b=>b.onclick=()=>{data.watch[b.dataset.gayWatch]=!data.watch[b.dataset.gayWatch];persist();go('gaylords')});
document.querySelectorAll('[data-gay-note]').forEach(el=>el.onchange=()=>{data.notes[el.dataset.gayNote]=el.value;persist();notice('Private note saved')});
document.querySelectorAll('[data-gay-copy]').forEach(b=>b.onclick=async()=>{let s=SOURCES.find(x=>x.id===b.dataset.gayCopy);if(!s)return;try{await navigator.clipboard.writeText(question(s));notice('Seller screening questions copied')}catch{notice('Clipboard permission denied; use seller source link')}});
document.querySelectorAll('[data-gay-est]').forEach(b=>b.onclick=()=>{let s=SOURCES.find(x=>x.id===b.dataset.gayEst);if(!s)return;let c=data.gayCalc;c.source=s.id;c.qty=s.qty??'';c.purchase=s.price??'';c.freight='';c.liftgate='';c.other='';c.sold='';c.net='';persist();go('gaylords');document.getElementById('gay-calculator')?.scrollIntoView({behavior:'smooth',block:'center'});notice('Enter actual freight/fees. No live sale price claimed.')});
document.querySelectorAll('[data-gay-calc]').forEach(el=>el.oninput=()=>{data.gayCalc[el.dataset.gayCalc]=el.value;persist();const r=document.getElementById('gay-calc-result');if(r)r.innerHTML=calcResult(data.gayCalc)});
const out=document.getElementById('gayExport');if(out)out.onclick=()=>{let lines=[['title','source','region','type','screening','screening_note','price_usd','quantity','shipping','evidence','url','notes'].join(',')];let q=x=>'"'+String(x??'').replace(/"/g,'""')+'"';for(let x of SOURCES)lines.push([x.title,x.source,x.state,x.type,x.screening,x.screening_note,x.price,x.qty,x.shipping,x.evidence,x.url,data.notes?.[x.id]||''].map(q).join(','));let u=URL.createObjectURL(new Blob([lines.join('\r\n')],{type:'text/csv'})),a=document.createElement('a');a.href=u;a.download='bookscout-gaylord-sources.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),500);};
}
window.BookScoutGaylords={page,bind,sources:SOURCES,screeningLabels:scanLabel};
})();
