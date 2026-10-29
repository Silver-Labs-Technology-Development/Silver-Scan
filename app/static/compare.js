/* Source-backed, read-only comparative market analysis. */
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==null&&text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n};
const fmt=n=>Number.isFinite(n)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:3}).format(n):'—';
const dollar=n=>Number.isFinite(n)?'$'+fmt(n):'—';
const percent=n=>Number.isFinite(n)?(n>0?'+':'')+n.toFixed(2)+'%':'—';
async function compare(event){
  event.preventDefault();
  const out=$('compare-results');
  const ids=$('compare-ids').value.toLowerCase().split(',').map(x=>x.trim()).filter(Boolean);
  if(ids.length<2||ids.length>5||new Set(ids).size!==ids.length||ids.some(x=>!/^[a-z0-9][a-z0-9-]{0,99}$/.test(x))){
    out.replaceChildren(el('p','Enter 2 to 5 distinct valid CoinGecko IDs, separated by commas.','hub-error'));return;
  }
  out.replaceChildren(el('p','Loading source-backed market comparisons…','hub-note'));
  try{
    const reply=await fetch('/api/coin-watch/quotes?ids='+encodeURIComponent(ids.join(',')),{headers:{Accept:'application/json'}});
    const data=await reply.json().catch(()=>({error:'Invalid provider response'}));
    if(!reply.ok)throw Error(data.error||'Market provider unavailable');
    const coins=data.assets||[];
    if(!coins.length){out.replaceChildren(el('p','No market quotes available. Your provider IDs may still exist as catalog entries.','hub-note'));return;}
    const missing=ids.filter(id=>!coins.some(c=>c.provider_id===id));
    const title=el('h3','Observed market data ('+coins.length+' of '+ids.length+' IDs)');
    const table=document.createElement('table');table.className='hub-table compare-table';
    const header=document.createElement('thead');const tr=document.createElement('tr');
    ['Coin','Provider ID','Rank','Price USD','24h volume USD','Market cap USD','24h change'].forEach(label=>tr.append(el('th',label)));
    header.append(tr);table.append(header);
    const body=document.createElement('tbody');
    for(const coin of coins){
      const row=document.createElement('tr');
      for(const value of [coin.name,coin.provider_id,coin.rank??'—',dollar(coin.price_usd),dollar(coin.volume_24h_usd),dollar(coin.market_cap_usd),percent(coin.change_24h_pct)])row.append(el('td',value));
      body.append(row);
    }
    table.append(body);
    const scroll=el('div',null,'hub-table-scroll');scroll.append(table);
    const chart=el('div',null,'compare-bars');
    for(const [key,label] of [['market_cap_usd','Market capitalization'],['volume_24h_usd','24-hour reported volume']]){
      const group=el('section',null,'compare-group');group.append(el('h4',label));
      const max=Math.max(0,...coins.map(c=>Number.isFinite(c[key])?c[key]:0));
      for(const coin of coins){
        const row=el('div',null,'compare-bar-row');row.append(el('span',coin.symbol||coin.name));
        const track=el('div',null,'compare-bar-track');
        const fill=el('div',null,'compare-bar-fill');
        fill.style.width=max>0&&Number.isFinite(coin[key])?Math.max(.5,coin[key]/max*100)+'%':'0%';
        track.append(fill);
        row.append(track,el('strong',dollar(coin[key])));group.append(row);
      }
      chart.append(group);
    }
    const notes=el('p','Source: '+(data.source||'CoinGecko')+
      (data.fetched_at?' · '+new Date(data.fetched_at*1000).toLocaleString():'')+
      (data.stale?' · Stale cached data':'')+
      '. Comparisons may use incomplete market observations.','hub-meta');
    out.replaceChildren(title,scroll,chart,notes);
    if(missing.length)out.append(el('p','Provider IDs without current quote: '+missing.join(', '),'hub-note'));
  }catch(e){out.replaceChildren(el('p','Comparison unavailable: '+e.message,'hub-error'));}
}
$('compare-form').addEventListener('submit',compare);
$('compare-form').requestSubmit();
