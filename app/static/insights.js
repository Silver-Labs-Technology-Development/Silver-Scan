/* SilverScan market insight modules. Provider data is displayed only if available. */
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n};
const group=(cls,...children)=>{const n=node('div',null,cls);n.append(...children);return n};
const fmt=n=>Number.isFinite(n)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n):'—';
const usd=n=>Number.isFinite(n)?'$'+fmt(n):'—';
const percentage=n=>Number.isFinite(n)?(n>0?'+':'')+n.toFixed(2)+'%':'—';
const source=data=>node('p',(data.source||'Unknown source')+(data.fetched_at?' · '+new Date(data.fetched_at*1000).toLocaleString():'')+(data.stale?' · STALE SNAPSHOT':''),'hub-meta');
const a=(href,text)=>{const n=node('a',text);n.href=href;return n};
const safeStatus=(id,msg)=>document.getElementById(id).replaceChildren(node('p',msg,'hub-note'));
async function fetchData(url){
  const reply=await fetch(url,{headers:{Accept:'application/json'}});
  const data=await reply.json().catch(()=>({error:'Unreadable provider response'}));
  if(!reply.ok)throw Error(data.error||'Unavailable (HTTP '+reply.status+')');
  return data;
}
function stat(name,value){
  return group('insight-stat',node('small',name),node('strong',value));
}
async function trending(){
  const target=document.getElementById('insights-trending');safeStatus('insights-trending','Loading provider trends…');
  try{
    const data=await fetchData('/api/insights/trending');
    const cards=(data.coins||[]).map((coin,i)=>{
      const card=node('article',null,'insight-card');
      card.append(node('span',String(i+1).padStart(2,'0')+' · TRENDING SEARCH','insight-rank'),
        node('h3',coin.name||coin.provider_id),
        node('p',(coin.symbol||'').toUpperCase()+' · '+(Number.isInteger(coin.rank)?'Market rank '+coin.rank:'Rank unavailable'),'hub-note'));
      const link=a('./coin-watch.html?search='+encodeURIComponent(coin.provider_id),'Research provider ID →');card.append(link);
      return card;
    });
    target.replaceChildren(...(cards.length?cards:[node('p','No trending search observations available.','hub-note')]));
    target.append(source(data));
  }catch(e){safeStatus('insights-trending','Trending data unavailable: '+e.message);}
}
async function categories(){
  const target=document.getElementById('insights-categories');safeStatus('insights-categories','Loading sector analytics…');
  try{
    const data=await fetchData('/api/insights/categories?limit=30');
    const rows=(data.categories||[]).map(item=>{
      const row=group('insight-row',group('insight-row-name',node('strong',item.name),node('small','Provider sector · '+item.id)),
        stat('Sector cap',usd(item.market_cap_usd)),stat('24h change',percentage(item.change_24h_pct)),stat('24h volume',usd(item.volume_24h_usd)));
      const change=item.change_24h_pct;
      if(Number.isFinite(change)){
        const bar=node('div',null,'insight-change');
        bar.classList.add(change>=0?'change-up':'change-down');
        const fill=node('div',null,'insight-change-fill');fill.style.width=Math.min(100,Math.abs(change)*8+5)+'%';
        bar.append(fill);row.append(bar);
      }
      return row;
    });
    target.replaceChildren(...(rows.length?rows:[node('p','No category market statistics available.','hub-note')]),source(data));
  }catch(e){safeStatus('insights-categories','Sector data unavailable: '+e.message);}
}
let exchangePage=1;
async function exchanges(next=false){
  const target=document.getElementById('insights-exchanges'),more=document.getElementById('more-exchanges');
  const provider=document.getElementById('exchange-provider').value;
  const sort=document.getElementById('exchange-sort').value;
  const page=next?exchangePage+1:1;more.disabled=true;
  safeStatus('insights-exchanges','Loading '+(provider==='cg'?'CoinGecko market':'CoinMarketCap exchange ID')+' page '+page+'…');
  try{
    const data=await fetchData(provider==='cg'?
      '/api/insights/exchanges?page='+page+'&limit=30':
      '/api/exchanges/cmc?page='+page+'&limit=30');
    exchangePage=page;more.disabled=!data.has_more;
    const exchanges=(data.exchanges||[]).slice();
    if(provider==='cg'){
      const sortOrder={
        trust:(a,b)=>(b.trust_score??-1)-(a.trust_score??-1),
        volume:(a,b)=>(b.trade_volume_24h_btc??-1)-(a.trade_volume_24h_btc??-1),
        rank:(a,b)=>(a.rank??999999)-(b.rank??999999),
        name:(a,b)=>a.name.localeCompare(b.name)
      };
      exchanges.sort(sortOrder[sort]||sortOrder.trust);
    }else{
      // CMC keyless /exchange/map does not supply exchange rank or volume.
      // Do not substitute CoinGecko measurements using an ambiguous name match.
      exchanges.sort((a,b)=>a.name.localeCompare(b.name));
    }
    const rows=exchanges.map(exchange=>{
      const card=group('insight-row',group('insight-row-name',
        node('strong',exchange.name),
        node('small',provider==='cg'?(exchange.country||'Country unavailable'):exchange.id+' · '+(exchange.tracked?'Tracked market':'Unverified status'))));
      if(provider==='cg'){
        card.append(stat('Provider rank',exchange.rank||'—'),
          stat('Trust score',Number.isFinite(exchange.trust_score)?exchange.trust_score.toFixed(0)+'/10':'—'),
          stat('24h BTC volume',fmt(exchange.trade_volume_24h_btc)));
        if(typeof exchange.website==='string'&&exchange.website.startsWith('https://')){
          const a=document.createElement('a');a.href=exchange.website;a.rel='noopener noreferrer';a.target='_blank';a.textContent='Website ↗';card.append(a);
        }
      }else{
        card.append(stat('Market tracking',exchange.tracked?'Active':'Unknown'),
          stat('Provider ID',exchange.id),stat('Volume / score','Not provided'));
      }
      return card;
    });
    target.replaceChildren(...(rows.length?rows:[node('p','No exchange records returned for this source page.','hub-note')]),source(data));
    document.getElementById('exchange-status').textContent=(provider==='cg'?'CoinGecko':'CoinMarketCap')+
      ' page '+exchangePage+' · '+rows.length+' venues; comparison is limited to this source page';
  }catch(e){safeStatus('insights-exchanges','External exchange data unavailable: '+e.message);more.disabled=false;}
}
document.getElementById('exchange-provider')?.addEventListener('change',()=>exchanges(false));
document.getElementById('exchange-sort')?.addEventListener('change',()=>exchanges(false));
async function defi(){
  const target=document.getElementById('insights-defi');safeStatus('insights-defi','Loading DeFi statistics…');
  try{
    const data=await fetchData('/api/insights/defi');
    const info=[
      stat('Global DeFi market cap',usd(data.market_cap_usd)),
      stat('24h DeFi volume',usd(data.volume_24h_usd)),
      stat('Reported DeFi dominance',percentage(data.dominance_pct)),
      stat('DeFi / ETH ratio',percentage(data.defi_to_eth_ratio_pct)),
      stat('Provider top coin',data.top_coin_name||'—')];
    target.replaceChildren(...info,source(data));
  }catch(e){safeStatus('insights-defi','DeFi market data unavailable: '+e.message);}
}
document.getElementById('reload-trending')?.addEventListener('click',trending);
document.getElementById('reload-categories')?.addEventListener('click',categories);
document.getElementById('reload-exchanges')?.addEventListener('click',()=>exchanges(false));
document.getElementById('more-exchanges')?.addEventListener('click',()=>exchanges(true));
document.getElementById('reload-defi')?.addEventListener('click',defi);
trending();categories();exchanges();defi();
