/* SilverScan manual portfolio — local-only account prototype.
   Quantities are user statements, never verified balances or wallet holdings.
   No API credentials, secrets, private keys, or passwords in localStorage. */
(() => {
  const $ = id => document.getElementById(id);
  const make = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (cls) node.className = cls;
    return node;
  };
  let csrf = null;
  let active = false;
  let holdings = [];
  let quotes = new Map();
  let quotedAt = null;
  const currency = amount => Number.isFinite(amount) ?
    new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:amount < 1 ? 6 : 2}).format(amount) : '—';
  function message(text, error=false) {
    const box = $('account-message');
    box.textContent = text || '';
    box.className = error ? 'hub-error' : 'hub-note';
  }
  async function api(url, options={}) {
    const response = await fetch(url,{
      credentials:'same-origin',
      headers:{'Accept':'application/json',...(options.body?{'Content-Type':'application/json'}:{}),
        ...((options.method==='POST'||options.method==='DELETE')&&csrf?{'X-CSRF-Token':csrf}:{})},
      ...options
    });
    const result = await response.json().catch(()=>({error:'Invalid account response'}));
    if(!response.ok)throw Error(result.error || 'Request failed ('+response.status+')');
    return result;
  }
  function showSession(signedIn,email=''){
    active=Boolean(signedIn);
    $('account-auth').hidden=active;
    $('account-portfolio').hidden=!active;
    $('account-email').textContent=email||'';
    if(!active){
      holdings=[];quotes=new Map();quotedAt=null;
      $('portfolio-rows').replaceChildren(make('p','Sign in to view your saved entries.','hub-note'));
    }
  }
  async function syncSession(){
    try{
      const result=await api('/api/account/session');
      csrf=result.csrf||null;
      showSession(result.authenticated,result.email);
      if(active){
        message('Signed in · Portfolio contains manually entered holdings.');
        await loadHoldings();
      }else message('Create a local preview account or sign in to save portfolio entries.');
    }catch(error){
      showSession(false);message('Local accounts unavailable: '+error.message,true);
    }
  }
  function coinId(raw) {
    const clean=String(raw||'').trim().toLowerCase().replace(/^coingecko:/,'');
    return /^[a-z0-9][a-z0-9-]{0,99}$/.test(clean) ? clean : null;
  }
  async function sign(event,route){
    event.preventDefault();
    const form=event.currentTarget,button=form.querySelector('button[type=submit]');
    const email=form.querySelector('[name=email]').value.trim();
    const password=form.querySelector('[name=password]').value;
    button.disabled=true;message('Checking your local account…');
    try{
      const result=await api('/api/account/'+route,{method:'POST',
        body:JSON.stringify({email,password})});
      csrf=result.csrf||null;
      form.reset();
      showSession(true,result.email);
      await loadHoldings();
      message('Account ready. Add a coin ID and the quantity you want to track.');
    }catch(error){message(error.message,true);}
    finally{button.disabled=false;}
  }
  function summary(){
    const target=$('portfolio-rows');
    const table=make('div',null,'portfolio-holdings');
    let total=0,available=0,missing=0;
    if(!holdings.length){
      target.replaceChildren(make('p','No coins added. Enter an asset ID and quantity above, or select “Add to portfolio” from the Coin Watch results.','hub-note'));
      $('portfolio-value').textContent='—';
      $('portfolio-coverage').textContent='No manually entered assets';
      return;
    }
    for(const entry of holdings){
      const row=make('div',null,'portfolio-holding');
      const quote=quotes.get(entry.asset_id);
      const quantity=Number(entry.quantity);
      const price=quote && Number(quote.price_usd);
      const observedValue=quote&&Number.isFinite(price)&&price>=0&&Number.isFinite(quantity)?price*quantity:null;
      if(Number.isFinite(observedValue)){total+=observedValue;available++;}
      else missing++;
      const title=make('div',null,'portfolio-coin-name');
      title.append(make('strong',quote?.name||entry.asset_id.slice('coingecko:'.length)),
        make('small',entry.asset_id));
      const amount=make('div',null,'portfolio-coin-quantity');
      amount.append(make('strong',entry.quantity),make('small','Manually entered quantity'));
      const value=make('div',null,'portfolio-coin-value');
      value.append(make('strong',Number.isFinite(observedValue)?currency(observedValue):'—'),
        make('small',quote&&Number.isFinite(price)?'Price '+currency(price):'Market quote unavailable'));
      const actions=make('div',null,'portfolio-coin-actions');
      const edit=make('button','Edit','hub-watch-star');
      edit.type='button';edit.addEventListener('click',()=>{
        $('holding-coin').value=entry.asset_id.slice('coingecko:'.length);
        $('holding-quantity').value=entry.quantity;
        $('holding-quantity').focus();
      });
      const remove=make('button','Remove','hub-watch-star');
      remove.type='button';remove.setAttribute('aria-label','Remove '+entry.asset_id);
      remove.addEventListener('click',async()=>{
        remove.disabled=true;
        try{
          await api('/api/account/portfolio/'+encodeURIComponent(entry.asset_id),{method:'DELETE'});
          message('Removed '+entry.asset_id+' from your manually tracked portfolio.');
          await loadHoldings();
        }catch(error){message(error.message,true);remove.disabled=false;}
      });
      actions.append(edit,remove);
      row.append(title,amount,value,actions);table.append(row);
    }
    const disclaimer=make('p','These quantities are self-reported. They are not checked against the blockchain, and market quotes can be stale or unavailable.','hub-meta');
    target.replaceChildren(table,disclaimer);
    $('portfolio-value').textContent=available?currency(total):'—';
    $('portfolio-coverage').textContent=available+' of '+holdings.length+' coins priced · '+missing+
      ' missing quote(s)'+(quotedAt?' · '+quotedAt:'');
  }
  async function updatePrices(){
    if(!active||!holdings.length){quotes=new Map();summary();return;}
    const ids=holdings.map(x=>x.asset_id.slice('coingecko:'.length));
    try{
      // Keep within the provider's validated 50-ID-per-request cap.
      const map=new Map();
      let timestamps=[];
      for(let i=0;i<ids.length;i+=50){
        const group=ids.slice(i,i+50);
        const result=await api('/api/coin-watch/quotes?ids='+encodeURIComponent(group.join(',')));
        for(const coin of result.assets||[])map.set(coin.id,coin);
        if(result.fetched_at)timestamps.push(result.fetched_at);
      }
      quotes=map;
      quotedAt=timestamps.length?new Date(Math.min(...timestamps)*1000).toLocaleString():'Source timestamp unavailable';
      summary();
    }catch(error){
      quotes=new Map();
      quotedAt='External market prices unavailable';
      summary();
      message('Holdings saved, but market quotes are unavailable: '+error.message,true);
    }
  }
  async function loadHoldings(){
    if(!active)return;
    try{
      const result=await api('/api/account/portfolio');
      holdings=Array.isArray(result.holdings)?result.holdings:[];
      summary();
      await updatePrices();
    }catch(error){message('Could not load saved holdings: '+error.message,true);}
  }
  async function save(event){
    event.preventDefault();
    if(!active){message('Sign in first to save your portfolio.',true);return;}
    const asset=coinId($('holding-coin').value);
    const quantity=$('holding-quantity').value.trim();
    if(!asset){message('Use the full CoinGecko coin ID, not just a ticker.',true);return;}
    const submit=event.currentTarget.querySelector('button[type=submit]');
    submit.disabled=true;
    try{
      await api('/api/account/portfolio',{method:'POST',body:JSON.stringify({
        asset_id:'coingecko:'+asset,quantity
      })});
      message('Saved '+asset+' with quantity '+quantity+'. No wallet verification required.');
      $('holding-quantity').value='';
      await loadHoldings();
    }catch(error){message(error.message,true);}
    finally{submit.disabled=false;}
  }
  async function logout(){
    try{
      await api('/api/account/logout',{method:'POST',body:'{}'});
      csrf=null;showSession(false);
      message('Signed out of your local account.');
    }catch(error){message(error.message,true);}
  }
  document.addEventListener('portfolio:select',event=>{
    const asset=coinId(event.detail?.id);
    if(!asset)return;
    if(!active){
      message('Create an account or sign in first, then add '+(event.detail?.name||asset)+'.',true);
      $('account-auth').scrollIntoView({behavior:'smooth',block:'center'});
      return;
    }
    $('holding-coin').value=asset;
    $('portfolio').scrollIntoView({behavior:'smooth',block:'start'});
    $('holding-quantity').focus();
    message('Selected '+(event.detail?.name||asset)+'. Enter how many coins you wish to track.');
  });
  $('register-form').addEventListener('submit',event=>sign(event,'register'));
  $('login-form').addEventListener('submit',event=>sign(event,'login'));
  $('holding-form').addEventListener('submit',save);
  $('account-logout').addEventListener('click',logout);
  $('portfolio-refresh').addEventListener('click',updatePrices);
  syncSession();
})();
