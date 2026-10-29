/* SilverScan PUBLIC VIEWING ALPHA — Cloudflare Pages advanced-mode Function.
   No Python services, wallet keys, user accounts, payments, mining payouts,
   public RPC proxy, or arbitrary third-party URLs are reachable here.

   CoinGecko commercial/redistribution rights MUST be approved and a suitable
   COINGECKO_API_KEY configured as a Cloudflare secret before market feeds work.
   All data remains provider-attributed. No exposed upstream API credentials.

   See docs/CLOUDFLARE-ALPHA.md for release/operations rules.
*/
const CG = "https://api.coingecko.com/api/v3";
const FNG = "https://api.alternative.me/fng/";
const LORE = "https://api.coinlore.net/api";
const ALLOWED_PAGES = new Set([25,50,100,200]);
const ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
const JSON_HEADERS = {
  "Content-Type":"application/json; charset=utf-8",
  "Cache-Control":"public, max-age=30",
  "X-Content-Type-Options":"nosniff",
  "Referrer-Policy":"no-referrer",
  "X-Robots-Tag":"noindex, nofollow"
};
const json = (data,status=200)=>new Response(JSON.stringify(data),{status,headers:JSON_HEADERS});
const fail=(message,status=503)=>json({error:message,alpha:true},status);
const num=n=>typeof n==="number"&&Number.isFinite(n)?n:null;
const positive=n=>num(n)!==null&&n>0;
const clampedInt=(value,fallback,min,max)=>{
  if(value===null)return fallback;
  if(!/^[0-9]{1,6}$/.test(value))throw Error("Invalid numeric parameter");
  const n=Number(value);
  if(n<min||n>max)throw Error("Numeric parameter outside allowed range");
  return n;
};
const safeImage=value=>
  typeof value==="string" && /^https:\/\/(coin-images\.coingecko\.com|assets\.coingecko\.com)\//.test(value)
  ?value:null;
const safeAsset=row=>({
  id:"coingecko:"+row.id,
  provider_id:row.id,
  name:typeof row.name==="string"?row.name.slice(0,140):row.id,
  symbol:typeof row.symbol==="string"?row.symbol.slice(0,30):"",
  rank:Number.isInteger(row.market_cap_rank)?row.market_cap_rank:null,
  price_usd:num(row.current_price),
  market_cap_usd:num(row.market_cap),
  volume_24h_usd:num(row.total_volume),
  circulating_supply:num(row.circulating_supply),
  change_1h_pct:num(row.price_change_percentage_1h_in_currency),
  change_24h_pct:num(row.price_change_percentage_24h_in_currency??row.price_change_percentage_24h),
  change_7d_pct:num(row.price_change_percentage_7d_in_currency),
  icon:safeImage(row.image),
  sparkline_7d:Array.isArray(row.sparkline_in_7d?.price)?
    row.sparkline_in_7d.price.filter(x=>num(x)!==null).filter((_,i)=>i%5===0).slice(0,34):[],
  market_status:"provider-reported-volume",
  network_identity:"provider-aggregated (not chain-verified)"
});

async function upstream(url, headers={}, maxLength=1800000){
  const parsed=new URL(url);
  if(![CG,"https://api.alternative.me",LORE].some(base=>parsed.origin===new URL(base).origin))
    throw Error("Unknown upstream host");
  const response=await fetch(url,{
    headers:{"Accept":"application/json",...headers},
    redirect:"error",
    signal:AbortSignal.timeout(8000),
    cf:{cacheTtl:120,cacheEverything:true}
  });
  if(!response.ok)throw Error("External source unavailable ("+response.status+")");
  const size=Number(response.headers.get("content-length")||0);
  if(size>maxLength)throw Error("Source response too large");
  const body=await response.text();
  if(body.length>maxLength)throw Error("Source response too large");
  return JSON.parse(body);
}


/* CoinLore documents a keyless public API for dashboards and business tools.
   Uses its own stable numeric IDs and 100-coin request batches. Never pretend
   a CoinLore ID is a CoinGecko token or that missing prices are zero. */
