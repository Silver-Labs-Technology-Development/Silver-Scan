/* Public exchange directory: only source-backed records, no cross-provider merging. */
(() => {
  const $=id=>document.getElementById(id);
  const el=(tag,value,klass)=>{const n=document.createElement(tag);if(value!==null&&value!==undefined)n.textContent=String(value);if(klass)n.className=klass;return n;};
  let page=1,more=false;
  const fmt=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n):'—';
  async function load(){
    const provider=$('exchange-provider').value;
    const limit=Number($('exchange-limit').value);
    const out=$('exchange-results');
    $('exchange-previous').disabled=true;$('exchange-next').disabled=true;
    out.replaceChildren(el('p','Loading source-attributed exchange records…','hub-note'));
    const path=provider==='cmc'?'/api/exchanges/cmc':'/api/exchanges/coingecko';
    try{
      const r=await fetch(path+'?page='+page+'&limit='+limit,{headers:{Accept:'application/json'}});
      const data=await r.json().catch(()=>({error:'Unreadable exchange response'}));
      if(!r.ok)throw Error(data.error||'Provider did not return exchange data');
      const venues=Array.isArray(data.exchanges)?data.exchanges.slice():[];
      const order=$('exchange-order').value;
      if(order==='name')venues.sort((a,b)=>String(a.name||'').localeCompare(String(b.name||'')));
      if(provider==='cg'&&order==='rank')venues.sort((a,b)=>(a.rank??999999)-(b.rank??999999));
      if(provider==='cg'&&order==='trust')venues.sort((a,b)=>(b.trust_score??-1)-(a.trust_score??-1));
      if(provider==='cg'&&order==='volume')venues.sort((a,b)=>(b.trade_volume_24h_btc??-1)-(a.trade_volume_24h_btc??-1));
      if(!venues.length){
        out.replaceChildren(el('p','No exchange records returned on this page.','hub-note'));
      }else{
        const wrap=el('div',null,'hub-table-scroll');
        const table=el('table',null,'hub-table');
        const head=el('thead'),tr=el('tr');
        ['Exchange','Provider ID','Provider rank','Trust score','24h BTC volume','Tracked'].forEach(t=>tr.append(el('th',t)));
        head.append(tr);table.append(head);
        const body=el('tbody');
        venues.forEach(v=>{
          const tr=el('tr');
          [v.name,v.id,v.rank??'—',
            typeof v.trust_score==='number'?v.trust_score+'/10':'—',
            fmt(v.trade_volume_24h_btc),
            v.tracked===true?'Yes':v.tracked===false?'No':'Unknown'].forEach(value=>tr.append(el('td',value)));
          body.append(tr);
        });
        table.append(body);wrap.append(table);
        out.replaceChildren(wrap);
      }
      const meta=el('p','Source: '+(data.source||'Provider')+
        (data.fetched_at?' · Observed '+new Date(data.fetched_at*1000).toLocaleString():'')+
        (data.note?' · '+data.note:''),'hub-meta');
      out.append(meta);
      more=Boolean(data.has_more);
      $('exchange-page-status').textContent='Source page '+page+' · '+venues.length+' exchange identities';
    }catch(e){
      more=false;
      out.replaceChildren(el('p','Exchange feed unavailable: '+e.message,'hub-error'),
        el('p','Try the CoinMarketCap identity directory if CoinGecko metrics require an authorized API key.','hub-note'));
      $('exchange-page-status').textContent='Source not available';
    }
    $('exchange-previous').disabled=page<=1;
    $('exchange-next').disabled=!more;
  }
  for(const id of ['exchange-provider','exchange-limit']){
    $(id).addEventListener('change',()=>{page=1;load();});
  }
  $('exchange-order').addEventListener('change',load);
  $('exchange-refresh').addEventListener('click',load);
  $('exchange-previous').addEventListener('click',()=>{page=Math.max(1,page-1);load();});
  $('exchange-next').addEventListener('click',()=>{if(more){page++;load();}});
  load();
})();
