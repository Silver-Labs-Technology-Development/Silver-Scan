/* Cloudflare Pages public-alpha API.
 * Server-side, read-only, allowlisted upstreams. NO local Python, private
 * portfolio, node RPC, credentials or wallet operations are exposed.
 * Cache source observations to protect API quotas; decline when unavailable.
 */
const CG = "https://api.coingecko.com/api/v3";
const ALT = "https://api.alternative.me/fng/";
const DEX = "https://api.dexscreener.com/latest/dex/search";
const COINBASE = "https://api.coinbase.com/api/v3/brokerage/market/products";
const LCW = "https://api.livecoinwatch.com/coins/list";
const CMC = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest";
const COIN_ID = /^[a-z0-9][a-z0-9-]{0,99}$/;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;
const NEWS = [
  ["CoinDesk","https://www.coindesk.com/arc/outboundfeeds/rss/","www.coindesk.com"],
  ["Cointelegraph","https://cointelegraph.com/rss","cointelegraph.com"],
  ["Decrypt","https://decrypt.co/feed","decrypt.co"]
];
const time = () => Math.floor(Date.now()/1000);
const number = x => {
  const n=Number(x);
  return x===null||x===undefined||x===""||!Number.isFinite(n)?null:n;
};
const integer=(sp,key,def,min,max)=>{
  const raw=sp.get(key);
  if(raw===null)return def;
  if(!/^\d{1,8}$/.test(raw))throw new RequestError("Invalid "+key,400);
  const val=Number(raw);
  if(val<min||val>max)throw new RequestError(key+" must be "+min+"–"+max,400);
  return val;
};
class RequestError extends Error{constructor(message,status=503){super(message);this.status=status;}}
function json(data,status=200,age=0){
  return new Response(JSON.stringify(data),{status,headers:{
    "content-type":"application/json; charset=utf-8",
    "cache-control":age>0?"public, max-age="+age+", s-maxage="+age:"no-store",
    "x-content-type-options":"nosniff",
    "access-control-allow-origin":"same-origin",
    "referrer-policy":"strict-origin-when-cross-origin"
  }});
}
function safeImage(value){
  try{
    const u=new URL(value);
    return u.protocol==="https:"&&["coin-images.coingecko.com","assets.coingecko.com"].includes(u.hostname)?u.href:null;
  }catch{return null;}
}
function safeLink(value,host){
  try{
    const u=new URL(value);
    return u.protocol==="https:"&&(u.hostname===host||u.hostname.endsWith("."+host))?u.href:null;
  }catch{return null;}
}
async function upstream(url,env,options={}){
  const u=new URL(url);
  if(!["api.coingecko.com","api.alternative.me","api.dexscreener.com","api.coinbase.com",
    "pro-api.coinmarketcap.com","api.livecoinwatch.com",
    "www.coindesk.com","cointelegraph.com","decrypt.co"].includes(u.hostname))
      throw new RequestError("Unapproved data source");
  const headers={"accept":options.xml?"application/rss+xml, application/xml":"application/json"};
  if(u.hostname==="api.coingecko.com"&&env.COINGECKO_DEMO_API_KEY)
    headers["x-cg-demo-api-key"]=env.COINGECKO_DEMO_API_KEY;
  if(u.hostname==="pro-api.coinmarketcap.com"&&env.CMC_API_KEY)
    headers["x-cmc_pro_api_key"]=env.CMC_API_KEY;
  if(u.hostname==="api.livecoinwatch.com"&&env.LIVECOINWATCH_API_KEY)
    headers["x-api-key"]=env.LIVECOINWATCH_API_KEY;
  const init={method:options.method||"GET",headers,redirect:"error",
    signal:AbortSignal.timeout(8000)};
  if(options.data){
    headers["content-type"]="application/json";
    init.body=JSON.stringify(options.data);
  }
  let response;
  try{response=await fetch(u.toString(),init);}
  catch{throw new RequestError("External provider temporarily unreachable");}
  if(!response.ok)throw new RequestError(
    "Upstream provider returned HTTP "+response.status+"; please retry later");
  const length=Number(response.headers.get("content-length")||0);
  if(length>1800000)throw new RequestError("Source payload too large");
  const text=await response.text();
  if(text.length>1800000)throw new RequestError("Source payload too large");
  if(options.xml)return text;
  try{return JSON.parse(text);}catch{throw new RequestError("Invalid provider response");}
}
const cgCoins=(raw,limit=250)=>raw.filter(x=>x&&typeof x.id==="string"&&COIN_ID.test(x.id)).slice(0,limit).map(c=>({
  id:"coingecko:"+c.id,provider_id:c.id,name:String(c.name||c.id).slice(0,150),
  symbol:String(c.symbol||"").slice(0,30),rank:number(c.market_cap_rank),
  price_usd:number(c.current_price),change_1h_pct:number(c.price_change_percentage_1h_in_currency),
  change_24h_pct:number(c.price_change_percentage_24h_in_currency??c.price_change_percentage_24h),
  change_7d_pct:number(c.price_change_percentage_7d_in_currency),
  market_cap_usd:number(c.market_cap),volume_24h_usd:number(c.total_volume),
  circulating_supply:number(c.circulating_supply),
  icon:safeImage(c.image),
  sparkline_7d:Array.isArray(c.sparkline_in_7d?.price)?
    c.sparkline_in_7d.price.filter(x=>Number.isFinite(x)).filter((x,i)=>i%5===0).slice(0,34):[],
  market_status:"provider-reported-volume"
}));
async function marketPage(sp,env,top=false){
  const page=top?1:integer(sp,"page",1,1,500);
  const limit=top?integer(sp,"limit",100,1,100):integer(sp,"limit",50,25,200);
  const query=new URLSearchParams({vs_currency:"usd",order:"market_cap_desc",
    per_page:String(limit),page:String(page),sparkline:limit<=100?"true":"false",
    price_change_percentage:"1h,24h,7d"});
  const raw=await upstream(CG+"/coins/markets?"+query,env);
  if(!Array.isArray(raw))throw new RequestError("Invalid market data");
  const filtered=cgCoins(raw).filter(c=>c.price_usd>0&&c.volume_24h_usd>0);
  return {source:"CoinGecko",source_url:"https://www.coingecko.com/",page,limit,
    provider_rows:raw.length,has_more:raw.length===limit,fetched_at:time(),stale:false,
    assets:filtered, note:"Provider-reported ranked markets. Coins without reported positive volume are filtered; a catalog ID does not verify active trading."};
}
async function cgQuote(ids,env){
  const p=new URLSearchParams({vs_currency:"usd",ids:ids.join(","),
    order:"market_cap_desc",per_page:"100",page:"1",sparkline:"false"});
  const raw=await upstream(CG+"/coins/markets?"+p,env);
  if(!Array.isArray(raw))throw new RequestError("Invalid quote data");
  return {source:"CoinGecko",assets:cgCoins(raw),fetched_at:time(),stale:false,
    note:"Source-observed prices, not verified wallet balances."};
}
function assetID(sp,name="id"){
  const id=sp.get(name)||"";
  if(!COIN_ID.test(id))throw new RequestError("Invalid CoinGecko ID",400);
  return id;
}
async function globalMarket(env){
  const raw=await upstream(CG+"/global",env),d=raw?.data;
  if(!d)throw new RequestError("Global data unavailable");
  return {source:"CoinGecko",fetched_at:time(),stale:false,
    market_cap_usd:number(d.total_market_cap?.usd),
    volume_24h_usd:number(d.total_volume?.usd),
    btc_dominance_pct:number(d.market_cap_percentage?.btc),
    eth_dominance_pct:number(d.market_cap_percentage?.eth),
    active_cryptocurrencies:Number.isInteger(d.active_cryptocurrencies)?d.active_cryptocurrencies:null,
    market_cap_change_24h_pct:number(d.market_cap_change_percentage_24h_usd),
    note:"CoinGecko global coverage, not a unique SilverScan indexed-asset count."};
}
async function sentiment(sp,env){
  const days=integer(sp,"days",30,7,90);
  if(![7,30,90].includes(days))throw new RequestError("Allowed days: 7, 30, 90",400);
  const raw=await upstream(ALT+"?limit="+days,env);
  const hist=(raw?.data||[]).map(x=>({
    value:Number(x.value),timestamp:Number(x.timestamp),
    classification:String(x.value_classification||"Unclassified")
  })).filter(x=>Number.isInteger(x.value)&&x.value>=0&&x.value<=100&&x.timestamp>0)
    .sort((a,b)=>a.timestamp-b.timestamp);
  if(!hist.length)throw new RequestError("Sentiment source returned no data");
  const last=hist[hist.length-1];
  return {source:"Alternative.me Crypto Fear & Greed Index",
    source_url:"https://alternative.me/crypto/fear-and-greed-index/",
    fetched_at:time(),stale:false,score:last.value,
    classification:last.classification,history:hist,observation_timestamp:last.timestamp};
}
async function profile(sp,env){
  const id=assetID(sp);
  const p=new URLSearchParams({localization:"false",tickers:"false",market_data:"true",
    community_data:"false",developer_data:"false",sparkline:"false"});
  const raw=await upstream(CG+"/coins/"+id+"?"+p,env);
  if(raw.id!==id)throw new RequestError("Mismatched provider identity");
  const m=raw.market_data||{},usd=obj=>number(obj?.usd);
  const contracts=Object.entries(raw.platforms||{}).slice(0,40)
    .filter(([chain,contract])=>typeof contract==="string"&&contract.length<150)
    .map(([network,contract])=>({network,contract}));
  const links=raw.links||{},resources=[];
  for(const [label,values] of [["Official website",links.homepage],["Blockchain explorer",links.blockchain_site],["Source code",links.repos_url?.github]]){
    const valid=Array.isArray(values)?values.find(x=>typeof x==="string"&&x.startsWith("https://")):null;
    if(valid)resources.push({label,url:valid});
  }
  return {source:"CoinGecko",fetched_at:time(),stale:false,id:"coingecko:"+id,
    provider_id:id,name:raw.name,symbol:raw.symbol,rank:number(raw.market_cap_rank),
    icon:safeImage(raw.image?.large),
    description:String(raw.description?.en||"").replace(/<[^>]*>/g," ").slice(0,1300),
    categories:Array.isArray(raw.categories)?raw.categories.slice(0,12):[],
    price_usd:usd(m.current_price),market_cap_usd:usd(m.market_cap),
    volume_24h_usd:usd(m.total_volume),ath_usd:usd(m.ath),atl_usd:usd(m.atl),
    high_24h_usd:usd(m.high_24h),low_24h_usd:usd(m.low_24h),
    fdv_usd:usd(m.fully_diluted_valuation),
    change_24h_pct:number(m.price_change_percentage_24h),
    change_7d_pct:number(m.price_change_percentage_7d),
    circulating_supply:number(m.circulating_supply),total_supply:number(m.total_supply),
    max_supply:number(m.max_supply),contracts,resources,
    note:"CoinGecko profile data does not verify tokens or imply Silver Labs exchange listing."};
}
async function chart(sp,env){
  const id=assetID(sp),days=integer(sp,"days",7,1,365);
  if(![1,7,30,90,365].includes(days))throw new RequestError("Invalid timeframe",400);
  const raw=await upstream(CG+"/coins/"+id+"/market_chart?vs_currency=usd&days="+days,env);
  if(!Array.isArray(raw.prices))throw new RequestError("No price history");
  const step=Math.max(1,Math.ceil(raw.prices.length/250));
  const points=raw.prices.filter((_,i)=>i%step===0).slice(0,250)
    .filter(p=>Array.isArray(p)&&Number.isFinite(p[0])&&Number.isFinite(p[1]));
  return {source:"CoinGecko",fetched_at:time(),stale:false,
    provider_id:id,days,currency:"USD",points};
}
function sourceStatus(env){
  const status=(name,feature,access)=>({name,feature,access,status:access,
    last_observed:null,docs_url:null});
  return {sources:[
    status("CoinGecko","Market prices, rankings, coin discovery, charts","requestable"),
    status("CoinMarketCap","Market rankings and exchange IDs",env.CMC_API_KEY?"requestable":"api_key_required"),
    status("Coinbase","Public Coinbase pairs only","requestable"),
    status("LiveCoinWatch","Ranked coin listings",env.LIVECOINWATCH_API_KEY?"requestable":"api_key_required"),
    status("MiningPoolStats","Permissioned pool data export","permissioned_import_required")
  ],provider_count:5,verified_unique_coin_count:null,asset_identity_merge_active:false,
    fetched_at:time(),note:"Provider status is configuration, not a real-time health check. Provider catalog IDs overlap; verified unique asset coverage is not calculated."};
}
async function catalogSearch(sp,env){
  const q=(sp.get("q")||"").trim(),limit=integer(sp,"limit",20,1,40);
  if(q.length<2||q.length>70||/[\x00-\x1f]/.test(q))
    throw new RequestError("Enter 2–70 printable characters",400);
  const raw=await upstream(CG+"/search?query="+encodeURIComponent(q),env);
  const matches=(Array.isArray(raw.coins)?raw.coins:[]).slice(0,limit)
    .filter(x=>typeof x.id==="string"&&COIN_ID.test(x.id))
    .map(c=>({id:"coingecko:"+c.id,provider_id:c.id,name:c.name,symbol:c.symbol,
      rank:c.market_cap_rank,market_status:"unverified"}));
  if(/^(btcs|bitcoin\s*silver)$/i.test(q)&&!matches.some(x=>x.provider_id==="bitcoin-silver-2"))
    matches.unshift({id:"coingecko:bitcoin-silver-2",provider_id:"bitcoin-silver-2",
      name:"Bitcoin Silver",symbol:"BTCS",rank:null,market_status:"unverified"});
  return {source:"CoinGecko /search",matches:matches.slice(0,limit),catalog_count:null,
    fetched_at:time(),stale:false,note:"Search returns provider matches, not a complete independently indexed catalog."};
}
async function insight(path,sp,env){
  let raw,key,output;
  if(path==="insights/trending"){
    raw=await upstream(CG+"/search/trending",env);
    output=(raw.coins||[]).slice(0,30).map(x=>x?.item).filter(x=>x&&COIN_ID.test(x.id))
      .map(x=>({id:"coingecko:"+x.id,provider_id:x.id,name:x.name,
        symbol:x.symbol,rank:x.market_cap_rank,market_status:"trending-search-unverified"}));
    return {source:"CoinGecko /search/trending",coins:output,fetched_at:time(),stale:false};
  }
  if(path==="insights/categories"){
    raw=await upstream(CG+"/coins/categories?order=market_cap_desc",env);
    if(!Array.isArray(raw))throw new RequestError("Invalid category data");
    return {source:"CoinGecko /coins/categories",fetched_at:time(),stale:false,
      categories:raw.slice(0,integer(sp,"limit",30,1,50)).map(c=>({
        id:c.id,name:c.name,market_cap_usd:number(c.market_cap),
        volume_24h_usd:number(c.volume_24h),
        change_24h_pct:number(c.market_cap_change_24h)}))};
  }
  if(path==="insights/exchanges"){
    const page=integer(sp,"page",1,1,20),limit=integer(sp,"limit",30,1,50);
    raw=await upstream(CG+"/exchanges?per_page="+limit+"&page="+page,env);
    if(!Array.isArray(raw))throw new RequestError("Invalid exchange data");
    return {source:"CoinGecko /exchanges",page,has_more:raw.length===limit,
      fetched_at:time(),stale:false,exchanges:raw.map(x=>({
        id:x.id,name:x.name,country:x.country,rank:number(x.trust_score_rank),
        trust_score:number(x.trust_score),
        trade_volume_24h_btc:number(x.trade_volume_24h_btc),
        website:typeof x.url==="string"&&x.url.startsWith("https://")?x.url:null
      }))};
  }
  if(path==="insights/defi"){
    raw=await upstream(CG+"/global/decentralized_finance_defi",env);
    const d=raw.data||{};
    return {source:"CoinGecko /global/decentralized_finance_defi",
      fetched_at:time(),stale:false,market_cap_usd:number(d.defi_market_cap),
      volume_24h_usd:number(d.trading_volume_24h),dominance_pct:number(d.defi_dominance),
      defi_to_eth_ratio_pct:number(d.defi_to_eth_ratio),top_coin_name:d.top_coin_name};
  }
  throw new RequestError("Unknown insight endpoint",404);
}
async function dexSearch(sp,env){
  const q=(sp.get("q")||"").trim();
  if(q.length<2||q.length>80||/[\x00-\x1f]/.test(q))
    throw new RequestError("Search must be 2–80 printable characters",400);
  const raw=await upstream(DEX+"?q="+encodeURIComponent(q),env);
  const pairs=(Array.isArray(raw.pairs)?raw.pairs:[]).slice(0,25).map(x=>({
    id:"dexscreener:"+x.chainId+":"+x.pairAddress,
    chain_id:x.chainId,dex_id:x.dexId,pair_address:x.pairAddress,
    base_token:x.baseToken,quote_token:x.quoteToken,price_usd:x.priceUsd,
    liquidity_usd:number(x.liquidity?.usd),
    volume_24h_usd:number(x.volume?.h24),change_24h_pct:number(x.priceChange?.h24),
    source_url:typeof x.url==="string"&&x.url.startsWith("https://dexscreener.com/")?x.url:null
  }));
  return {source:"DEX Screener",source_url:"https://dexscreener.com/",
    fetched_at:time(),stale:false,pairs,note:"External research only, not verified swaps or SilvEx listings."};
}
function decodeXML(s){return s.replace(/&lt;/g,"<").replace(/&gt;/g,">")
  .replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&amp;/g,"&");}
