/* Silver Scan data hub. Strict provider IDs; original source-backed UI.
   Does not treat ticker strings as verified chain or contract identity. */
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n};
const box=(cls,...parts)=>{const n=el('div',null,cls);n.append(...parts);return n};
const compact=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:3}).format(n):'—';
const usd=n=>typeof n==='number'&&Number.isFinite(n)?'$'+(n<.01&&n>0?n.toPrecision(3):compact(n)):'—';
const pct=n=>typeof n==='number'&&Number.isFinite(n)?(n>0?'+':'')+n.toFixed(2)+'%':'—';
const link=(href,label)=>{const a=el('a',label);a.href=href;a.target='_blank';a.rel='noopener noreferrer';return a};
async function get(url){
  const r=await fetch(url,{headers:{Accept:'application/json'}});
  const data=await r.json().catch(()=>({error:'Unreadable server reply'}));
  if(!r.ok)throw Error(data.error||'Provider unavailable (HTTP '+r.status+')');
  return data;
}
function meta(data){
  const n=el('p','Source: '+(data.source||'unavailable')+
  (data.fetched_at?' · Retrieved '+new Date(data.fetched_at*1000).toLocaleString():'')+
  (data.stale?' · STALE snapshot':'')+
  (data.note?' · '+data.note:''),'hub-meta');return n;
}
function addCell(row,text){
  const c=el('td');
  if(text instanceof Node)c.append(text);else c.textContent=String(text??'—');
  row.append(c);
}
const WATCH_KEY='silver-scan-coin-watch-v1';
const watched=()=>{
  try{const ids=JSON.parse(localStorage.getItem(WATCH_KEY)||'[]');
    return Array.isArray(ids)?ids.filter(id=>typeof id==='string'&&/^(?:coingecko:[a-z0-9-]{1,100}|coinlore:[0-9]{1,18})$/.test(id)).slice(0,50):[];}
  catch{return [];}
};
function toggleWatch(id){
  if(!/^(?:coingecko:[a-z0-9-]{1,100}|coinlore:[0-9]{1,18})$/.test(id))return;
  const ids=watched(),next=ids.includes(id)?ids.filter(x=>x!==id):[...ids,id].slice(0,50);
  try{localStorage.setItem(WATCH_KEY,JSON.stringify(next));}catch{return;}
  renderWatch();
}

