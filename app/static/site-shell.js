/* One SilverScan header across all pages, without external dependencies. */
(() => {
  const header=document.querySelector('header.site-header');
  if(!header)return;
  const file=location.pathname.split('/').pop()||'index.html';
  const isHome=file==='index.html';
  const view={
    'coin-watch.html':'watch','news.html':'news','mining.html':'mining',
    'universal-explorer.html':'explorer'
  };
  header.innerHTML=[
    '<div class="shell header-main ss-header-main">',
      '<a class="brand ss-brand" href="./" aria-label="SilverScan home">',
        '<span class="brand-mark" aria-hidden="true"><span>S</span></span>',
        '<span class="brand-type"><strong>SILVER<span>SCAN</span></strong><small>MARKETS · MINING · BLOCKCHAINS</small></span>',
      '</a>',
      '<form class="global-search ss-search" id="global-search-form" role="search">',
        '<label class="sr-only" for="global-search">Find coins and tokens</label>',
        '<span class="search-icon" aria-hidden="true">⌕</span>',
        '<input id="global-search" name="q" type="search" maxlength="100" autocomplete="off" placeholder="Search coins, tokens, assets...">',
        '<kbd aria-hidden="true">/</kbd><button type="submit">Search</button>',
      '</form>',
      '<div class="header-actions ss-header-actions">',
        '<span class="currency-pill" title="Market prices are in USD">USD</span>',
        '<button type="button" class="theme-toggle" id="theme-toggle" aria-label="Switch color theme" title="Switch light / dark">◐</button>',
        '<button type="button" class="ss-mobile-toggle" id="ss-mobile-toggle" aria-label="Open navigation" aria-controls="ss-navigation" aria-expanded="false">☰ <span>Menu</span></button>',
      '</div>',
    '</div>',
    '<div class="nav-wrap ss-nav-wrap" id="ss-navigation">',
      '<nav class="shell research-nav ss-nav" aria-label="SilverScan primary navigation">',
        '<a class="ss-nav-item" data-ss-section="markets" href="./#markets">Markets</a>',
        '<a class="ss-nav-item" data-ss-section="watch" href="./coin-watch.html">Coin Watch</a>',
        '<a class="ss-nav-item" data-ss-section="explorer" href="./universal-explorer.html">Explorer</a>',
        '<a class="ss-nav-item" data-ss-section="mining" href="./mining.html">Mining</a>',
        '<a class="ss-nav-item" data-ss-section="news" href="./news.html">Crypto News</a>',
        '<details class="ss-nav-dropdown" id="ss-research-dropdown">',
          '<summary class="ss-nav-item ss-nav-summary" aria-label="More research pages">More Research <span aria-hidden="true">⌄</span></summary>',
          '<div class="ss-dropdown-panel">',
            '<a href="./insights.html">Market Insights</a>',
            '<a href="./compare.html">Compare Coins</a>',
            '<a href="./#heatmap">Market Heatmap</a>',
            '<a href="./#dex">DEX Scan</a>',
            '<a href="./#explorer">Bitcoin Silver L1</a>',
            '<a href="./features.html">All Features</a>',
          '</div>',
        '</details>',
      '</nav>',
    '</div>'
  ].join('');
  const menu=header.querySelector('#ss-mobile-toggle');
  const nav=header.querySelector('#ss-navigation');
  const dropdown=header.querySelector('#ss-research-dropdown');
  const links=[...header.querySelectorAll('[data-ss-section]')];

  function currentSection(){
    if(isHome)return ['#heatmap','#dex','#explorer'].includes(location.hash)?'research':'markets';
    return view[file]||'research';
  }
  function markCurrent(){
    const current=currentSection();
    for(const anchor of links){
      const selected=anchor.dataset.ssSection===current;
      anchor.classList.toggle('ss-current',selected);
      if(selected)anchor.setAttribute('aria-current','page');
      else anchor.removeAttribute('aria-current');
    }
    dropdown.classList.toggle('ss-current',current==='research');
    const summary=dropdown.querySelector('summary');
    if(current==='research')summary.setAttribute('aria-current','page');
    else summary.removeAttribute('aria-current');
  }
  markCurrent();
  window.addEventListener('hashchange',markCurrent);
  function closeMenu(){
    nav.classList.remove('ss-open');
    menu.setAttribute('aria-expanded','false');
    menu.setAttribute('aria-label','Open navigation');
  }
  menu.addEventListener('click',()=>{
    const open=!nav.classList.contains('ss-open');
    nav.classList.toggle('ss-open',open);
    menu.setAttribute('aria-expanded',String(open));
    menu.setAttribute('aria-label',open?'Close navigation':'Open navigation');
    if(!open)dropdown.open=false;
  });
  dropdown.addEventListener('toggle',()=>{
    dropdown.querySelector('summary').setAttribute('aria-expanded',String(dropdown.open));
  });
  document.addEventListener('click',event=>{
    if(!dropdown.contains(event.target))dropdown.open=false;
    if(!header.contains(event.target))closeMenu();
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      const wasOpen=dropdown.open;
      dropdown.open=false;
      if(nav.classList.contains('ss-open')){closeMenu();menu.focus();}
      else if(wasOpen)dropdown.querySelector('summary').focus();
    }
  });
  header.querySelectorAll('.ss-nav a').forEach(a=>a.addEventListener('click',()=>{
    closeMenu();dropdown.open=false;
  }));
  // Home's search is owned by research.js; other pages get the same search path.
  if(!isHome)header.querySelector('#global-search-form').addEventListener('submit',event=>{
    event.preventDefault();
    const q=header.querySelector('#global-search').value.trim();
    if(q.length>=2)location.href='./coin-watch.html?search='+encodeURIComponent(q);
    else header.querySelector('#global-search').focus();
  });
})();