function field(text,tag){
  const r=new RegExp("<"+tag+"(?:\\s[^>]*)?>([\\s\\S]*?)<\\/"+tag+">","i").exec(text);
  return r?decodeXML(r[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g,"$1").replace(/<[^>]+>/g,"").trim()):"";
}
async function newsFeed(sp,env){
  const limit=integer(sp,"limit",20,1,40),stories=[];
  const feeds=await Promise.all(NEWS.map(async ([name,url,host])=>{
    try{
      const xml=await upstream(url,env,{xml:true});
      const entries=[...xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)].slice(0,25);
      return entries.map(match=>{
        const item=match[1],headline=field(item,"title"),href=field(item,"link");
        const link=safeLink(href,host);
        const date=Date.parse(field(item,"pubDate"));
        const thumb=/\b(?:media:thumbnail|media:content|enclosure)\b[^>]*\burl="(https:\/\/[^"]+)"/i.exec(item)?.[1]||null;
        const u=thumb?new URL(thumb):null;
        const img=u&&u.protocol==="https:"&&(u.hostname===host||u.hostname.endsWith("."+host))?thumb:null;
        if(!headline||!link)return null;
        return {source:name,title:headline.slice(0,230),url:link,
          published_at:Number.isFinite(date)?Math.floor(date/1000):null,
          thumbnail_url:img,favicon_url:"https://"+host+"/favicon.ico"};
      }).filter(Boolean);
    }catch{return [];}
  }));
  for(const feed of feeds)stories.push(...feed);
  if(!stories.length)throw new RequestError("Publishers did not return usable RSS headlines");
  stories.sort((a,b)=>(b.published_at||0)-(a.published_at||0));
  return {source:"Publisher RSS feeds",fetched_at:time(),stale:false,
    articles:stories.slice(0,limit),note:"Headlines and source URLs only. Publisher-owned images may be missing; licensing and redistribution apply."};
}
function miningEstimate(sp){
  const names=["miner_hashrate_hps","network_hashrate_hps","block_reward","blocks_per_day",
    "price_usd","fee_percent","power_watts","electricity_usd_per_kwh"];
  const values=names.map(key=>{
    const v=sp.get(key);
    if(v===null||v.length>60||v==="")throw new RequestError("Missing "+key,400);
    const n=Number(v);
    if(!Number.isFinite(n)||n<0)throw new RequestError("Invalid "+key,400);
    return n;
  });
  const [miner,network,reward,blocks,price,fee,power,electricity]=values;
  if(!miner||!network||!blocks||fee>100||miner>network)
    throw new RequestError("Invalid network ratio, fee, or block interval",400);
  const coins=miner/network*reward*blocks*(1-fee/100);
  const gross=coins*price,energy=power*24/1000*electricity;
  return {source:"User inputs · expected-value model",coin_per_day_expected:coins,
    gross_usd_per_day_expected:gross,electricity_usd_per_day:energy,
    net_usd_per_day_before_other_costs:gross-energy,
    note:"Illustrative mathematical expected output; not actual mining earnings or a return guarantee."};
}
function poolRegistry(){
  const coins=[["btcs","Bitcoin Silver","SHA-256d","BTCS locally tested backend"],
    ["btc","Bitcoin","SHA-256d","Disabled candidate"],
    ["bch","Bitcoin Cash","SHA-256d","Disabled candidate"],
    ["ltc","Litecoin","Scrypt","Disabled candidate"],
    ["doge","Dogecoin","Scrypt / AuxPoW","Disabled candidate"]];
  return {source:"Silver Pool public staging snapshot; not live pool monitoring",
    active_public_pool_coins:0,ready_for_real_payouts:false,
    coins:coins.map(([id,name,algorithm,status])=>({
      id,name,algorithm,status,public_mining_enabled:false,
      payouts_enabled:false,network_hashrate_hps:null,pool_hashrate_hps:null,
      network_difficulty:null,block_reward:null,block_time_seconds:null,
      pool_fee_percent:null,miningpoolstats_url:id==="btcs"?"https://miningpoolstats.stream/bitcoinsilver":null
    })),note:"Offline staging profiles only; no verified public multi-coin mining or payouts."};
}
function notConnected(feature){
  throw new RequestError(feature+" requires a separately secured, connected backend. Alpha visitors cannot access local accounts, BTCS node RPC, private mining-pool datasets, or operator systems.",503);
}
async function handle(path,sp,env){
  switch(path){
    case "sources/status":return sourceStatus(env);
    case "market/global":return globalMarket(env);
    case "market/sentiment":return sentiment(sp,env);
    case "markets":return marketPage(sp,env,true);
    case "catalog/page":return marketPage(sp,env);
    case "catalog/search":return catalogSearch(sp,env);
    case "assets/profile":return profile(sp,env);
    case "assets/chart":return chart(sp,env);
    case "asset/quote":{
      const res=await cgQuote([assetID(sp)],env);
      return {source:res.source,asset:res.assets[0]||null,
        fetched_at:res.fetched_at,stale:false};
    }
    case "coin-watch/quotes":{
      const ids=(sp.get("ids")||"").split(",");
      if(ids.length<1||ids.length>50||ids.some(x=>!COIN_ID.test(x)))
        throw new RequestError("Select 1–50 valid CoinGecko IDs",400);
      return cgQuote(ids,env);
    }
    case "news":return newsFeed(sp,env);
    case "insights/trending":case "insights/categories":
    case "insights/exchanges":case "insights/defi":return insight(path,sp,env);
    case "dex/search":return dexSearch(sp,env);
    case "mining/estimate":return miningEstimate(sp);
    case "mining/coins":return poolRegistry();
    case "coinmarketcap/active":{
      if(!env.CMC_API_KEY)notConnected("CoinMarketCap API key");
      const page=integer(sp,"page",1,1,200),limit=integer(sp,"limit",100,25,200);
      const raw=await upstream(CMC+"?start="+((page-1)*limit+1)+"&limit="+limit+
        "&convert=USD",env);
      return {source:"CoinMarketCap",page,limit,has_more:(raw.data||[]).length===limit,
        fetched_at:time(),stale:false,assets:(raw.data||[]).filter(x=>x&&x.quote?.USD?.volume_24h>0&&x.quote.USD.price>0).map(x=>({
          id:"coinmarketcap:"+x.id,provider_id:String(x.id),name:x.name,symbol:x.symbol,
          rank:x.cmc_rank,price_usd:number(x.quote.USD.price),
          volume_24h_usd:number(x.quote.USD.volume_24h),
          market_cap_usd:number(x.quote.USD.market_cap),
          change_24h_pct:number(x.quote.USD.percent_change_24h)
        }))};
    }
    case "livecoinwatch/markets":{
      if(!env.LIVECOINWATCH_API_KEY)notConnected("LiveCoinWatch API key");
      const page=integer(sp,"page",1,1,500),limit=integer(sp,"limit",50,25,200);
      let all=[];
      for(let i=0;i<limit;i+=100){
        const count=Math.min(100,limit-i);
        const raw=await upstream(LCW,env,{method:"POST",data:{
          currency:"USD",sort:"rank",order:"ascending",
          offset:(page-1)*limit+i,limit:count,meta:true}});
        if(!Array.isArray(raw))throw new RequestError("Invalid LiveCoinWatch data");
        all.push(...raw);
        if(raw.length<count)break;
      }
      return {source:"LiveCoinWatch /coins/list",page,limit,has_more:all.length===limit,
        fetched_at:time(),stale:false,assets:all.filter(x=>SAFE_ID.test(x.code||"")&&x.rate>0&&x.volume>0)
        .map(x=>({id:"livecoinwatch:"+x.code,provider_id:x.code,name:x.name,symbol:x.code,
          rank:x.rank,price_usd:number(x.rate),volume_24h_usd:number(x.volume),
          market_cap_usd:number(x.cap),change_24h_pct:number(x.delta?.day)?(x.delta.day-1)*100:null,
          market_status:"provider-reported-volume"})),
        note:"Market data by LiveCoinWatch; codes are not merged to other provider identities."};
    }
    case "coinbase/pairs":notConnected("Coinbase pairs (separate provider implementation)");
    case "mining/overview":notConnected("BTCS node RPC");
    case "pools/market":notConnected("Authorized MiningPoolStats pool data");
    case "universal/networks":return {networks:[
      {id:"btcs",name:"Bitcoin Silver L1",family:"UTXO",currency:"BTCS",configured:false},
      {id:"ethereum",name:"Ethereum",family:"EVM",currency:"ETH",configured:false},
      {id:"bsc",name:"BNB Smart Chain",family:"EVM",currency:"BNB",configured:false},
      {id:"solana",name:"Solana",family:"Solana",currency:"SOL",configured:false},
      {id:"base",name:"Base",family:"EVM",currency:"ETH",configured:false}
    ],source:"Public alpha registry",note:"RPC is not connected to public alpha."};
    case "universal/search":notConnected("Multichain explorer RPC");
    case "health":return {status:"alpha",source:"Cloudflare Pages",
      connected_btcs_node:false,accounts_enabled:false};
    default:throw new RequestError("This feature is not connected in the public alpha.",503);
  }
}
export async function onRequestGet(context){
  const url=new URL(context.request.url);
  const path=url.pathname.replace(/^\/api\/?/,"");
  if(path.startsWith("account/"))return json({error:"Account APIs are not available on the public alpha."},403);
  let age=path==="market/global"?240:([ "news","insights/categories","insights/exchanges" ].includes(path)?900:120);
  if(path==="mining/estimate"||path==="health"||path==="sources/status")age=0;
  // Edge cache is shared and contains no personal data. Query values are validated
  // before any external call. Cloudflare Pages rate limiting should be configured
  // separately in dashboard for production public use.
  try{
    const cache=typeof caches!=="undefined"?caches.default:null;
    const key=new Request(url.toString(),{method:"GET"});
    if(cache&&age){const cached=await cache.match(key);if(cached)return cached;}
    const data=await handle(path,url.searchParams,context.env||{});
    const response=json(data,200,age);
    if(cache&&age)context.waitUntil(cache.put(key,response.clone()));
    return response;
  }catch(e){
    const status=e instanceof RequestError?e.status:503;
    return json({error:e instanceof RequestError?e.message:
      "This data source is temporarily unavailable.",source:path},status);
  }
}
export function onRequestPost(){return json({error:"Public alpha is read-only. No account, trading or wallet writes are enabled."},405);}
export function onRequestPut(){return onRequestPost();}
export function onRequestDelete(){return onRequestPost();}
