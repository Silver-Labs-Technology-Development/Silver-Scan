/* Every unconnected feature has an honest screen rather than a dead button.
   Reuses current source-controlled feature descriptions; no invented data. */
(async()=>{
  const $=id=>document.getElementById(id);
  const name=new URLSearchParams(location.search).get('feature')||'';
  const kind={
    markets:[
      ['Market data','Commercially permitted provider coverage and rate-limited API ingestion'],
      ['Identity','Provider IDs aligned to verified network or contract identifiers'],
      ['Freshness','Cached timestamps, stale fallback and missing-data disclosures']
    ],
    mining:[
      ['Chain adapter','Algorithm-specific verified node RPC and independently measured network statistics'],
      ['Pool integration','Read-only Silver Pool API after active Stratum and payout gates pass'],
      ['ROI','Explicit user assumptions, chain fees, electricity and cost disclosures']
    ],
    chains:[
      ['Indexer','Network-specific canonical block/transaction/contract data with reorganization handling'],
      ['Security','Validation of addresses, chain IDs, contract source and provider limits'],
      ['Coverage','Network-by-network adapter maturity, sync state and source timestamps']
    ],
    defi:[
      ['Network','Verified RPC / provider feed and network-aware contract identifiers'],
      ['Data quality','Source-backed liquidity, history and reserves with no invented prices'],
      ['Integration','Independent smart-contract and custody review before interactive swapping']
    ],
    projects:[
      ['Project identity','Approved metadata, verified links and separate chain/contract IDs'],
      ['Analytics','Privacy-preserving measured page events and provider-sourced market metrics'],
      ['Integrity','Clearly labeled sponsorship and independent listing/integration reviews']
    ]
  };
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n};
  try{
    const response=await fetch('./features.html',{cache:'no-store'});
    if(!response.ok)throw Error('Feature map unavailable');
    const doc=new DOMParser().parseFromString(await response.text(),'text/html');
    const cards=[...doc.querySelectorAll('[data-feature-card]')];
    const selected=cards.find(card=>card.querySelector('h3')?.textContent===name);
    if(!selected)throw Error('Feature not found. Browse the complete feature directory.');
    const group=selected.closest('.feature-group');
    const id=group?.id||group?.getAttribute('aria-labelledby')||'markets';
    const title=selected.querySelector('h3')?.textContent||name;
    const description=selected.querySelector('p')?.textContent||'Integration pending';
    const state=selected.getAttribute('data-status')||'planned';
    document.title=title+' — SilverScan Feature Lab';
    $('feature-title').textContent=title;
    $('feature-description').textContent=description;
    $('feature-status').textContent=state==='planned'?'Integration pending':state==='partial'?'Partially implemented':'Development preview';
    const requirements=kind[id]||kind.markets;
    $('feature-requirements').replaceChildren(...requirements.map(([heading,text])=>{
      const card=el('article');
      card.append(el('h3',heading),el('p',text));
      return card;
    }));
    const preview=$('feature-preview');
    if(state==='planned'){
      preview.append(el('p','No verified live source is connected for this feature. The layout remains illustrative until its adapter passes independent tests.','hub-note'));
    }else{
      preview.append(el('p','A limited prototype exists elsewhere in SilverScan. Review the feature directory for the actual working page and its available data sources.','hub-note'));
    }
  }catch(error){
    $('feature-title').textContent='Feature not found';
    $('feature-status').textContent='No valid feature selected';
    $('feature-description').textContent=error.message;
    $('feature-requirements').replaceChildren(el('p','Choose a feature from the All Features directory.','hub-note'));
  }
})();