function assetTable(rows,kind){
  const wrapper=el('div',null,'hub-table-scroll');
  const table=el('table',null,'hub-table');
  const head=el('tr');
  const names=kind==='pairs'?['Pair','Base/Quote','Spot price','24h volume','Status']:['Asset','Market ID','Rank','USD price','24h volume','24h change','Watch'];
  for(const h of names)head.append(el('th',h));
  const th=el('thead');th.append(head);table.append(th);
  const body=el('tbody');
  for(const data of rows){
    const tr=el('tr');
    if(kind==='pairs'){
      addCell(tr,data.pair||'—');addCell(tr,(data.base||'?')+'/'+(data.quote||'?'));
      addCell(tr,usd(data.price));addCell(tr,typeof data.volume_24h==='number'?
        compact(data.volume_24h)+' '+(data.volume_unit||data.base||'base units'):'—');
      addCell(tr,data.status||'Unknown');
    }else{
      const name=el('strong',data.name||data.provider_id||'—');
      const sub=el('small',(data.symbol||'').toUpperCase()+' · '+(data.market_status||'market unverified'));
      addCell(tr,box('hub-asset-cell',name,sub));
      addCell(tr,data.id||'—');addCell(tr,data.rank??'—');
      addCell(tr,usd(data.price_usd));addCell(tr,usd(data.volume_24h_usd));addCell(tr,pct(data.change_24h_pct));
      const c=el('td');
      if(typeof data.id==='string'&&(data.id.startsWith('coingecko:')||data.id.startsWith('coinlore:'))){
        const active=watched().includes(data.id);
        const star=el('button',active?'★':'☆','hub-watch-star');
        star.type='button';star.title=active?'Remove from Coin Watch':'Add to Coin Watch';
        star.setAttribute('aria-label',(active?'Remove ':'Watch ')+(data.name||data.id));
        star.setAttribute('aria-pressed',String(active));
        star.addEventListener('click',()=>{toggleWatch(data.id);star.textContent=watched().includes(data.id)?'★':'☆';star.setAttribute('aria-pressed',String(watched().includes(data.id)));});
        c.append(star);
        if($('portfolio')){
          const add=el('button','+ Portfolio','hub-portfolio-pick');
          add.type='button';add.setAttribute('aria-label','Add '+(data.name||data.id)+' to manual portfolio');
          add.addEventListener('click',()=>document.dispatchEvent(new CustomEvent('portfolio:select',{
            detail:{id:data.id,name:data.name,symbol:data.symbol}
          })));
          c.append(add);
        }
      }else c.textContent='—';
      tr.append(c);
    }
    body.append(tr);
  }
  table.append(body);wrapper.append(table);return wrapper;
}
async function renderWatch(){
  const panel=$('watch-results');if(!panel)return;
  const ids=watched();
  if(!ids.length){
    panel.replaceChildren(el('p','Your watchlist is empty. Search the catalog below and select ☆ to save a coin.','hub-note'));return;
  }
  panel.replaceChildren(el('p','Checking '+ids.length+' saved provider IDs…','hub-note'));
  const sources=[
    {prefix:'coinlore:',url:'/api/coinlore/quotes?ids='},
    {prefix:'coingecko:',url:'/api/coin-watch/quotes?ids='}
  ];
  const result=[];
  const warnings=[];
  for(const source of sources){
    const subset=ids.filter(id=>id.startsWith(source.prefix));
    if(!subset.length)continue;
    try{
      const data=await get(source.url+encodeURIComponent(subset.map(id=>id.slice(source.prefix.length)).join(',')));
      result.push(...(data.assets||[]));
    }catch(error){warnings.push(source.prefix.slice(0,-1)+' quotes temporarily unavailable');}
  }
  panel.replaceChildren(
    result.length?assetTable(result,'assets'):el('p','Saved coins have no current provider quotes; entries remain stored in this browser.','hub-note'));
  const missing=ids.filter(id=>!result.some(asset=>asset.id===id));
  if(missing.length){
    const list=box('hub-missing',el('h3','Saved IDs without a current quote'));
    for(const id of missing){
      const row=box('hub-missing-row',el('code',id));
      const b=el('button','Remove','hub-watch-star');
      b.type='button';b.addEventListener('click',()=>toggleWatch(id));
      row.append(b);list.append(row);
    }
    panel.append(list);
  }
  if(warnings.length)panel.append(el('p',warnings.join(' · '),'hub-note'));
  panel.append(el('p','Watchlist is saved only in your browser. Market data is provider-reported and does not verify ownership.','hub-meta'));
}
let currentPage=0,currentSource='lore';
const pageInfo=$('universe-progress');
async function loadUniverse({search=null,next=false}={}){
  const source=$('market-source').value;
  if(source!==currentSource){currentPage=0;currentSource=source;}
  if(search!==null)currentPage=0;
  else if(next)currentPage++;
  else currentPage=0;
  const button=$('next-page');button.disabled=true;
  const panel=$('universe-results');
  panel.replaceChildren(el('p','Loading source-backed data…','hub-note'));
  pageInfo.textContent='Retrieving '+source.toUpperCase()+' page '+(currentPage+1);
  try{
    let url;
    if(search!==null){
      url=(source==='lore'?'/api/coinlore/search?q=':'/api/catalog/search?q=')+encodeURIComponent(search)+'&limit=40';
      const data=await get(url);
      const rows=data.matches||[];
      panel.replaceChildren(meta(data),rows.length?assetTable(rows,'assets'):el('p','No provider IDs matched your search.','hub-note'));
      pageInfo.textContent=rows.length+' matching catalog IDs'+(typeof data.catalog_count==='number'?' from '+data.catalog_count.toLocaleString('en-US')+' provider catalog IDs':'')+' · active trading not verified';
      $('universe-source').textContent=data.source||'Catalog search';
      return;
    }
    url=source==='lore'?'/api/coinlore/markets?page='+(currentPage+1)+'&limit=100':
      source==='cg'?'/api/catalog/page?page='+(currentPage+1)+'&limit=100':
      source==='cmc'?'/api/coinmarketcap/active?page='+(currentPage+1)+'&limit=100':
      '/api/coinbase/pairs?offset='+(currentPage*100)+'&limit=100';
    const data=await get(url);
    const rows=source==='coinbase'?data.pairs||[]:data.assets||[];
    panel.replaceChildren(meta(data),rows.length?assetTable(rows,source==='coinbase'?'pairs':'assets'):el('p','No active records returned from the provider on this page.','hub-note'));
    button.disabled=!data.has_more;
    $('universe-source').textContent=data.source||source;
    pageInfo.textContent='Source page '+(currentPage+1)+' · '+rows.length+' records returned';
  }catch(error){
    if(next)currentPage=Math.max(0,currentPage-1);
    panel.replaceChildren(el('p','Provider unavailable: '+error.message,'hub-error'));
    pageInfo.textContent='No active records verified';
  }
}
$('asset-search')?.addEventListener('submit',event=>{
  event.preventDefault();const q=$('search-coins').value.trim();if(q.length>=2)loadUniverse({search:q});
});
$('load-listings')?.addEventListener('click',()=>loadUniverse());
$('next-page')?.addEventListener('click',()=>loadUniverse({next:true}));
$('market-source')?.addEventListener('change',()=>{currentPage=0;$('universe-progress').textContent='Select “Load source listings”'});
$('btcs-fetch')?.addEventListener('click',async()=>{
  const panel=$('btcs-result');panel.replaceChildren(el('p','Checking BTCS via CoinGecko ID bitcoin-silver-2…','hub-note'));
  try{
    const result=await get('/api/asset/quote?id=bitcoin-silver-2');
    if(!result.asset){panel.replaceChildren(el('p','No provider-reported BTCS quote available. BTCS remains in the research catalog.','hub-note'));return;}
    const coin=result.asset;
    panel.replaceChildren(box('hub-quote-grid',
      box('',el('small','Observed USD price'),el('strong',usd(coin.price_usd))),
      box('',el('small','24h reported volume'),el('strong',usd(coin.volume_24h_usd))),
      box('',el('small','Provider rank'),el('strong',coin.rank||'Not ranked')),
      box('',el('small','24h change'),el('strong',pct(coin.change_24h_pct)))),meta(result));
  }catch(e){panel.replaceChildren(el('p','BTCS quote unavailable: '+e.message,'hub-error'));}
});
function newsCard(item){
  const article=el('article',null,'hub-story');
  // Only external article links from the validated publisher feed are shown.
  const anchor=link(item.url,item.title||'Read original article');
  anchor.className='hub-news-title';
  const artwork=el('div',null,'hub-story-artwork');
  const fallback=el('div',null,'hub-story-image-fallback');
  fallback.append(el('span',(item.source||'NEWS').split(/\s+/).map(x=>x[0]).join('').slice(0,2).toUpperCase(),'hub-story-monogram'),el('small','PUBLISHER STORY'));
  artwork.append(fallback);
  if(typeof item.thumbnail_url==='string'&&item.thumbnail_url.startsWith('https://')){
    const img=document.createElement('img');
    img.src=item.thumbnail_url;
    img.alt=''; // Decorative article media; the real article title is adjacent.
    img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';
    img.addEventListener('load',()=>artwork.classList.add('image-ready'));
    img.addEventListener('error',()=>img.remove());
    artwork.append(img);
  }
  const artworkLink=link(item.url,'');
  artworkLink.className='hub-story-art-link';
  artworkLink.setAttribute('aria-label','Read '+(item.title||'article')+' at '+(item.source||'original publisher'));
  artworkLink.append(artwork);
  const sourceRow=el('div',null,'hub-story-byline');
  const faviconWrap=el('span',null,'hub-favicon-wrap');
  faviconWrap.append(el('span',(item.source||'N').slice(0,1),'hub-favicon-fallback'));
  if(typeof item.favicon_url==='string'&&item.favicon_url.startsWith('https://')){
    const favicon=document.createElement('img');
    favicon.src=item.favicon_url;favicon.alt='';favicon.loading='lazy';
    favicon.referrerPolicy='no-referrer';
    favicon.addEventListener('load',()=>faviconWrap.classList.add('icon-ready'));
    favicon.addEventListener('error',()=>favicon.remove());
    faviconWrap.append(favicon);
  }
  sourceRow.append(faviconWrap,el('span',item.source||'Publisher','hub-news-source'));
  const body=el('div',null,'hub-story-body');
  const timestamp=item.published_at?new Date(item.published_at*1000).toLocaleString():'Publisher date unavailable';
  body.append(sourceRow,anchor,el('small',timestamp,'hub-news-date'));
  article.append(artworkLink,body);
  return article;
}
async function loadNews(){
  const panel=$('news-results');if(!panel)return;
  panel.replaceChildren(el('p','Loading publisher-provided headlines and imagery…','hub-note'));
  try{
    const data=await get('/api/news?limit=30');
    const stories=(data.articles||[]).slice(0,30);
    const nodes=stories.map(newsCard);
    panel.replaceChildren(...(nodes.length?nodes:[el('p','No verified publisher headlines returned.','hub-note')]),meta(data));
  }catch(e){panel.replaceChildren(el('p','News sources unavailable: '+e.message,'hub-error'));}
}
$('refresh-news')?.addEventListener('click',loadNews);
$('mining-form')?.addEventListener('submit',async event=>{
  event.preventDefault();
  const form=event.currentTarget,params=new URLSearchParams();
  for(const field of form.elements){
    if(field.name&&field.value!=='')params.set(field.name,field.value);
  }
  const out=$('mining-results');out.replaceChildren(el('p','Calculating assumptions…','hub-note'));
  try{
    const d=await get('/api/mining/estimate?'+params);
    const cards=box('hub-quote-grid',
      box('',el('small','Expected coins / day'),el('strong',compact(d.coin_per_day_expected))),
      box('',el('small','Expected gross / day'),el('strong',usd(d.gross_usd_per_day_expected))),
      box('',el('small','Electricity / day'),el('strong',usd(d.electricity_usd_per_day))),
      box('',el('small','Net before other costs'),el('strong',usd(d.net_usd_per_day_before_other_costs))));
    out.replaceChildren(cards,el('p',d.note,'hub-meta'));
  }catch(e){out.replaceChildren(el('p','Cannot calculate: '+e.message,'hub-error'));}
});
$('reload-watch')?.addEventListener('click',renderWatch);
if($('watch-results'))renderWatch();
if($('news-results'))loadNews();
const initialQuery=new URLSearchParams(location.search).get('search');
if($('search-coins')&&initialQuery&&initialQuery.trim().length>=2&&initialQuery.length<=70){
  $('search-coins').value=initialQuery.trim();
  loadUniverse({search:initialQuery.trim()});
}
// Show real active market rows immediately; the low-volume BTCS quote is an
// optional explicit action, not a failing automatic CoinGecko request.
if($('universe-results')&&!initialQuery)loadUniverse();
if($('mining-network-results'))loadMiningNetworks();
$('refresh-mining')?.addEventListener('click',loadMiningNetworks);

