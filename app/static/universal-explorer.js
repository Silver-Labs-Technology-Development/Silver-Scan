/* SilverScan Universal Explorer — one interface, separate verified RPC schemas.
   Never displays invented transfers, token holders, or wallet ownership.
   All text is inserted with textContent; no unsafe HTML or script execution. */
(() => {
  const $=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{
    const n=document.createElement(tag);
    if(text!==null&&text!==undefined)n.textContent=String(text);
    if(cls)n.className=cls;
    return n;
  };
  const group=(cls,...children)=>{const n=el('div',null,cls);n.append(...children);return n;};
  let currentNetworks=[];
  const detailPairs={
    address:[
      ['Address / account','address'],
      ['Native balance','native_balance'],
      ['Account transaction nonce','transaction_nonce'],
      ['Contract deployed','is_contract'],
      ['Account owner program','program_owner'],
      ['Executable program','executable'],
      ['Account data size','space'],
      ['Parsed account type','parsed_account_type'],
      ['Token mint','token_mint'],
      ['Raw mint supply','token_supply_raw'],
      ['Mint supply','token_supply']
    ],
    contract:[
      ['Contract address','address'],['Native balance','native_balance'],
      ['Account transaction nonce','transaction_nonce'],
      ['Contract deployed','is_contract']
    ],
    account:[
      ['Solana account','address'],['SOL balance','native_balance'],
      ['Owner program','program_owner'],['Executable','executable'],
      ['Account data bytes','space'],['Parsed type','parsed_account_type'],
      ['Token mint','token_mint'],['SPL supply','token_supply'],
      ['Mint decimals','token_supply_decimals']
    ],
    transaction:[
      ['Transaction hash','hash'],['Solana signature','signature'],['From','from'],
      ['To','to'],['Block number','block_number'],['Block slot','slot'],
      ['Native token value','value_native'],['Gas limit','gas_limit'],
      ['Gas price (wei)','gas_price_wei'],['Gas used','gas_used'],
      ['EVM status (1 = success)','status'],['Emitted event logs','log_count'],
      ['SOL fee (lamports)','fee_lamports'],['Instruction count','instruction_count'],
      ['Token balance snapshots','token_balance_changes'],['Block timestamp','block_time']
    ],
    block:[
      ['Block height','height'],['Solana slot','slot'],
      ['Block hash','hash'],['Solana blockhash','blockhash'],
      ['Previous blockhash','previous_blockhash'],['Block time','timestamp'],
      ['Block time','block_time'],['Block height','block_height'],
      ['Transactions in block','transaction_count'],
      ['Gas used','gas_used'],['Gas limit','gas_limit'],['Miner / validator address','miner']
    ]
  };
  const pairs=(fields,data)=>{
    const list=el('dl',null,'universal-detail-list');
    for(const [label,key] of fields){
      const value=data[key];
      if(value===null||value===undefined)continue;
      if(typeof value!=='number'&&typeof value!=='string'&&typeof value!=='boolean')continue;
      const wrap=el('div',null,'universal-detail-pair');
      wrap.append(el('dt',label),el('dd',typeof value==='boolean'?(value?'Yes':'No'):value));
      list.append(wrap);
    }
    return list;
  };
  async function api(url){
    const reply=await fetch(url,{headers:{Accept:'application/json'}});
    const data=await reply.json().catch(()=>({error:'Unreadable node response'}));
    if(!reply.ok)throw Error(data.error||'Network query failed (HTTP '+reply.status+')');
    return data;
  }
  function display(data){
    const target=$('universal-results');
    if(data.found===false){
      target.replaceChildren(el('h3','No confirmed match'),
        el('p','The selected network did not return that transaction or block. This can also mean a node is not fully indexed, not yet finalized or has pruned the requested history.','hub-note'));
      return;
    }
    const heading=group('universal-result-head',
      el('div',null,''),
      el('span',(data.family||'Blockchain')+' · '+(data.network_name||data.network),'hub-chip'));
    heading.firstChild.append(el('span',(data.type||'Result').toUpperCase(),'eyebrow'),
      el('h3',(data.network_name||data.network)+' '+(data.type||'lookup')+' details'));
    const main=el('section',null,'universal-summary');
    const key=data.type==='contract'?'contract':data.type==='account'?'account':data.type;
    main.append(pairs(detailPairs[key]||detailPairs.address,data));
    if(data.type==='contract'){
      const meta=data.token_metadata||{};
      const block=el('div',null,'universal-subsection');
      block.append(el('h4','Fungible token contract metadata'));
      const token=pairs([['Name','name'],['Symbol','symbol'],['Decimals','decimals'],['Reported total supply','display_total_supply']],meta);
      block.append(token);
      if(!token.childElementCount)block.append(el('p','The contract did not return standard ERC-20 / BEP-20 metadata. It may be another kind of smart contract.','hub-note'));
      main.append(block);
    }
    if(Array.isArray(data.recent_signatures)&&data.recent_signatures.length){
      const block=el('div',null,'universal-subsection');
      block.append(el('h4','Recent Solana account signatures (limited RPC observations)'));
      const list=el('div',null,'universal-signatures');
      for(const record of data.recent_signatures){
        if(typeof record.signature!=='string')continue;
        const b=el('button',record.signature,'universal-signature');
        b.type='button';b.addEventListener('click',()=>{
          $('universal-q').value=record.signature;
          $('universal-kind').value='transaction';
          $('universal-form').requestSubmit();
        });
        list.append(b);
      }
      block.append(list);main.append(block);
    }
    if(data.message)main.append(el('p',data.message,'hub-note'));
    const footer=el('p','Source: '+(data.source||'RPC')+
      (data.observed_at?' · Observed '+new Date(data.observed_at*1000).toLocaleString():'')+
      ' · Read-only observations, not a complete chain index.','hub-meta');
    target.replaceChildren(heading,main,footer);
  }
  async function loadNetworks(){
    const slot=$('universal-networks');
    try{
      const data=await api('/api/universal/networks');
      currentNetworks=data.networks||[];
      const cards=currentNetworks.map(network=>{
        const card=el('button',null,'universal-chain-card');
        card.type='button';
        card.append(el('strong',network.name),
          el('small',network.family+' · '+network.currency),
          el('span',network.configured?'RPC adapter configured':'RPC provider required',
            network.configured?'universal-chain-ready':'universal-chain-unconfigured'));
        card.addEventListener('click',()=>{
          if(network.id==='btcs'){
            location.href='./#explorer';return;
          }
          $('universal-chain').value=network.id;
          $('universal-form').scrollIntoView({block:'start',behavior:'smooth'});
          $('universal-q').focus();
        });
        return card;
      });
      slot.replaceChildren(...cards);
    }catch(error){
      slot.replaceChildren(el('p','Chain registry unavailable: '+error.message,'hub-error'));
    }
  }
  async function search(event){
    event.preventDefault();
    const network=$('universal-chain').value;
    if(network==='btcs'){
      location.href='./#explorer';return;
    }
    const q=$('universal-q').value.trim();
    if(q.length>110||!q){
      $('universal-results').replaceChildren(el('p','Enter a public blockchain identifier.','hub-error'));return;
    }
    const kind=$('universal-kind').value;
    const form=$('universal-form'),button=form.querySelector('button[type=submit]');
    button.disabled=true;
    $('universal-results').replaceChildren(el('p','Querying '+network+' for observed on-chain data…','hub-note'));
    try{
      const data=await api('/api/universal/search?network='+encodeURIComponent(network)+
        '&q='+encodeURIComponent(q)+'&kind='+encodeURIComponent(kind));
      display(data);
    }catch(error){
      $('universal-results').replaceChildren(el('h3','Lookup unavailable'),
        el('p',error.message,'hub-error'),
        el('p','Check the selected chain, identifier format and RPC provider availability. Public shared endpoints are rate-limited, and some chains require an operator-provided RPC URL.','hub-note'));
    }finally{button.disabled=false;}
  }
  $('universal-form').addEventListener('submit',search);
  const url=new URLSearchParams(location.search),chain=url.get('network')||'';
  if(['ethereum','bsc','base','polygon','arbitrum','avalanche','solana','btcs'].includes(chain))
    $('universal-chain').value=chain;
  const query=url.get('q');
  if(query&&query.length<=110)$('universal-q').value=query;
  loadNetworks();
})();