const loreNumber=value=>{
  if(value===null||value===undefined||value==='')return null;
  const number=Number(value);
  return Number.isFinite(number)?number:null;
};
const loreAsset=item=>{
  if(!item||!/^[0-9]{1,18}$/.test(String(item.id||'')))return null;
  const name=typeof item.name==='string'?item.name.slice(0,130):'';
  const id=String(item.id);
  return {
    id:'coinlore:'+id,provider_id:id,
    name:name||'CoinLore asset '+id,
    symbol:typeof item.symbol==='string'?item.symbol.slice(0,25):'',
    rank:loreNumber(item.rank),
    price_usd:loreNumber(item.price_usd),
    market_cap_usd:loreNumber(item.market_cap_usd),
    volume_24h_usd:loreNumber(item.volume24),
    circulating_supply:loreNumber(String(item.csupply||'').replace(/,/g,'')),
    change_1h_pct:loreNumber(item.percent_change_1h),
    change_24h_pct:loreNumber(item.percent_change_24h),
    change_7d_pct:loreNumber(item.percent_change_7d),
    sparkline_7d:[],icon:null,
    market_status:'provider-reported-volume',network_identity:'provider-aggregated (not chain-verified)'
  };
};
async function loreMarkets(url,forceFirst=false){
  const page=forceFirst?1:clampedInt(url.searchParams.get('page'),1,1,500);
  const limit=forceFirst?clampedInt(url.searchParams.get('limit'),50,1,100):
    clampedInt(url.searchParams.get('limit'),50,25,200);
  if(!forceFirst&&!ALLOWED_PAGES.has(limit))throw Error('Select 25, 50, 100 or 200 coins per page');
  const rows=[];let count=null,sourceTime=null;
  const start=(page-1)*limit;
  for(let i=0;i<limit;i+=100){
    const batch=Math.min(100,limit-i);
    const info=await upstream(LORE+'/tickers/?start='+(start+i)+'&limit='+batch,{},950000);
    if(!info||!Array.isArray(info.data))throw Error('CoinLore returned an invalid market page');
    if(Number.isInteger(info.info?.coins_num))count=info.info.coins_num;
    if(Number.isInteger(info.info?.time))sourceTime=info.info.time;
    rows.push(...info.data);
    if(info.data.length<batch)break;
  }
  const assets=rows.map(loreAsset).filter(c=>c&&positive(c.price_usd)&&positive(c.volume_24h_usd));
  return {
    source:'CoinLore',source_url:'https://www.coinlore.com/cryptocurrency-data-api',
    assets,page,limit,provider_rows:rows.length,has_more:count===null?rows.length===limit:start+rows.length<count,
    provider_market_count:count,currency:'USD',fetched_at:sourceTime||Math.floor(Date.now()/1000),
    stale:false,note:'Live CoinLore market observations. Coins with missing/zero prices or volume are excluded. Not an independently validated universal token index.'
  };
}
async function loreSearch(url){
  const query=(url.searchParams.get('q')||'').trim().toLowerCase();
  if(query.length<2||query.length>70||/[<>]/.test(query))throw Error('Search term must be 2–70 characters');
  const limit=clampedInt(url.searchParams.get('limit'),30,1,50);
  // CoinLore's dedicated lightweight catalogue includes unpriced/unranked
  // assets; results never imply a live market without a separate quote.
  const raw=await upstream(LORE+'/assets/',{},6000000);
  const list=Array.isArray(raw?.data)?raw.data:Array.isArray(raw)?raw:[];
  if(!list.length)throw Error('CoinLore asset catalog unavailable');
  const matches=list.filter(item=>item&&/^[0-9]{1,18}$/.test(String(item.id||''))&&(
    String(item.name||'').toLowerCase().includes(query)||
    String(item.symbol||'').toLowerCase()===query||
    String(item.nameid||'').toLowerCase().includes(query)
  )).slice(0,limit).map(item=>({
    id:'coinlore:'+item.id,provider_id:String(item.id),
    name:String(item.name||'').slice(0,120),symbol:String(item.symbol||'').slice(0,30),
    rank:loreNumber(item.rank),price_usd:null,volume_24h_usd:null,
    market_status:'catalog-discovery-only'
  }));
  return {source:'CoinLore asset catalog',matches,catalog_count:list.length,
    fetched_at:Math.floor(Date.now()/1000),stale:false,
    note:'Catalog IDs do not guarantee active trading; quoted prices must be requested separately.'};
}
async function loreQuotes(url){
  const ids=(url.searchParams.get('ids')||'').split(',');
  if(!ids.length||ids.length>50||ids.some(x=>!/^[0-9]{1,18}$/.test(x)))throw Error('Supply 1–50 distinct CoinLore IDs');
  const unique=[...new Set(ids)];
  const rows=[];
  for(let index=0;index<unique.length;index+=15){
    const data=await upstream(LORE+'/ticker/?id='+unique.slice(index,index+15).join(','),{},950000);
    if(!Array.isArray(data))throw Error('CoinLore quote response invalid');
    rows.push(...data);
  }
  return {source:'CoinLore /ticker',assets:rows.map(loreAsset).filter(Boolean),
    fetched_at:Math.floor(Date.now()/1000),stale:false,
    note:'Current provider quotes. Missing prices do not erase saved watchlist IDs.'};
}
async function loreGlobal(){
  const raw=await upstream(LORE+'/global/',{},250000);
  const item=Array.isArray(raw)?raw[0]:null;
  if(!item)throw Error('CoinLore global market data unavailable');
  return {
    source:'CoinLore',fetched_at:Math.floor(Date.now()/1000),stale:false,
    market_cap_usd:loreNumber(item.total_mcap),volume_24h_usd:loreNumber(item.total_volume),
    btc_dominance_pct:loreNumber(item.btc_d),eth_dominance_pct:loreNumber(item.eth_d),
    active_cryptocurrencies:loreNumber(item.coins_count),
    market_cap_change_24h_pct:loreNumber(item.mcap_change),
    note:'Global reported totals from CoinLore; asset count is the provider count and not SilverScan independently indexed coins.'
  };
}
async function loreQuote(url){
  const id=url.searchParams.get('id')||'';
  if(!/^[0-9]{1,18}$/.test(id))throw Error('Invalid CoinLore asset ID');
  const raw=await upstream(LORE+'/ticker/?id='+id,{},150000);
  const asset=Array.isArray(raw)?loreAsset(raw[0]):null;
  return {source:'CoinLore',asset,fetched_at:Math.floor(Date.now()/1000),stale:false};
}

