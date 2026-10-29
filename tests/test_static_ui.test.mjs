import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const page = readFileSync('app/static/markets.html', 'utf8')
const landing = readFileSync('app/static/index.html', 'utf8')
const css = readFileSync('app/static/styles.css', 'utf8')
const explorer = readFileSync('app/static/explorer.js', 'utf8')
const research = readFileSync('app/static/research.js', 'utf8')

test('SilverScan shares a consistent navigation shell across all visible pages',()=>{
  const shell=readFileSync('app/static/site-shell.js','utf8');
  const shellCSS=readFileSync('app/static/site-shell.css','utf8');
  const files=['index.html','markets.html','exchanges.html','coin-watch.html','news.html','mining.html','insights.html','compare.html','universal-explorer.html','features.html','feature-detail.html'];
  for(const name of files){
    const content=readFileSync('app/static/'+name,'utf8');
    assert.match(content,/src="\.\/site-shell\.js"/);
    assert.match(content,/href="\.\/site-shell\.css"/);
    assert.match(content,/<header class="site-header" role="banner"><\/header>/);
  }
  for(const route of ['coin-watch.html','universal-explorer.html','mining.html','news.html','insights.html','compare.html','features.html']){
    assert.ok(shell.includes(route));
  }
  assert.match(shell,/id="theme-toggle"/);
  assert.match(shell,/id="ss-mobile-toggle"/);
  assert.match(shell,/ss-nav-dropdown/);
  assert.match(shell,/aria-expanded/);
  assert.match(shellCSS,/@media\(max-width:970px\)/);
  assert.match(page,/Silver Labs/i);
  assert.match(page,/not SilvEx trades/i);
  for(const id of ['explorer-search','view','research-view','net'])assert.ok(page.includes('id="'+id+'"'));
});

test('research modules are external; untrusted block fields never become HTML templates', () => {
  assert.doesNotMatch(page, /<script>\s*[\s\S]*?<\/script>/)
  assert.match(page, /src="\.\/explorer\.js"/)
  assert.match(page, /src="\.\/research\.js"/)
  assert.match(research, /import \{sparkline,timeSeries,dominanceRing,sentimentGauge\}/)
  assert.match(explorer, /textContent/)
  assert.doesNotMatch(explorer, /innerHTML\s*=/)
  assert.doesNotMatch(explorer, /insertAdjacentHTML/)
  assert.doesNotMatch(research, /innerHTML\s*=/)
})

