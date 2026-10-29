/* Silver Scan market workspace.
 * All displayed numbers come from named upstream providers. DOM is assembled
 * using textContent, not injected HTML. No coin listing implies endorsement.
 */
import {sparkline,timeSeries,dominanceRing,sentimentGauge} from './charts.js';
const $=id=>document.getElementById(id);
const research=$('research-view'),explorer=$('view'),overview=$('market-overview'),controls=$('explorer-controls');
const tabs=[...document.querySelectorAll('[data-tab]')];
const WATCH_KEY='silver-scan-coin-watch-v1',THEME_KEY='silver-scan-theme-v1';
const moneyFmt=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});
const compactFmt=new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2});
const numberFmt=new Intl.NumberFormat('en-US',{maximumFractionDigits:0});
const state={tab:'markets',market:null,global:null,sentiment:null,sort:'rank',direction:1,query:'',page:0,selected:null};
const perPage=25;
function el(tag,text=null,cls=''){
  const item=document.createElement(tag);if(text!==null&&text!==undefined)item.textContent=String(text);
  if(cls)item.className=cls;return item;
}
function wrap(cls,...children){const d=el('div',null,cls);d.append(...children);return d;}
function button(label,callback,cls=''){
  const b=el('button',label,cls);b.type='button';b.addEventListener('click',callback);return b;
}
function link(url,label){
  const a=el('a',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;
}
function finite(n){return typeof n==='number'&&Number.isFinite(n);}
function money(n){if(!finite(n))return '—';if(Math.abs(n)>0&&Math.abs(n)<.01)return '$'+n.toLocaleString('en-US',{maximumSignificantDigits:5});return moneyFmt.format(n);}
function usdCompact(n){if(!finite(n))return '—';return Math.abs(n)>=1e4?'$'+compactFmt.format(n):money(n);}
function count(n){return finite(n)?numberFmt.format(n):'—';}
function pct(n){return finite(n)?(n>0?'+':'')+n.toFixed(2)+'%':'—';}
function change(n){const span=el('span',pct(n),'change');if(finite(n))span.classList.add(n>=0?'up':'down');return span;}
function source(data){
  const row=wrap('source-line',el('span','Source: '+(data?.source||'Unavailable'),'provider-pill'));
  if(data?.fetched_at)row.append(el('span','Retrieved '+new Date(data.fetched_at*1000).toLocaleString()));
  if(data?.stale)row.append(el('strong','STALE cached data','down'));
  return row;
}
function errorMessage(text){return el('p',text,'notice error');}
function display(...nodes){research.replaceChildren(...nodes);}
async function fetchJson(path){
  const response=await fetch(path,{headers:{Accept:'application/json'}});
  let result;try{result=await response.json();}catch{throw Error('Invalid provider response');}
  if(!response.ok)throw Error(result?.error||'Backend unavailable ('+response.status+')');
  return result;
}
function watchIds(){
  try{
    const parsed=JSON.parse(localStorage.getItem(WATCH_KEY)||'[]');
    return Array.isArray(parsed)?parsed.filter(i=>typeof i==='string'&&/^coingecko:[a-z0-9-]+$/.test(i)).slice(0,200):[];
  }catch{return [];}
}
function toggleWatch(asset){
  const ids=watchIds();
  const next=ids.includes(asset.id)?ids.filter(i=>i!==asset.id):[...ids,asset.id].slice(0,200);
  try{localStorage.setItem(WATCH_KEY,JSON.stringify(next));}catch{return false;}
  if(state.selected&&state.selected.id===asset.id)openAsset(state.selected.provider_id);
  else if(state.tab==='markets'||state.tab==='watch')paintTable();
  return true;
}
function star(asset){
  const active=watchIds().includes(asset.id);
  const b=button(active?'★':'☆',()=>{
    if(!toggleWatch(asset))b.title='Browser storage unavailable';
  },'watch-button');
  b.setAttribute('aria-pressed',String(active));b.setAttribute('aria-label',(active?'Remove from':'Add to')+' Coin Watch '+(asset.name||asset.id));
  b.title=active?'Remove from Coin Watch':'Add to Coin Watch';return b;
}
function icon(asset){
  if(typeof asset?.icon==='string'&&/^https:\/\/(coin-images\.coingecko\.com|assets\.coingecko\.com)\//.test(asset.icon)){
    const image=el('img',null,'coin-icon');image.src=asset.icon;image.alt='';image.loading='lazy';image.referrerPolicy='no-referrer';
    image.addEventListener('error',()=>image.replaceWith(el('span',(asset.symbol||'?').charAt(0).toUpperCase(),'coin-fallback')),{once:true});
    return image;
  }
  return el('span',(asset?.symbol||'?').charAt(0).toUpperCase(),'coin-fallback');
}
function setText(id,value){const item=$(id);if(item)item.textContent=String(value);}
function status(message,data=null){
  setText('data-state',message);
  setText('last-updated',data?.fetched_at?'Retrieved: '+new Date(data.fetched_at*1000).toLocaleString():'Updated: —');
}
const titles={
  markets:['Cryptocurrency Prices by Market Cap','Track cryptocurrency prices, global statistics, seven-day trends, market sentiment and detailed asset research.'],
  watch:['Coin Watch','Your saved coins, private to this browser. Market coverage depends on the data provider.'],
  mining:['Mining & Pool Intelligence','Verified Bitcoin Silver node metrics and independent references for other mining networks.'],
  dex:['DEX Scan','Discover token pairs, liquidity and DEX activity. Results are external observations, not verified listings.'],
  explorer:['Blockchain Explorer','Search Bitcoin Silver L1 blocks, transactions and indexed address history.']
};
function setTheme(theme){
  const val=theme==='dark'?'dark':'light';
  document.documentElement.dataset.theme=val;
  $('theme-toggle').textContent=val==='dark'?'☀':'◐';
  $('theme-toggle').setAttribute('aria-label','Switch to '+(val==='dark'?'light':'dark')+' theme');
  try{localStorage.setItem(THEME_KEY,val);}catch{}
}
function setupTheme(){
  let stored='light';try{stored=localStorage.getItem(THEME_KEY)||'light';}catch{}
  setTheme(stored);
  $('theme-toggle').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
}
function switchTab(tab){
  if(!titles[tab])tab='markets';
  state.tab=tab;state.selected=null;state.page=0;
  for(const item of tabs){
    const selected=item.dataset.tab===tab;
    item.classList.toggle('selected',selected);item.setAttribute('aria-pressed',String(selected));
  }
  overview.hidden=!['markets','watch'].includes(tab);
  controls.hidden=tab!=='explorer';explorer.hidden=tab!=='explorer';research.hidden=tab==='explorer';
  const [title,description]=titles[tab];
  setText('page-title',title);setText('page-description',description);
  status(tab==='explorer'?'Node-backed information':'Provider-backed market data');
  if(tab==='markets'||tab==='watch')loadMarket();
  else if(tab==='dex')renderDex();
  else if(tab==='mining')renderMining();
  if(location.hash!=='#'+tab)history.replaceState(null,'','#'+tab);
}
async function loadGlobal(){
  try{
    const g=await fetchJson('/api/market/global');state.global=g;
    setText('metric-cap',usdCompact(g.market_cap_usd));
    setText('metric-volume',usdCompact(g.volume_24h_usd));
    setText('metric-btc',finite(g.btc_dominance_pct)?g.btc_dominance_pct.toFixed(2)+'%':'—');
    setText('metric-coins',count(g.active_cryptocurrencies));
    setText('metric-cap-change',finite(g.market_cap_change_24h_pct)?pct(g.market_cap_change_24h_pct)+' over 24h':'24h change unavailable');
    const changeNode=$('metric-cap-change');
    changeNode.classList.remove('up','down');
    if(finite(g.market_cap_change_24h_pct))changeNode.classList.add(g.market_cap_change_24h_pct>=0?'up':'down');
    setText('market-coins',count(g.active_cryptocurrencies));
    setText('market-cap-top',usdCompact(g.market_cap_usd));
    setText('market-volume-top',usdCompact(g.volume_24h_usd));
    setText('market-btc-top',finite(g.btc_dominance_pct)?g.btc_dominance_pct.toFixed(1)+'%':'—');
    setText('market-source-top','Source: CoinGecko'+(g.stale?' · stale':''));
  }catch{
    setText('metric-cap-change','Global market overview unavailable');
    setText('market-source-top','Market totals unavailable');
  }
  if(state.market&&state.tab==='markets')renderMarketHome();
}
async function loadSentiment(){
  try{state.sentiment=await fetchJson('/api/market/sentiment?days=30');}
  catch{state.sentiment=null;}
  if(state.market&&state.tab==='markets')renderMarketHome();
}
function panel(cls,...children){return wrap('panel '+cls,...children);}
function sectionHeading(name,sub=''){return wrap('section-head',wrap('',el('h2',name),el('p',sub)));}
function marketHighlights(){
  if(!state.market)return null;
  const assets=state.market.assets.filter(c=>finite(c.change_24h_pct));
  const movers=[...assets].sort((a,b)=>b.change_24h_pct-a.change_24h_pct);
  const out=wrap('top-highlights');
  for(const [title,list] of [['Top Gainers',movers.slice(0,3)],['Top Losers',movers.slice(-3).reverse()]]){
    const body=panel('highlight-panel');
    body.append(wrap('panel-head',el('h3',title),el('span','TOP 100 SNAPSHOT','tiny-label')));
    const ol=el('ol',null,'highlight-list');
    list.forEach((coin,i)=>{
      const row=el('li',null,'highlight-row');
      row.append(el('span',String(i+1),'position'),button((coin.name||coin.provider_id),()=>openAsset(coin.provider_id),'grow'),change(coin.change_24h_pct));
      ol.append(row);
    });
    if(!list.length)ol.append(el('li','Market movement data unavailable','muted'));
    body.append(ol);out.append(body);
  }
  const feature=panel('highlight-panel featured-panel');
  feature.append(wrap('panel-head',el('h3','Featured network'),el('span','SILVER LABS','featured-label')));
  feature.append(el('h2','Bitcoin Silver · BTCS'),el('p','Discover BTCS L1 chain activity and network mining information. Market data availability is independent of node connectivity.'));
  feature.append(button('View BTCS mining data',()=>switchTab('mining'),'featured-cta'));
  out.append(feature);
  return out;
}
function sentimentCard(){
  const card=panel('data-visual-card');
  card.append(wrap('panel-head',el('h3','Crypto Fear & Greed'),el('span','MARKET SENTIMENT','tiny-label')));
  const data=state.sentiment;
  if(!data){
    card.append(el('p','Sentiment provider unavailable. No score is estimated.','muted'));
  } else {
    card.append(sentimentGauge(data.score,data.classification));
    const history=data.history?.map(p=>[p.timestamp*1000,p.value])||[];
    if(history.length>1)card.append(timeSeries(history,{kind:'sentiment',label:'Alternative.me Fear and Greed historical observations'}));
    card.append(source(data));
  }
  card.append(link('https://alternative.me/crypto/fear-and-greed-index/','Source: Alternative.me Fear & Greed Index'));
  card.append(el('p','The index summarizes general crypto sentiment, not BTCS sentiment or an investment signal.','research-note'));
  return card;
}
function dominanceCard(){
  const card=panel('data-visual-card');
  card.append(wrap('panel-head',el('h3','Market Dominance'),el('span','MARKET CAP SHARE','tiny-label')));
  const g=state.global;
  card.append(dominanceRing(g?.btc_dominance_pct,g?.eth_dominance_pct));
  if(g)card.append(source(g));
  else card.append(el('p','Global market data unavailable.','muted'));
  return card;
}
function tableCoinRows(coins){
  const tbody=el('tbody');
  coins.forEach((coin)=>{
    const tr=el('tr');
    const td=val=>{const item=el('td');if(val instanceof Node)item.append(val);else item.textContent=String(val??'—');tr.append(item);return item;};
    td(coin.rank??'—');
    const cell=td('');
    const name=button(coin.name||coin.provider_id,()=>openAsset(coin.provider_id),'coin-button');
    const text=wrap('coin-text',name,el('span',(coin.symbol||'—').toUpperCase(),'ticker'));
    cell.append(wrap('coin-cell',icon(coin),text));
    td(money(coin.price_usd));
    td(change(coin.change_1h_pct));td(change(coin.change_24h_pct));td(change(coin.change_7d_pct));
    td(usdCompact(coin.market_cap_usd));td(usdCompact(coin.volume_24h_usd));
    td(count(coin.circulating_supply));
    td(sparkline(coin.sparkline_7d,coin.change_7d_pct));
    td(star(coin));
    tbody.append(tr);
  });
  return tbody;
}
function filtered(){
  let coins=[...(state.market?.assets||[])];
  if(state.tab==='watch'){
    const watched=new Set(watchIds());
    coins=coins.filter(coin=>watched.has(coin.id));
  }
  const q=state.query.trim().toLowerCase();
  if(q)coins=coins.filter(c=>(c.name||'').toLowerCase().includes(q)||(c.symbol||'').toLowerCase().includes(q)||(c.provider_id||'').includes(q));
  const key={rank:'rank',price:'price_usd',change:'change_24h_pct',cap:'market_cap_usd',volume:'volume_24h_usd'}[state.sort]||'rank';
  coins.sort((a,b)=>{
    const x=a[key],y=b[key];
    if(x==null&&y==null)return 0;
    if(x==null)return 1;if(y==null)return -1;
    return (x-y)*state.direction;
  });
  return coins;
}
function paintTable(){
  if(!state.market)return;
  const existing=$('markets-table-section');
  if(!existing)return;
  const box=buildMarketTable();
  existing.replaceWith(box);
}
function buildMarketTable(){
  const coins=filtered();const pages=Math.max(1,Math.ceil(coins.length/perPage));
  state.page=Math.min(state.page,pages-1);
  const shown=coins.slice(state.page*perPage,(state.page+1)*perPage);
  const holder=panel('panel-tight');holder.id='markets-table-section';
  const title=wrap('',el('h2',state.tab==='watch'?'Your watched cryptocurrencies':'All Cryptocurrencies'));
  title.append(el('p','Provider-ranked top 100 snapshot · filter and sort currently loaded assets','research-note'));
  const search=el('input');search.type='search';search.placeholder='Filter name or ticker';search.value=state.query;
  search.setAttribute('aria-label','Filter current coin list');
  const sort=el('select');sort.setAttribute('aria-label','Sort cryptocurrency table');
  const options=[['rank','Market cap rank'],['cap','Market capitalization'],['price','Coin price'],['change','24h price change'],['volume','24h volume']];
  options.forEach(([value,name])=>{const item=el('option',name);item.value=value;sort.append(item);});
  sort.value=state.sort;
  const direction=button(state.direction===1?'Ascending ↑':'Descending ↓',()=>{state.direction*=-1;state.page=0;paintTable();},'tab-button');
  const controls=wrap('toolbar-controls',search,sort,direction);
  search.addEventListener('input',()=>{
    state.query=search.value;state.page=0;
    // Only the table needs replacement; retain focus after filtering.
    const start=search.selectionStart;
    paintTable();
    const next=document.querySelector('#markets-table-section input');
    if(next){next.focus();try{next.setSelectionRange(start,start);}catch{}}
  });
  sort.addEventListener('change',()=>{state.sort=sort.value;state.page=0;paintTable();});
  holder.append(wrap('table-toolbar',title,controls));
  const table=el('table',null,'market-table');
  const head=el('thead');const tr=el('tr');
  ['#','Coin','Price','1h %','24h %','7d %','Market cap','24h volume','Circulating supply','Last 7 days','Watch'].forEach(name=>tr.append(el('th',name)));
  head.append(tr);table.append(head,tableCoinRows(shown));
  holder.append(wrap('table-scroll',table));
  if(!shown.length)holder.append(el('p',state.tab==='watch'?'No watched coins in the provider top-100 snapshot. Watch assets with the star icon.':'No assets matched your filter.','empty-panel'));
  const footer=wrap('table-footer',el('span','Showing '+(shown.length?state.page*perPage+1:0)+'–'+(state.page*perPage+shown.length)+' of '+coins.length+' visible assets'));
  const pagination=wrap('pagination');
  const prev=button('Previous',()=>{state.page--;paintTable();});
  prev.disabled=state.page===0;
  const next=button('Next',()=>{state.page++;paintTable();});
  next.disabled=state.page>=pages-1;
  pagination.append(prev,el('span','Page '+(state.page+1)+' / '+pages),next);
  footer.append(pagination);holder.append(footer);
  return holder;
}
function renderMarketHome(){
  if(!state.market)return;
  const title=sectionHeading(state.tab==='watch'?'Your Coin Watch':'Crypto Market Overview',state.tab==='watch'?'Browser-local watchlist, updated with current provider data.':'Rankings, real provider sparklines, sentiment and market breadth.');
  const nodes=[title];
  if(state.tab==='markets'){
    const highlights=marketHighlights();if(highlights)nodes.push(highlights);
    nodes.push(sectionHeading('Market Intelligence','Independent sources, explicitly identified.'));
    nodes.push(wrap('visualization-grid',dominanceCard(),sentimentCard()));
  }
  nodes.push(buildMarketTable(),source(state.market),el('p','Market snapshots are not complete exchange listings. The symbol of a coin is not a verified contract or network identifier.','research-note'));
  display(...nodes);
}
async function loadMarket(){
  if(state.market){
    status(state.market.stale?'Showing stale market snapshot':'CoinGecko market snapshot',state.market);
    renderMarketHome();return;
  }
  display(el('p','Loading cryptocurrency market data and real charts…','loading-panel'));
  try{
    const data=await fetchJson('/api/markets?limit=100');
    if(!Array.isArray(data.assets))throw Error('Market provider returned an invalid asset list');
    state.market=data;
    status(data.stale?'STALE: provider response cached':'CoinGecko market snapshot',data);
    renderMarketHome();
  }catch(error){status('Market source unavailable');display(errorMessage(error.message+' · No illustrative market numbers will be shown.'));}
}
function metric(label,value){const d=el('div',null,'detail-stat');d.append(el('dt',label),el('dd',value));return d;}
async function openAsset(id){
  if(!/^[a-z0-9][a-z0-9-]{0,99}$/.test(id))return;
  state.selected={id:'coingecko:'+id,provider_id:id};
  overview.hidden=true;
  setText('page-title','Coin research');
  setText('page-description','Detailed market profile, historical price data, supply and network identity.');
  display(el('p','Loading provider coin profile…','loading-panel'));
  try {
    const profile=await fetchJson('/api/assets/profile?id='+encodeURIComponent(id));
    state.selected=profile;
    setText('page-title',(profile.name||id)+' ('+(profile.symbol||'').toUpperCase()+')');
    setText('page-description','Markets, historical prices, supply, contracts and independent reference links.');
    status('CoinGecko asset profile',profile);
    const heading=wrap('breadcrumbs',button('← Back to '+(state.tab==='watch'?'Coin Watch':'Markets'),()=>{
      overview.hidden=false;setText('page-title',titles[state.tab][0]);setText('page-description',titles[state.tab][1]);renderMarketHome();
    }));
    const name=wrap('asset-main',icon(profile),wrap('',el('h2',(profile.name||id)),el('span',(profile.symbol||'').toUpperCase()+' · Rank '+(profile.rank||'—'),'asset-symbol')));
    const price=wrap('asset-price',el('strong',money(profile.price_usd)),change(profile.change_24h_pct));
    const head=panel('asset-head',name,price);
    const chartBox=panel('chart-card');
    const ranges=wrap('chart-range');
    const slot=wrap('chart-wrap',el('p','Loading real price history…','muted'));
    chartBox.append(wrap('panel-head',wrap('',el('h3','Price History · USD'),el('p','CoinGecko observed prices, not exchange trades executed by Silver Labs.','research-note')),ranges),slot);
    const rangesInfo=[[1,'24H'],[7,'7D'],[30,'30D'],[90,'90D'],[365,'1Y']];
    let chartRequest=0;
    const loadChart=async days=>{
      const request=++chartRequest;
      ranges.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.days)===days)));
      slot.replaceChildren(el('p','Loading '+days+'-day history…','muted'));
      try{
        const data=await fetchJson('/api/assets/chart?id='+encodeURIComponent(id)+'&days='+days);
        if(request!==chartRequest)return;
        slot.replaceChildren(timeSeries(data.points,{label:'Historical '+days+' day USD price trend'}),source(data));
      }catch(error){if(request===chartRequest)slot.replaceChildren(errorMessage('Chart unavailable: '+error.message));}
    };
    rangesInfo.forEach(([days,label])=>{
      const b=button(label,()=>loadChart(days));b.dataset.days=String(days);b.setAttribute('aria-pressed',String(days===7));ranges.append(b);
    });
    const grid=wrap('detail-stat-grid',
      metric('Market cap',usdCompact(profile.market_cap_usd)),metric('24h volume',usdCompact(profile.volume_24h_usd)),
      metric('Fully diluted valuation',usdCompact(profile.fdv_usd)),metric('Circulating supply',count(profile.circulating_supply)),
      metric('Total supply',count(profile.total_supply)),metric('Maximum supply',count(profile.max_supply)),
      metric('24h high',money(profile.high_24h_usd)),metric('24h low',money(profile.low_24h_usd)),
      metric('All-time high',money(profile.ath_usd)),metric('All-time low',money(profile.atl_usd))
    );
    const stats=panel('asset-metrics',el('h3','Coin Statistics'),grid);
    const details=panel('',el('h3','About '+(profile.name||id)),el('p',profile.description||'A description is not available from this data provider.','research-note'));
    details.append(source(profile),el('p',profile.note,'research-note'));
    const network=panel('',el('h3','Networks & Contract Identifiers'));
    if(profile.contracts?.length){
      for(const c of profile.contracts.slice(0,20)){
        network.append(wrap('contract-row',el('strong',c.network),el('code',c.contract)));
      }
    } else network.append(el('p','No provider-platform contract references returned. No chain identity inferred.','research-note'));
    if(profile.resources?.length){
      const row=wrap('asset-resources');
      profile.resources.forEach(item=>row.append(link(item.url,item.label)));
      network.append(el('h3','Project references'),row);
    }
    const first=wrap('asset-grid',chartBox,stats),second=wrap('asset-extra',details,network);
    const watch=button(watchIds().includes(profile.id)?'★ Watching':'☆ Add to Coin Watch',()=>{
      if(!toggleWatch(profile))watch.title='Browser storage unavailable';
    },'tab-button');
    display(heading,head,wrap('asset-actions',watch),first,second);
    loadChart(7);
  }catch(error){display(errorMessage('Coin profile unavailable: '+error.message),button('Return to market table',()=>{overview.hidden=false;renderMarketHome();}));}
}
function renderDex(){
  const heading=sectionHeading('DEX Pair Discovery','Search by token name, pair or contract. Compare results by chain, DEX and pair identity.');
  const form=el('form',null,'research-form');
  const input=el('input');input.type='search';input.minLength=2;input.maxLength=80;input.required=true;input.placeholder='e.g. token name or 0x contract address';input.setAttribute('aria-label','Search external DEX pairs');
  const submit=el('button','Search pairs');submit.type='submit';
  form.append(input,submit);
  const output=wrap('dex-results',el('p','Enter a query to search externally observed pairs.','empty-panel'));
  form.addEventListener('submit',async ev=>{
    ev.preventDefault();output.replaceChildren(el('p','Searching DEX Screener…','loading-panel'));
    try{
      const data=await fetchJson('/api/dex/search?q='+encodeURIComponent(input.value.trim()));
      const table=el('table',null,'dex-table'),thead=el('thead'),tr=el('tr');
      ['Pair / Network','DEX','Price USD','Liquidity USD','24h Volume','Source'].forEach(h=>tr.append(el('th',h)));thead.append(tr);table.append(thead);
      const body=el('tbody');
      data.pairs.forEach(p=>{
        const r=el('tr'),identity=wrap('',el('strong',(p.base_token?.symbol||'?')+'/'+(p.quote_token?.symbol||'?')),el('div',p.chain_id+' · '+p.pair_address,'research-note'));
        [identity,p.dex_id||'—',p.price_usd?('$'+p.price_usd):'—',usdCompact(p.liquidity_usd),usdCompact(p.volume_24h_usd),p.source_url?link(p.source_url,'View source'):'—'].forEach(v=>{
          const cell=el('td');if(v instanceof Node)cell.append(v);else cell.textContent=v;r.append(cell);
        });body.append(r);
      });table.append(body);
      output.replaceChildren(source(data),el('p',data.note,'research-note'));
      if(data.pairs.length)output.append(wrap('table-scroll',table));else output.append(el('p','No source pairs matched this search.','empty-panel'));
    }catch(error){output.replaceChildren(errorMessage(error.message));}
  });
  display(heading,panel('',form,output),el('p','External DEX pair data is not an endorsement of token legitimacy, liquidity availability or a supported SilvEx swap.','research-note'));
}
async function renderMining(){
  display(sectionHeading('Mining & Pool Statistics','Node-provided BTCS network metrics. Other mining networks need their own independently verified adapters.'),el('p','Checking connected BTCS node…','loading-panel'));
  const header=sectionHeading('Bitcoin Silver · BTCS','Featured mining network · network data is not Silver Pool operator statistics.');
  const learn=panel('featured-panel',el('h3','Compare mining pools'),el('p','MiningPoolStats is an external directory. Its listed pools and rankings are independent of Silver Labs.','research-note'),link('https://miningpoolstats.stream/bitcoinsilver','View BTCS on MiningPoolStats'));
  const infoPanel=panel('',el('h3','Mining coverage'),el('p','Silver Scan can add independently verified per-chain and per-pool adapters. Cataloging coins does not mean their mining services or data feeds are operational.','research-note'));
  try{
    const d=await fetchJson('/api/mining/overview');
    const grid=wrap('mining-grid',
      metric('Network',d.network||'Unavailable'),metric('BTCS block height',count(d.height)),
      metric('Network difficulty',finite(d.difficulty)?count(d.difficulty):'—'),
      metric('Network hashrate H/s',finite(d.network_hashrate_hps)?compactFmt.format(d.network_hashrate_hps)+' H/s':'—')
    );
    display(header,panel('',grid,el('p',d.note,'research-note'),el('p','Source: '+d.source,'research-note')),learn,infoPanel);
  }catch(error){
    display(header,errorMessage('BTCS node mining information unavailable: '+error.message),learn,infoPanel);
  }
}
function bindSearch(){
  const form=$('global-search-form'),input=$('global-search');
  form.addEventListener('submit',event=>{
    event.preventDefault();
    state.query=input.value.trim();state.page=0;
    if(state.tab!=='markets'&&state.tab!=='watch')switchTab('markets');
    else if(state.selected){state.selected=null;overview.hidden=false;renderMarketHome();}
    else paintTable();
    document.querySelector('#markets-table-section')?.scrollIntoView({behavior:'smooth',block:'start'});
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='/'&&!(event.target instanceof HTMLInputElement)&&!(event.target instanceof HTMLTextAreaElement)){
      event.preventDefault();input.focus();
    }
  });
}
function start(){
  setupTheme();bindSearch();
  tabs.forEach(item=>item.addEventListener('click',()=>switchTab(item.dataset.tab)));
  loadGlobal();loadSentiment();
  const tab=location.hash.slice(1);
  switchTab(titles[tab]?tab:'markets');
}
start();
