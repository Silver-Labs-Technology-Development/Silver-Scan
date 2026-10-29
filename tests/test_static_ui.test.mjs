import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const page = readFileSync('app/static/index.html', 'utf8')
const css = readFileSync('app/static/styles.css', 'utf8')
const explorer = readFileSync('app/static/explorer.js', 'utf8')
const research = readFileSync('app/static/research.js', 'utf8')

test('SilverScan has distinct in-depth market, watch, news and mining destinations', () => {
  for (const tab of ['explorer','markets','dex','heatmap']) {
    assert.match(page, new RegExp('data-tab="' + tab + '"'))
  }
  for (const id of ['explorer-search','view','research-view','net']) {
    assert.match(page, new RegExp('id="' + id + '"'))
  }
  assert.match(page, /Silver Labs/i)
  assert.match(page, /not SilvEx trades/i)
  assert.match(page, /href="\.\/features\.html"/)
  assert.match(page, /href="\.\/coin-watch\.html"/)
  assert.match(page, /href="\.\/news\.html"/)
  assert.match(page, /href="\.\/mining\.html"/)
})

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
  assert.match(page, /aria-label="SilverScan sections"/)
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
    assert.match(html,/id="theme-toggle"/);
    assert.match(html,/SILVER<span>SCAN/);
    assert.match(html,/href="\.\/news\.html"/);
    assert.match(html,/href="\.\/mining\.html"/);
    assert.match(html,/href="\.\/coin-watch\.html"/);
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
  assert.doesNotMatch(html,/No live data module yet/);
  assert.match(html,/href="\.\/coin-watch\.html#portfolio"/);
  assert.match(detailed,/feature-skeleton/);
  assert.match(script,/DOMParser/);
  assert.match(script,/textContent/);
  assert.doesNotMatch(script,/innerHTML\s*=/);
});
