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

test('Cloudflare Pages alpha serves static assets and a public health endpoint',async()=>{
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

test('source panel distinguishes five connectors from verified asset count',async()=>{
  const response=await parsed(await worker.fetch(req('/api/sources/status'),env));
  assert.equal(response.sources.length,5);
  assert.equal(response.verified_unique_coin_count,null);
  assert.equal(response.asset_identity_merge_active,false);
  assert.equal(response.sources[0].status,'api_key_required');
  assert.ok(!JSON.stringify(response).includes('MY_PRIVATE_KEY'));
});

test('missing licensed market key does not fall back to unauthorized source',async()=>{
  const response=await worker.fetch(req('/api/catalog/page?page=1&limit=200'),env);
  assert.equal(response.status,503);
  const result=await parsed(response);
  assert.match(result.error,/Provider temporarily unavailable/);
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
  const r=await worker.fetch(req('/api/catalog/page?page=1&limit=25'),
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
