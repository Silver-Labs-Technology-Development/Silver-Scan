import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
const {default:worker}=await import('../app/static/_worker.js');

function req(path,method='GET'){
  return new Request('https://scan.example.test'+path,{method});
}
const env={
  ASSETS:{fetch:async request=>new Response('STATIC '+new URL(request.url).pathname,{status:200})}
};
async function parsed(response){return response.json();}

test('Cloudflare Workers alpha serves static assets and a public health endpoint',async()=>{
  const response=await worker.fetch(req('/index.html'),env);
  assert.equal(response.status,200);
  assert.match(await response.text(),/STATIC/);
  const health=await parsed(await worker.fetch(req('/api/alpha/health'),env));
  assert.equal(health.status,'alpha');
  assert.ok(health.locked_services.includes('account storage'));
});

test('public accounts, arbitrary RPC and write operations fail closed',async()=>{
  const write=await worker.fetch(req('/api/account/register','POST'),env);
  assert.equal(write.status,405);
  assert.equal((await parsed(write)).alpha,true);
  assert.equal((await worker.fetch(req('/api/account/session'),env)).status,403);
  assert.equal((await worker.fetch(req('/api/universal/search?network=ethereum&q=0x0'),env)).status,503);
  assert.equal((await worker.fetch(req('/api/nonexistent-private-service'),env)).status,503);
});

test('source panel distinguishes six provider options from verified asset count',async()=>{
  const response=await parsed(await worker.fetch(req('/api/sources/status'),env));
  assert.equal(response.sources.length,6);
  assert.equal(response.verified_unique_coin_count,null);
  assert.equal(response.asset_identity_merge_active,false);
  assert.equal(response.sources[0].name,'CoinLore');
  assert.equal(response.sources[0].status,'requestable');
  assert.equal(response.sources[1].status,'api_key_required');
  assert.ok(!JSON.stringify(response).includes('MY_PRIVATE_KEY'));
});

test('public live market uses keyless CoinLore without an invented demo result',async()=>{
  const original=globalThis.fetch;
  let calls=0;
  globalThis.fetch=async(request)=>{
    calls++;
    assert.match(String(request),/api\.coinlore\.net\/api\/tickers\/\?/);
    const url=new URL(String(request));
    const start=Number(url.searchParams.get('start'));
    const limit=Number(url.searchParams.get('limit'));
    const rows=Array.from({length:limit},(_,i)=>({
      id:String(start+i+10),name:'External asset '+(start+i+10),symbol:'A'+(start+i+10),
      rank:start+i+1,price_usd:'12.50',volume24:2000,market_cap_usd:'100000',
      csupply:'5000',percent_change_24h:'2.7'
    }));
    return new Response(JSON.stringify({data:rows,info:{coins_num:12345,time:1782800000}}));
  };
  try{
    const result=await parsed(await worker.fetch(req('/api/coinlore/markets?page=2&limit=200'),env));
    assert.equal(calls,2);
    assert.equal(result.source,'CoinLore');
    assert.equal(result.assets.length,200);
    assert.equal(result.assets[0].id,'coinlore:210');
    assert.equal(result.assets[0].price_usd,12.5);
    assert.equal(result.has_more,true);
    assert.equal(result.provider_market_count,12345);
    assert.ok(result.note.includes('Not an independently validated'));
  }finally{globalThis.fetch=original}
});

test('global market view gets real reported totals without a provider key',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async request=>{
    assert.match(String(request),/api\.coinlore\.net\/api\/global/);
    return new Response(JSON.stringify([{coins_count:14993,total_mcap:2653000000000,
      total_volume:99182003568,btc_d:'60.31',eth_d:'10.70',mcap_change:'-0.97'}]));
  };
  try{
    const data=await parsed(await worker.fetch(req('/api/market/global'),env));
    assert.equal(data.source,'CoinLore');
    assert.equal(data.active_cryptocurrencies,14993);
    assert.equal(data.btc_dominance_pct,60.31);
  }finally{globalThis.fetch=original}
});

