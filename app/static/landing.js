/* SilverScan public homepage: only on-demand source observations, no demo numbers. */
(() => {
  const $=id=>document.getElementById(id);
  const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined&&value!==null)e.textContent=String(value);if(cls)e.className=cls;return e;};
  const money=n=>typeof n==='number'&&Number.isFinite(n)?'$'+new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n):'—';
  const num=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('en-US').format(n):'—';
  async function get(path){
    const r=await fetch(path,{headers:{Accept:'application/json'}});
    const body=await r.json().catch(()=>({error:'Unreadable provider response'}));
    if(!r.ok)throw Error(body.error||'Source temporarily unavailable');
    return body;
  }
  async function pulse(){
    try{
      const d=await get('/api/market/global');
      $('landing-cap').textContent=money(d.market_cap_usd);
      $('landing-volume').textContent=money(d.volume_24h_usd);
      $('landing-dominance').textContent=typeof d.btc_dominance_pct==='number'?d.btc_dominance_pct.toFixed(1)+'%':'—';
      $('landing-coins').textContent=num(d.active_cryptocurrencies);
      $('landing-market-state').textContent='Observed';
      $('landing-market-source').textContent=(d.source||'External market feed')+
        (d.fetched_at?' · '+new Date(d.fetched_at*1000).toLocaleString():'');
    }catch(e){
      $('landing-market-state').textContent='Feed unavailable';
      $('landing-market-source').textContent='Source observation unavailable; full markets remain accessible.';
    }
  }
  async function highlights(){
    const target=$('landing-market-rows');
    try{
      const data=await get('/api/coinlore/markets?page=1&limit=25');
      const assets=(data.assets||[]).filter(c=>c&&typeof c.name==='string').slice(0,6);
      if(!assets.length)throw Error('No provider rows');
      const items=assets.map(coin=>{
        const card=node('a',null,'scan-market-item');
        card.href='./markets.html';
        const label=node('div');
        label.append(node('strong',coin.name),node('small',(coin.symbol||'').toUpperCase()+' · CoinLore rank '+(coin.rank??'—')));
        card.append(label,node('b',money(coin.price_usd)));
        return card;
      });
      target.replaceChildren(...items);
      $('landing-asset-state').textContent='CoinLore · '+(data.fetched_at?new Date(data.fetched_at*1000).toLocaleTimeString():'provider snapshot');
    }catch(e){
      target.replaceChildren(node('p','Live market highlights are temporarily unavailable. Open the market terminal to retry.','scan-landing-empty'));
      $('landing-asset-state').textContent='Source unavailable';
    }
  }
  pulse();highlights();
})();
