# SilverScan multi-source market/data policy

The platform is a **reader and research interface**, not a licensed bulk
redistribution feed, mining service or exchange. Discovering an asset ID is
different from observing an active market, verifying a blockchain/network or
making that asset tradeable.

## Sources and currently implemented endpoints

| Source | SilverScan path | Capability | Boundary |
| --- | --- | --- | --- |
| CoinGecko | `/api/catalog/search?q=BTCS` | Catalog ID discovery across its coin universe (incl. `bitcoin-silver-2`) | Entries are unverified catalog identities, **not** all active markets |
| CoinGecko | `/api/catalog/page?page=1&limit=100` | Server-side provider pagination, positive price/24h volume observations | No artificial 100-coin cap; API limit is 250 per page, preview defaults to 100 |
| CoinGecko | `/api/asset/quote?id=bitcoin-silver-2` | Fetch one low-rank asset directly by provider ID | No guaranteed quote; source may return no liquidity or rate-limit |
| CoinGecko | `/api/markets`, `/api/market/global`, `/api/assets/chart`, `/api/assets/profile` | Existing top-market overview, market cap, charts and profiles | Separate aggregate view; not global all-coin indexing |
| CoinMarketCap | `/api/coinmarketcap/active?page=1&limit=100` | Separate active-market listings, authenticated with `CMC_API_KEY` when supplied | Keyless rate-limited mode also supported; CMC provider ID is preserved |
| Coinbase Advanced Trade | `/api/coinbase/pairs?offset=0&limit=100` | Public spot-trading pair information | Pair count is **not** a unique coin count or global market cap |
| Publisher RSS | `/api/news?limit=30` | CoinDesk, Cointelegraph, Decrypt, The Block and Bitcoin Magazine source headlines, dates and article URLs | No copied article body or unsupported image scraping |
| Mining model | `/api/mining/estimate?...eight explicit inputs...` | Network-share expected output, gross estimate and electricity | Not actual miner payouts, an investment result or a guarantee |
| Bitcoin Silver RPC | `/api/mining/overview` | Locally connected Core network metrics | Requires a functioning node, no pooled miner metrics without Silver Pool adapter |
| MiningPoolStats | External directory link | Known external point of reference | No verified licensed bulk API has been established; **no third-party scraping or import is active** |

All pricing and news endpoints use allowlisted HTTPS hosts, bounded responses,
timeouts and cache/stale behavior. The code does not fabricate prices on source
failure. Provider errors and stale snapshots should be visible in the UI.

SilverScan now has distinct pages: `/coin-watch.html` combines broad CoinGecko ID discovery with locally saved watchlist coins and optional CMC/Coinbase comparisons; `/news.html` shows attributed publisher headlines; `/mining.html` includes verified network status and explicitly user-input mining estimates. `/data-hub.html` is a legacy bookmark redirect. The existing dashboard provides charts, project discovery, heatmap,
Fear & Greed and the BTCS L1 explorer.

## Important: catalog capacity is not measured coverage

CoinGecko and CoinMarketCap offer large catalogs and APIs with pagination.
SilverScan does **not** currently have 22,000+ independently indexed, live,
verified or tradeable assets. Its API routes let you query their catalogs and
active markets with source and timestamps; actual available count varies by
provider, cache, account plan, API quota, user query and source policy.

A full product-market catalog would require:

1. A licensed/approved commercial provider plan and attribution requirements.
2. Scheduled budgeted synchronization with backoff, incremental updates,
   idempotency and anomaly checks.
3. A persisted catalog with distinct provider IDs, network/contract identity,
   symbol collisions, asset delisting/deactivation and source timestamps.
4. Measured `discovered`, `market-observed`, `onchain-verified` and
   `independently indexed` counters.
5. Monitoring API quota/spend before enabling wide batch ingestion.

Never treat the count returned by `/coins/list` as a number of currently
trading coins. Never merge CMC, CG and Coinbase by ticker alone: multiple assets
can share tickers.

## Licensing and charges

- CoinGecko: commercial use currently requires a qualifying paid plan and
  prominent provider attribution. Public display does not automatically
  authorize API syndication/resale or unrestricted raw-data redistribution.
  See https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses
- CoinMarketCap: keyless and developer plans have different quotas and API
  access; consult the agreement before selling market data or using it in
  subscriptions. See https://coinmarketcap.com/api/keyless/
- Coinbase: the public Advanced Trade products endpoint describes available
  Coinbase trading pairs only.
- MiningPoolStats: do not automatically pull wholesale site data without
  documented permission and a supported API contract.
- News: link to original publisher, display byline/publisher and timestamp;
  review each outlet's syndication and caching terms before paid distribution.

**Charging project marketing or listing fees is separate** from the right to
sell data feeds. Paid placements should be labeled sponsored, independent
market rankings must not be influenced by payment, and no project gains
exchange access or wallet integration just by being listed.

## Preview and operational boundary

```sh
cd ~/Silver-Labs/Silver-Scan
# Check for existing uncommitted changes before choosing a branch/worktree.
# Pull request 1 holds the current dev UI and provider work.
git fetch origin pull/1/head
# Start an isolated CLEAN preview worktree as in the SilverScan README.
```

Optional environment keys for the Python backend are read server-side only:
`COINGECKO_DEMO_API_KEY` (development; not commercial entitlement) and
`CMC_API_KEY`. Never place them in static HTML, JS, commits or frontend code.

The backend defaults to loopback and is **not production-ready** for untrusted
public access. Live server deployment needs licensing, secure proxy, egress
budgets, quotas, denial-of-service defenses, access logs, telemetry, backups,
compliance review and commercial disclosure controls.