test('licensed CoinGecko market displays sanitized provider-backed rows',async()=>{
  const original=globalThis.fetch;
  let called=false;
  globalThis.fetch=async(request,options)=>{
    called=true;
    assert.match(String(request),/api.coingecko.com\/api\/v3\/coins\/markets/);
    assert.equal(options.headers['x-cg-demo-api-key'],'MY_PRIVATE_KEY');
    return new Response(JSON.stringify([
      {id:'bitcoin-silver-2',name:'Bitcoin Silver',symbol:'BTCS',
       current_price:0.02,total_volume:900,market_cap_rank:5000,
       market_cap:250000,price_change_percentage_24h:2.4,
       image:'https://coin-images.coingecko.com/coins/images/example.png'},
      {id:'no-volume',current_price:1,total_volume:0},
      {id:'../invalid',current_price:12,total_volume:20}
    ]),{status:200,headers:{'Content-Type':'application/json'}});
  };
  try{
    const r=await worker.fetch(req('/api/catalog/page?page=7&limit=25'),
      {...env,COINGECKO_API_KEY:'MY_PRIVATE_KEY',CG_COMMERCIAL_USE_APPROVED:'yes'});
    assert.equal(r.status,200);
    const data=await parsed(r);
    assert.equal(called,true);
    assert.equal(data.assets.length,1);
    assert.equal(data.assets[0].id,'coingecko:bitcoin-silver-2');
    assert.equal(data.assets[0].rank,5000);
    assert.ok(!JSON.stringify(data).includes('MY_PRIVATE_KEY'));
    assert.equal(data.has_more,false);
  }finally{globalThis.fetch=original}
});

test('unlicensed key alone is insufficient; malformed input is rejected',async()=>{
  const r=await worker.fetch(req('/api/asset/quote?id=bitcoin'),
    {...env,COINGECKO_API_KEY:'MY_PRIVATE_KEY'});
  assert.equal(r.status,503);
  const bad=await worker.fetch(req('/api/catalog/page?page=1&limit=251'),env);
  assert.equal(bad.status,400);
  const unknown=await worker.fetch(req('/api/asset/quote?id=../secret'),env);
  assert.equal(unknown.status,400);
});

test('sentiment works from a public source with clearly attributed observations',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async()=>new Response(JSON.stringify({data:[
    {value:'40',value_classification:'Fear',timestamp:'1783000000'},
    {value:'55',value_classification:'Neutral',timestamp:'1782910000'}
  ]}),{status:200,headers:{'Content-Type':'application/json'}});
  try{
    const r=await worker.fetch(req('/api/market/sentiment?days=30'),env);
    assert.equal(r.status,200);
    const data=await parsed(r);
    assert.equal(data.score,40);
    assert.equal(data.source,'Alternative.me Fear & Greed Index');
    assert.equal(data.history.length,2);
  }finally{globalThis.fetch=original}
});


test('existing Cloudflare Worker deploy config uses bound static assets and safe API routing',()=>{
  const toml=readFileSync('wrangler.worker.toml','utf8');
  const ignore=readFileSync('app/static/.assetsignore','utf8');
  const headers=readFileSync('app/static/_headers','utf8');
  assert.match(toml,/name\s*=\s*"silver-scan"/);
  assert.match(toml,/main\s*=\s*"\.\/app\/static\/_worker\.js"/);
  assert.match(toml,/directory\s*=\s*"\.\/app\/static"/);
  assert.match(toml,/binding\s*=\s*"ASSETS"/);
  assert.match(toml,/run_worker_first\s*=\s*\["\/api\/\*"\]/);
  assert.match(ignore,/^_worker\.js$/m);
  assert.match(headers,/X-Content-Type-Options:\s*nosniff/);
  assert.match(headers,/Content-Security-Policy:/);
  assert.match(toml,/compatibility_date/);
});

test('public worker does not allow local account registration or the universal RPC proxy',async()=>{
  for(const path of ['/api/account/login','/api/account/portfolio','/api/universal/search?network=bsc&q=123']){
    const response=await worker.fetch(req(path),env);
    assert.ok([403,503].includes(response.status));
    const content=await parsed(response);
    assert.equal(content.alpha,true);
  }
});
