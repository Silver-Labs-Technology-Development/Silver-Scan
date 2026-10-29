/* SilverScan mining-pool market. A listing is not a recommendation.
   MiningPoolStats data requires reviewed permission and source provenance.
   No fabricated pool counts or missing financial input defaults. */
(() => {
  const $=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==null&&text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const compact=n=>typeof n==='number'&&Number.isFinite(n)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n):'—';
  const pct=n=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(2)+'%':'—';
  let offset=0,networks=new Map(),pageSize=50,matched=0,rows=[];
  async function get(url){
    const response=await fetch(url,{headers:{Accept:'application/json'}});
    const body=await response.json().catch(()=>({error:'Unreadable upstream response'}));
    if(!response.ok)throw Error(body.error||'Data unavailable');
    return body;
  }
  const note=text=>$('pool-market-results').replaceChildren(el('p',text,'hub-note'));
  function td(row,value){row.append(el('td',value));}
  async function rank(){
    const coin=$('pool-coin').value,sort=$('pool-sort').value;
    pageSize=Number($('pool-per-page').value);
    $('pool-market-prev').disabled=true;$('pool-market-next').disabled=true;
    note('Checking permissioned pool observations…');
    try{
      const data=await get('/api/pools/market?coin='+encodeURIComponent(coin)+
        '&sort='+encodeURIComponent(sort)+'&limit='+pageSize+'&offset='+offset);
      matched=data.total_matching||0;
      rows=data.pools||[];
      networks=new Map((data.networks||[]).map(n=>[n.coin,n]));
      const options=$('pool-coin');
      if(options.options.length===1&&data.networks?.length){
        for(const network of data.networks){
          const option=el('option',network.coin.toUpperCase()+(network.algorithm?' · '+network.algorithm:''));
          option.value=network.coin;options.add(option);
        }
      }
      $('pool-market-count').textContent=data.provider_data_loaded?
        (matched.toLocaleString()+' reported pools; not independently audited'):
        'No authorized live pool dataset connected';
      if(!data.provider_data_loaded){
        const info=el('div',null,'pool-unavailable');
        info.append(el('h3','MiningPoolStats data connection pending'),
          el('p',data.warning||'A permissioned data feed is required.'),
          el('p','SilverScan will not present copied third-party pool rankings or fabricated hashrates. For now you can compare available Silver Pool development statuses, inspect external source directories and use the manual estimator.','hub-note'));
        const a=el('a','See MiningPoolStats BTCS pools →');a.href='https://miningpoolstats.stream/bitcoinsilver';a.target='_blank';a.rel='noopener noreferrer';info.append(a);
        $('pool-market-results').replaceChildren(info);
      }else{
        const wrap=el('div',null,'hub-table-scroll');
        const table=el('table',null,'hub-table pool-directory-table');
        const head=el('thead'),tr=el('tr');
        ['Pool','Coin','Fee','Observed hashrate','Network share','Payout','Min payout','Miners','Reported status','Freshness','Preference score','Research'].forEach(h=>tr.append(el('th',h)));
        head.append(tr);table.append(head);
        const body=el('tbody');
        for(const pool of rows){
          const row=el('tr');
          td(row,pool.name);td(row,pool.coin.toUpperCase());td(row,pct(pool.fee_percent));
          td(row,compact(pool.pool_hashrate_hps)+' H/s');td(row,pct(pool.network_share_pct));
          td(row,pool.payout_method||'—');td(row,compact(pool.minimum_payout));
          td(row,compact(pool.miners));td(row,pool.status||'Unknown');
          td(row,pool.observed_at?new Date(pool.observed_at*1000).toLocaleString():'Unreported');
          td(row,pool.preference_score===null?'Not scored':pool.preference_score.toFixed(1)+' / 100');
          const cell=el('td');
          const estimate=el('button','Estimate','hub-estimate-link');
          estimate.type='button';estimate.addEventListener('click',()=>prepareEstimate(pool));
          cell.append(estimate);
          if(pool.source_url){
            const a=el('a','Source');a.href=pool.source_url;a.rel='noopener noreferrer';a.target='_blank';cell.append(a);
          }
          row.append(cell);body.append(row);
        }
        table.append(body);wrap.append(table);
        const meta=el('p','Source: '+data.source+' · Dataset '+(data.fetched_at?new Date(data.fetched_at*1000).toLocaleString():'time unavailable')+
          (data.warning?' · '+data.warning:''),'hub-meta');
        $('pool-market-results').replaceChildren(
          rows.length?wrap:el('p','No pool observations match these filters.','hub-note'),meta);
      }
      $('pool-market-prev').disabled=offset===0;
      $('pool-market-next').disabled=offset+pageSize>=matched;
      $('pool-market-page').textContent=matched?
        ((offset+1)+'–'+(offset+rows.length)+' of '+matched+' observed pools'):
        'No verified imported pool rows';
    }catch(error){
      note('Unable to load mining-pool directory: '+error.message);
      $('pool-market-count').textContent='Data unavailable';
    }
  }
  async function prepareEstimate(pool){
    const coin=networks.get(pool.coin);
    if(!coin){$('estimate-target').textContent='No verified network record available for this pool.';return;}
    const field=(id,value)=>{
      const input=$(id);if(input&&value!==null&&value!==undefined&&Number.isFinite(value))input.value=String(value);
    };
    field('network-hash',coin.network_hashrate_hps);
    field('reward',coin.block_reward);
    field('blocks',coin.blocks_per_day);
    field('fee',pool.fee_percent);
    $('estimate-target').textContent='Selected '+pool.name+' ('+pool.coin.toUpperCase()+
      '): independently supply your hardware H/s, power and electricity rate. Pool fee/network fields use the approved source snapshot when present.';
    if(coin.coingecko_id){
      try{
        const result=await get('/api/coin-watch/quotes?ids='+encodeURIComponent(coin.coingecko_id));
        const quote=(result.assets||[]).find(item=>item.provider_id===coin.coingecko_id);
        if(quote&&typeof quote.price_usd==='number'&&quote.price_usd>0){
          field('price',quote.price_usd);
          $('estimate-target').textContent+=' CoinGecko price observed '+new Date((result.fetched_at||0)*1000).toLocaleString()+'.';
        }else $('estimate-target').textContent+=' No current market quote; enter price manually.';
      }catch{
        $('estimate-target').textContent+=' Coin market price unavailable; enter an observed price manually.';
      }
    }
    document.getElementById('mining')?.scrollIntoView({behavior:'smooth',block:'start'});
    $('miner-hash')?.focus();
  }
  $('pool-market-refresh')?.addEventListener('click',()=>{offset=0;rank();});
  $('pool-coin')?.addEventListener('change',()=>{offset=0;rank();});
  $('pool-sort')?.addEventListener('change',()=>{offset=0;rank();});
  $('pool-per-page')?.addEventListener('change',()=>{offset=0;rank();});
  $('pool-market-prev')?.addEventListener('click',()=>{offset=Math.max(0,offset-pageSize);rank();});
  $('pool-market-next')?.addEventListener('click',()=>{offset+=pageSize;rank();});
  rank();
})();