test('responsive and accessible visual foundation', () => {
  assert.match(page, /<html lang="en">/)
  assert.match(page, /name="viewport"/)
  assert.match(page, /class="skip-link"/)
  assert.match(readFileSync('app/static/site-shell.js','utf8'), /aria-label="SilverScan primary navigation"/)
  assert.match(page, /aria-live="polite"/)
  assert.match(css, /@media\(max-width:700px\)/)
  assert.match(css, /@media\(prefers-reduced-motion:reduce\)/)
  assert.match(css, /:focus-visible/)
  assert.match(css, /#research-view\[hidden\]/)
})

test('query controls use encoded parameters and no authorization or signing flow', () => {
  assert.match(explorer, /encodeURIComponent/)
  assert.match(research, /encodeURIComponent/)
  assert.match(research, /Fear & Greed/)
  assert.match(research, /Market Dominance/)
  assert.match(research, /historical/i)
  assert.match(research, /Market Cap Heatmap/)
  assert.match(research, /renderHeatmap/)
  assert.doesNotMatch(explorer, /mining\.submit|sendrawtransaction|signTransaction/)
})



test('Coin Watch combines catalog discovery with saved coins, separate news and mining pages',()=>{
  const watch=readFileSync('app/static/coin-watch.html','utf8');
  const news=readFileSync('app/static/news.html','utf8');
  const mining=readFileSync('app/static/mining.html','utf8');
  const script=readFileSync('app/static/data-hub.js','utf8');
  for(const html of [watch,news,mining]){
    assert.match(html,/src="\.\/data-hub\.js"/);
    assert.match(html,/href="\.\/theme\.css"/);
    assert.match(html,/src="\.\/site-shell\.js"/);
    assert.match(readFileSync("app/static/site-shell.js","utf8"),/SILVER<span>SCAN/);
    assert.match(readFileSync("app/static/site-shell.js","utf8"),/href="\.\/news\.html"/);
    assert.match(readFileSync("app/static/site-shell.js","utf8"),/href="\.\/mining\.html"/);
    assert.match(readFileSync("app/static/site-shell.js","utf8"),/href="\.\/coin-watch\.html"/);
  }
  assert.match(watch,/id="watch-results"/);
  assert.match(watch,/id="asset-search"/);
  assert.match(watch,/bitcoin-silver-2/);
  assert.match(watch,/CoinMarketCap active listings/);
  assert.match(watch,/Coinbase available spot pairs/);
  assert.match(news,/Latest Crypto News/);
  assert.doesNotMatch(news,/id="asset-search"/);
  assert.match(mining,/id="mining-network-results"/);
  assert.match(mining,/id="mining-form"/);
  assert.doesNotMatch(mining,/id="asset-search"/);
  assert.match(script,/localStorage\.setItem\(WATCH_KEY/);
  assert.match(script,/\/api\/coin-watch\/quotes/);
  assert.match(script,/\/api\/mining\/coins/);
  assert.match(script,/\/api\/news/);
  assert.match(script,/\/api\/mining\/estimate/);
  assert.doesNotMatch(script,/innerHTML\s*=/);
});

test('main market pages offer provider pagination with 25–200 coins per page',()=>{
  assert.match(research,/marketPageSize:50/);
  assert.match(research,/\[25,50,100,200\]/);
  assert.match(research,/\/api\/catalog\/page/);
  assert.match(research,/marketProviders\[state\.marketProvider\]/);
  assert.match(research,/marketHasMore/);
  assert.match(research,/Previous/);
  assert.match(research,/Next/);
  assert.doesNotMatch(research,/Provider-ranked top 100 snapshot/);
  assert.match(research,/location.href='\.\/coin-watch\.html\?search='/);
});

test('shared CSS exposes distinct readable dark and light panels',()=>{
  const theme=readFileSync('app/static/theme.css','utf8');
  const themeJS=readFileSync('app/static/theme.js','utf8');
  assert.match(theme,/html\[data-theme=dark\]/);
  assert.match(theme,/html\[data-theme=light\]/);
  assert.match(theme,/--panel:#1b344b/);
  assert.match(theme,/--panel:#ffffff/);
  assert.match(theme,/--text:#f1f7ff/);
  assert.match(theme,/--text:#153149/);
  assert.match(themeJS,/localStorage\.getItem\(KEY\)/);
  assert.match(theme,/opacity:1/);
});


test('manual account portfolio has real forms and user-owned positions without wallet verification',()=>{
  const watch=readFileSync('app/static/coin-watch.html','utf8');
  const client=readFileSync('app/static/portfolio.js','utf8');
  assert.match(watch,/id="register-form"/);
  assert.match(watch,/id="login-form"/);
  assert.match(watch,/id="holding-form"/);
  assert.match(watch,/id="portfolio-rows"/);
  assert.match(watch,/id="holding-quantity"/);
  assert.match(watch,/src="\.\/portfolio\.js"/);
  assert.match(watch,/No wallet connection, signatures, deposits or ownership checks/);
  assert.match(client,/\/api\/account\/'\+route/);
  assert.match(client,/sign\(event,'register'\)/);
  assert.match(client,/\/api\/account\/portfolio/);
  assert.match(client,/\/api\/coin-watch\/quotes/);
  assert.match(client,/credentials:'same-origin'/);
  assert.doesNotMatch(client,/localStorage\.setItem/);
  assert.doesNotMatch(client,/innerHTML\s*=/);
});

test('news articles support attributed image media, favicons and lazy-loaded fallbacks',()=>{
  const script=readFileSync('app/static/data-hub.js','utf8');
  const css=readFileSync('app/static/data-hub.css','utf8');
  assert.match(script,/thumbnail_url/);
  assert.match(script,/favicon_url/);
  assert.match(script,/loading='lazy'/);
  assert.match(script,/hub-story-image-fallback/);
  assert.match(css,/hub-story-artwork\.image-ready/);
  assert.match(css,/hub-favicon-wrap\.icon-ready/);
});

test('market insights and comparison have real pages and provider endpoints',()=>{
  const insights=readFileSync('app/static/insights.html','utf8');
  const compare=readFileSync('app/static/compare.html','utf8');
  const a=readFileSync('app/static/insights.js','utf8');
  const b=readFileSync('app/static/compare.js','utf8');
  for(const id of ['insights-trending','insights-categories','insights-exchanges','insights-defi']){
    assert.ok(insights.includes('id="'+id+'"'));
  }
  assert.match(compare,/id="compare-ids"/);
  assert.match(a,/\/api\/insights\/trending/);
  assert.match(a,/\/api\/insights\/categories/);
  assert.match(a,/\/api\/insights\/exchanges/);
  assert.match(a,/\/api\/insights\/defi/);
  assert.match(b,/\/api\/coin-watch\/quotes/);
  assert.doesNotMatch(a,/innerHTML\s*=/);
  assert.doesNotMatch(b,/innerHTML\s*=/);
});

test('every planned feature leads to a meaningful integration outline',()=>{
  const html=readFileSync('app/static/features.html','utf8');
  const detailed=readFileSync('app/static/feature-detail.html','utf8');
  const script=readFileSync('app/static/feature-detail.js','utf8');
  assert.match(html,/href="\.\/feature-detail\.html\?feature=/);
  assert.doesNotMatch(html,/<span class="feature-action feature-action-muted">No live data module yet<\/span>/);
  assert.match(html,/href="\.\/coin-watch\.html#portfolio"/);
  assert.match(detailed,/feature-skeleton/);
  assert.match(script,/DOMParser/);
  assert.match(script,/textContent/);
  assert.doesNotMatch(script,/innerHTML\s*=/);
});


test('keyless CoinLore default and compact source-status panel replace blank alpha markets',()=>{
  const shell=readFileSync('app/static/site-shell.js','utf8');
  const theme=readFileSync('app/static/site-shell.css','utf8');
  const watch=readFileSync('app/static/coin-watch.html','utf8');
  assert.match(research,/marketProvider:'lore'/);
  assert.match(research,/\/api\/coinlore\/markets/);
  assert.match(research,/function openLoreAsset/);
  assert.match(page,/id="ss-source-details"/);
  assert.match(page,/id="sources-status"/);
  assert.doesNotMatch(page,/class="provider-board"/);
  assert.match(theme,/\.ss-sources-popover/);
  assert.match(watch,/value="lore" selected/);
  assert.match(readFileSync('app/static/data-hub.js','utf8'),/\/api\/coinlore\/search/);
  assert.match(readFileSync('app/static/data-hub.js','utf8'),/\/api\/coinlore\/quotes/);
  assert.match(shell,/More Research/);
});


test('Cloudflare-hosted exchange directory has shared navigation and separated sources',()=>{
  const html=readFileSync('app/static/exchanges.html','utf8');
  const js=readFileSync('app/static/exchanges.js','utf8');
  const nav=readFileSync('app/static/site-shell.js','utf8');
  assert.match(nav,/href="\.\/exchanges\.html"/);
  assert.match(html,/id="exchange-results"/);
  assert.match(html,/id="exchange-provider"/);
  assert.match(html,/id="exchange-next"/);
  assert.match(html,/src="\.\/exchanges\.js"/);
  assert.match(js,/\/api\/exchanges\/cmc/);
  assert.match(js,/\/api\/exchanges\/coingecko/);
  assert.doesNotMatch(js,/innerHTML\s*=/);
});


test('new SilverScan cloud landing page links to the preserved full markets terminal and all major hubs',()=>{
  const script=readFileSync('app/static/landing.js','utf8');
  const style=readFileSync('app/static/landing.css','utf8');
  const nav=readFileSync('app/static/site-shell.js','utf8');
  assert.match(landing,/src="\.\/site-shell\.js"/);
  assert.match(landing,/id="landing-market-rows"/);
  assert.match(landing,/id="landing-cap"/);
  assert.match(landing,/href="\.\/markets\.html"/);
  assert.match(landing,/href="\.\/exchanges\.html"/);
  assert.match(landing,/href="\.\/mining\.html#pool-market"/);
  assert.match(landing,/href="\.\/universal-explorer\.html"/);
  assert.match(script,/\/api\/market\/global/);
  assert.match(script,/\/api\/coinlore\/markets/);
  assert.doesNotMatch(script,/innerHTML\s*=/);
  assert.match(style,/@media\(max-width:570px\)/);
  assert.match(page,/id="research-view"/);
  assert.match(page,/src="\.\/research\.js"/);
  assert.match(nav,/href="\.\/markets\.html#markets"/);
  assert.match(nav,/data-ss-section="home"/);
});