async function loadMiningNetworks(){
  const output=$('mining-network-results');
  if(!output)return;
  output.replaceChildren(el('p','Reading Silver Pool published registry status…','hub-note'));
  try{
    const data=await get('/api/mining/coins');
    const rows=data.coins||[];
    const cards=el('div',null,'hub-source-cards');
    for(const coin of rows){
      const card=el('article',null,'mining-coin');
      const heading=box('hub-panel-head',el('h3',coin.name+' ('+coin.id.toUpperCase()+')'));
      card.append(heading,el('p','Algorithm: '+coin.algorithm));
      card.append(el('p','Pool status: '+coin.status,'hub-mining-status'));
      card.append(el('p','Public mining: '+(coin.public_mining_enabled?'Verified enabled':'Not verified / disabled')));
      card.append(el('p','Network H/s: — · Pool H/s: — · Difficulty: — · Reward: —','hub-note'));
      if(coin.miningpoolstats_url)card.append(link(coin.miningpoolstats_url,'MiningPoolStats external reference'));
      const target=el('button','Estimate with my inputs','hub-estimate-link');
      target.type='button';target.addEventListener('click',()=>{
        document.getElementById('mining')?.scrollIntoView({block:'start',behavior:'smooth'});
        const title=$('estimate-target');if(title)title.textContent='Estimating '+coin.name+' ('+coin.id.toUpperCase()+') — enter real assumptions';
        $('miner-hash')?.focus();
      });
      card.append(target);cards.append(card);
    }
    output.replaceChildren(meta(data),cards);
    try{
      const node=await get('/api/mining/overview');
      const label=box('hub-node-stats',
        el('h3','Verified BTCS node observations'),
        el('p','Height: '+(node.height??'—')+' · Difficulty: '+(node.difficulty??'—')+' · Network H/s: '+(node.network_hashrate_hps??'—')),
        el('p','Source: '+node.source+' · node-only, not Silver Pool pool hashrate or earnings','hub-meta'));
      output.prepend(label);
    }catch{
      output.prepend(el('p','BTCS Core node RPC is not connected to this preview. Network difficulty and hashrate are unavailable.','hub-note'));
    }
  }catch(e){output.replaceChildren(el('p','Coin registry currently unavailable: '+e.message,'hub-error'));}
}