const cgEnabled=env=>Boolean(env.COINGECKO_API_KEY&&env.CG_COMMERCIAL_USE_APPROVED==="yes");
function cgHeaders(env){
  return env.COINGECKO_KEY_TIER==="pro"
   ?{"x-cg-pro-api-key":env.COINGECKO_API_KEY}
   :{"x-cg-demo-api-key":env.COINGECKO_API_KEY};
}
async function coingecko(path,params,env){
  if(!cgEnabled(env))throw Error("CoinGecko feed disabled: commercial provider authorization/key required");
  const root=env.COINGECKO_KEY_TIER==="pro"?"https://pro-api.coingecko.com/api/v3":CG;
  const url=new URL(root+path);
  for(const [key,value] of Object.entries(params||{}))url.searchParams.set(key,String(value));
  // Never proxy a client-supplied provider URL.
  const response=await fetch(url.toString(),{
    headers:{Accept:"application/json",...cgHeaders(env)},
    redirect:"error",
    signal:AbortSignal.timeout(8000),
    cf:{cacheTtl:120,cacheEverything:true}
  });
  if(!response.ok)throw Error("CoinGecko data unavailable ("+response.status+")");
  const txt=await response.text();
  if(txt.length>2000000)throw Error("CoinGecko response too large");
  return JSON.parse(txt);
}
async function markets(url,env,forceFirst=false){
  const page=forceFirst?1:clampedInt(url.searchParams.get("page"),1,1,500);
  const limit=forceFirst?clampedInt(url.searchParams.get("limit"),50,1,100)
    :clampedInt(url.searchParams.get("limit"),50,25,200);
  if(!forceFirst&&!ALLOWED_PAGES.has(limit))throw Error("Select 25, 50, 100 or 200 coins per page");
  const raw=await coingecko("/coins/markets",{
    vs_currency:"usd",order:"market_cap_desc",page,
    per_page:limit,sparkline:limit<=100?"true":"false",
    price_change_percentage:"1h,24h,7d"
  },env);
  if(!Array.isArray(raw))throw Error("CoinGecko returned an invalid market page");
  const assets=raw.filter(row=>row&&ID.test(row.id||"")&&positive(row.current_price)&&positive(row.total_volume)).map(safeAsset);
  return {
    source:"CoinGecko",source_url:"https://www.coingecko.com/",
    assets,page,limit,provider_rows:raw.length,has_more:raw.length===limit,
    fetched_at:Math.floor(Date.now()/1000),stale:false,currency:"USD",
    note:"External market-cap ranked observations only. Positive price and reported volume are required; page gaps are possible."
  };
}
async function quotes(url,env,one=false){
  let ids=[];
  if(one){
    const id=url.searchParams.get("id")||"";
    if(!ID.test(id))throw Error("Invalid provider coin ID");
    ids=[id];
  }else{
    ids=(url.searchParams.get("ids")||"").split(",");
    if(!ids.length||ids.length>50||ids.some(id=>!ID.test(id)))throw Error("Supply 1–50 CoinGecko IDs");
  }
  const raw=await coingecko("/coins/markets",{
    vs_currency:"usd",ids:[...new Set(ids)].join(","),
    per_page:Math.min(250,Math.max(1,ids.length)),
    page:1,sparkline:"false",price_change_percentage:"1h,24h,7d"
  },env);
  if(!Array.isArray(raw))throw Error("Source returned invalid coin quotes");
  const assets=raw.filter(item=>item&&ID.test(item.id||"")).map(safeAsset);
  const base={source:"CoinGecko",assets,fetched_at:Math.floor(Date.now()/1000),stale:false,
    note:"Provider observations; identifiers are not proof of wallet ownership or a verified market."};
  return one?{...base,asset:assets[0]||null}:base;
}
async function globalMarket(env){
  const raw=await coingecko("/global",{},env);
  const d=raw?.data;
  if(!d||typeof d!=="object")throw Error("Source global totals unavailable");
  return {source:"CoinGecko",fetched_at:Math.floor(Date.now()/1000),stale:false,
    market_cap_usd:num(d.total_market_cap?.usd),
    volume_24h_usd:num(d.total_volume?.usd),
    btc_dominance_pct:num(d.market_cap_percentage?.btc),
    eth_dominance_pct:num(d.market_cap_percentage?.eth),
    active_cryptocurrencies:Number.isInteger(d.active_cryptocurrencies)?d.active_cryptocurrencies:null,
    market_cap_change_24h_pct:num(d.market_cap_change_percentage_24h_usd),
    note:"Global totals from CoinGecko; not independently indexed SilverScan assets."};
}
async function sentiment(url){
  const days=clampedInt(url.searchParams.get("days"),30,7,90);
  if(![7,30,90].includes(days))throw Error("Select 7, 30 or 90 days");
  const raw=await upstream(FNG+"?limit="+days);
  if(!Array.isArray(raw?.data)||!raw.data.length)throw Error("Sentiment feed unavailable");
  const h=raw.data.map(item=>({
    value:Number(item.value),timestamp:Number(item.timestamp),
    classification:typeof item.value_classification==="string"?item.value_classification:"Unknown"
  })).filter(x=>Number.isFinite(x.value)&&x.value>=0&&x.value<=100&&Number.isFinite(x.timestamp));
  if(!h.length)throw Error("Sentiment feed contains no observations");
  return {source:"Alternative.me Fear & Greed Index",
    source_url:"https://alternative.me/crypto/fear-and-greed-index/",
    fetched_at:Math.floor(Date.now()/1000),stale:false,
    score:h[0].value,classification:h[0].classification,
    history:h,note:"General crypto market sentiment, not an investment signal or BTCS-specific sentiment."};
}
function sources(env){
  const cg=cgEnabled(env);
  const at=Math.floor(Date.now()/1000);
  const list=[
    {name:"CoinLore",feature:"Live ranked coins and global totals; no API key",access:"requestable",status:"requestable",last_observed:null,docs_url:"https://www.coinlore.com/cryptocurrency-data-api"},
    {name:"CoinGecko",feature:"Market-cap prices, rankings and global stats",access:cg?"requestable":"licensed_key_required",status:cg?"requestable":"api_key_required",last_observed:null,docs_url:"https://www.coingecko.com/en/api"},
    {name:"CoinMarketCap",feature:"Additional research and exchange coverage",access:"integration_pending",status:"integration_pending",last_observed:null,docs_url:"https://coinmarketcap.com/api/"},
    {name:"Coinbase",feature:"Exchange spot pairs (not global coin counts)",access:"integration_pending",status:"integration_pending",last_observed:null,docs_url:"https://www.coinbase.com/"},
    {name:"LiveCoinWatch",feature:"Market rankings, optional approved provider plan",access:"integration_pending",status:"integration_pending",last_observed:null,docs_url:"https://www.livecoinwatch.com/tools/api"},
    {name:"MiningPoolStats",feature:"Pool information, authorized import not connected",access:"permissioned_import_required",status:"permissioned_import_required",last_observed:null,docs_url:"https://miningpoolstats.stream/bitcoinsilver"},
  ];
  return {sources:list,provider_count:list.length,
    verified_unique_coin_count:null,asset_identity_merge_active:false,fetched_at:at,
    note:"CoinLore is a keyless on-demand live source. Other providers require separate authorization. Source counts overlap and are not a verified 22k asset index."};
}
function poolCoins(){
  const data=[
    ["btcs","Bitcoin Silver","SHA-256d","Locally tested Silver Pool backend"],
    ["btc","Bitcoin","SHA-256d","Disabled staging profile"],
    ["bch","Bitcoin Cash","SHA-256d","Disabled staging profile"],
    ["ltc","Litecoin","Scrypt","Disabled staging profile"],
    ["doge","Dogecoin","Scrypt / AuxPoW","Disabled staging profile"]
  ];
  return {source:"Public Silver Pool staging configuration snapshot",active_public_pool_coins:0,
    ready_for_real_payouts:false,
    coins:data.map(([id,name,algorithm,status])=>({
      id,name,algorithm,status,public_mining_enabled:false,payouts_enabled:false,
      network_hashrate_hps:null,pool_hashrate_hps:null,network_difficulty:null,
      block_reward:null,pool_fee_percent:null,
      miningpoolstats_url:id==="btcs"?"https://miningpoolstats.stream/bitcoinsilver":null
    })),
    note:"Public alpha staging information, NOT live mining or payout availability."};
}
export default {
  async fetch(request,env){
    const url=new URL(request.url);
    if(!url.pathname.startsWith("/api/"))return env.ASSETS.fetch(request);
    if(request.method!=="GET")return fail("Public alpha is read-only. Login, portfolio sync, mining, trading and financial writes are disabled.",405);
    if(url.pathname.startsWith("/api/account/"))return fail("Account registration and synced portfolios are not available in public alpha.",403);
    try{
      const path=url.pathname;
      if(path==="/api/alpha/health")return json({status:"alpha",backend:"Cloudflare Workers",live_services:["static site","CoinLore market API","alternative.me sentiment"],locked_services:["account storage","public RPC","trading","payouts"],timestamp:Date.now()});
      if(path==="/api/sources/status")return json(sources(env));
      if(path==="/api/mining/coins")return json(poolCoins());
      if(path==="/api/market/global")return json(cgEnabled(env)?await globalMarket(env):await loreGlobal());
      if(path==="/api/coinlore/markets")return json(await loreMarkets(url));
      if(path==="/api/coinlore/quote")return json(await loreQuote(url));
      if(path==="/api/coinlore/search")return json(await loreSearch(url));
      if(path==="/api/coinlore/quotes")return json(await loreQuotes(url));
      if(path==="/api/markets")return json(cgEnabled(env)?await markets(url,env,true):await loreMarkets(url,true));
      if(path==="/api/catalog/page")return json(cgEnabled(env)?await markets(url,env):await loreMarkets(url));
      if(path==="/api/coin-watch/quotes")return json(await quotes(url,env));
      if(path==="/api/asset/quote")return json(await quotes(url,env,true));
      if(path==="/api/market/sentiment")return json(await sentiment(url));
      if(path==="/api/assets/chart"){
        const id=url.searchParams.get("id")||"",days=clampedInt(url.searchParams.get("days"),7,1,365);
        if(!ID.test(id)||![1,7,30,90,365].includes(days))throw Error("Invalid chart request");
        const data=await coingecko("/coins/"+id+"/market_chart",{vs_currency:"usd",days},env);
        if(!Array.isArray(data?.prices))throw Error("Chart unavailable");
        const points=data.prices.filter((x,i)=>i%Math.max(1,Math.ceil(data.prices.length/250))===0)
          .slice(0,250).filter(x=>Array.isArray(x)&&x.length===2&&num(x[0])!==null&&num(x[1])!==null);
        return json({source:"CoinGecko",provider_id:id,days,currency:"USD",points,fetched_at:Math.floor(Date.now()/1000),stale:false});
      }
      if(path==="/api/catalog/search"){
        const q=(url.searchParams.get("q")||"").trim();
        if(q.length<2||q.length>70||/[<>]/.test(q))throw Error("Search term must have 2–70 characters");
        const limit=clampedInt(url.searchParams.get("limit"),20,1,40);
        const data=await coingecko("/search",{query:q},env);
        const matches=Array.isArray(data?.coins)?data.coins.filter(x=>ID.test(x.id||""))
          .slice(0,limit).map(x=>({id:"coingecko:"+x.id,provider_id:x.id,name:x.name,symbol:x.symbol,
            market_status:"unverified",rank:Number.isInteger(x.market_cap_rank)?x.market_cap_rank:null})):[];
        return json({source:"CoinGecko /search",matches,catalog_count:null,
          fetched_at:Math.floor(Date.now()/1000),stale:false,
          note:"Provider search suggestions, not the complete ID catalog or verification of trading."});
      }
      if(path==="/api/pools/market")return json({source:"Not connected",provider_data_loaded:false,provider_permission_asserted:false,pools:[],networks:[],total_matching:0,offset:0,limit:50,warning:"No authorized MiningPoolStats import configured in public alpha."});
      if(path==="/api/universal/networks")return json({source:"Alpha network registry",networks:[
        {id:"btcs",name:"Bitcoin Silver L1",family:"UTXO",currency:"BTCS",configured:false,data_level:"Local-only until secured node backend is hosted"},
        {id:"ethereum",name:"Ethereum",family:"EVM",currency:"ETH",configured:false,data_level:"RPC integration pending"},
        {id:"bsc",name:"BNB Smart Chain",family:"EVM",currency:"BNB",configured:false,data_level:"RPC integration pending"},
        {id:"solana",name:"Solana",family:"Solana",currency:"SOL",configured:false,data_level:"RPC integration pending"}]});
      // Restrict all other services by default. Never expose direct RPC, SQL or
      // user-account endpoints through the public viewing platform.
      return fail("This alpha module needs an approved hosted read-only data adapter. No fabricated values are shown.",503);
    }catch(error){
      if(error.message?.startsWith("Invalid")||error.message?.startsWith("Select")||
         error.message?.startsWith("Search")||error.message?.startsWith("Supply")||
         error.message?.startsWith("Numeric"))return fail(error.message,400);
      return fail("Provider temporarily unavailable or not yet authorized for public use.",503);
    }
  }
};