# SilverScan — Silver Labs Explorer & Research Terminal

**Development prototype with a release-ready public viewing alpha branch. Live Cloudflare hosting must be verified in the Pages dashboard before announcing a URL.**

SilverScan is an independent Silver Labs product, separate from any explorer
owned by the Bitcoin Silver organization. It combines a BTCS L1 block explorer
prototype with a developing multi-coin market research terminal.

## Existing Cloudflare Workers service: `silver-scan`

**The actual user-provided dashboard URL is for Cloudflare Workers, not Pages.**
Use the existing Worker named `silver-scan` and the production branch
`main`. The Workers-specific configuration in
[`wrangler.worker.toml`](wrangler.worker.toml) provides static assets, a
restricted Cloudflare API and server-side `ASSETS` binding. See
[`docs/CLOUDFLARE-WORKERS-ALPHA.md`](docs/CLOUDFLARE-WORKERS-ALPHA.md)
for GitHub connection, build command, security verification and monitoring.

The optional Pages configuration remains separate; **do not create a duplicate
Pages project** when releasing to the existing Worker.

## Cloudflare public viewing alpha

The canonical GitHub and Cloudflare Workers production branch is **`main`**,
separate from active local development worktrees and feature PR branches. The site is static
HTML/CSS/JavaScript with a narrow Cloudflare Pages Function in
[`app/static/_worker.js`](app/static/_worker.js); **it does not run the
local Python account database or node RPC backend**.

- Read [Cloudflare deployment instructions](docs/CLOUDFLARE-ALPHA.md) for
  correct Git connection, `app/static` output directory, attribution,
  optional approved provider secrets, Cloudflare Web Analytics and final
  external HTTPS verification.
- The full user account login/portfolio backend remains local-only;
  browser-local Coin Watch stars can still work on a public static site.
- Market feed access requires the appropriate commercial license and
  Cloudflare-secret provider key; incomplete endpoints show an honest
  unavailable state rather than fabricated results.
- External mining data, payouts, DEX trading, wallet signing and unguarded
  blockchain RPC are not enabled on a viewing alpha.
- A successful GitHub push/CI check is **not proof of public Cloudflare
  deployment**. Only a verified external HTTPS deployment counts as live.

## Capabilities in this branch

| Section | Implementation | Important limitation |
|---|---|---|
| BTCS L1 Explorer | Python RPC block/transaction lookup, address views, SQLite indexing | Local prototype; partial indexing and reorg gaps; not a canonical proof |
| Markets & Graphs | Ranked CoinGecko/CMC/LiveCoinWatch backend adapters with 25/50/100/200 per page and source-attributed charts | Availability depends on approved provider access and commercial permissions; never claim a merged 22k active-asset index |
| Coin Watch & Manual Portfolio | Browser-local starred IDs, catalog search and a local-only password-backed manual holdings prototype | Public alpha has no account registration or synchronized portfolios; no holdings are verified from wallet balances |
| Coin Profile & Price Charts | Provider-backed asset profile, contract references, price history for 24h/7d/30d/90d/1y where API plans permit | Historical coverage varies by provider and API plan; missing history is shown as unavailable |
| Sentiment & Dominance | Alternative.me Crypto Fear & Greed score/history and CoinGecko BTC/ETH market-cap dominance graphic | Market-level reference data, not coin-specific sentiment or buy/sell advice |
| DEX Scan | DEX Screener token/pair search with chain, pair and token contract identity | External research only, no SilvEx listing, trade or swap |
| BTCS L2 / NFT / token indexing | Future phased integration | Not implemented or operational |
| Mining research | BTCS Core network difficulty/hashrate/height readout and external MiningPoolStats reference | Requires a connected node; not Silver Pool miner accounting or directory integration |
| Pool analytics / SilvEx integration | Planned verified API adapters | No live integration is claimed |

All research responses state the external source, retrieval timestamp and stale
cache condition. Data is never invented when providers or backends fail. The
ticker alone must never be used to identify a token; DEX pairs include the
source's chain and pair address, while market items retain stable CoinGecko IDs.

## Visible full-product feature map

Navigate to `/features.html` from the SilverScan main dashboard. This page
visibly maps **36 capabilities across five pillars**: Markets & Research,
Mining & Proof of Work, Blockchains & On-Chain Data, DEX & DeFi, and Projects &
Ecosystem. It is searchable and filterable by `UI/backend prototype`,
`partial integration`, and `on roadmap`.

The directory is a real page, not a slide or a fake statistics screenshot. Its
links open working portions of the existing SilverScan preview. Unsupported
modules (exchange comparisons, multi-chain token holders, NFTs, smart-contract
verification, lending analytics, project advertising inventory and production
wallet integrations) have clearly marked unavailable/roadmap states.

The main navigation also contains a **performance heatmap**, drawn from
actual CoinGecko top-100 snapshot values; each tile links to a detailed coin
profile. Tile size approximates rank, **not exact market-cap area**. It is
not a category heatmap, and no unavailable data is simulated.

The information architecture combines broad market research, mining-pool
discovery and blockchain/token explorer navigation while remaining an original
Silver Labs interface. This branch does not copy other sites' proprietary
visuals or claim to have their full data coverage.

## SilverScan information architecture (October 2026)

This build uses **SilverScan** as one word. Product navigation has distinct
destinations rather than duplicating Coin Universe as a standalone application:

- `/` — market-cap rankings across CoinGecko source pages; choose **25, 50,
  100 or 200 coins per page** and use Previous/Next. Source pages may filter
  zero-volume or unpriced records, so page counts are not an independently
  verified number of actively traded assets. The separate heatmap is a
  limited top-market visual.
- `/coin-watch.html` — **Coin Watch + Coin Universe**: browser-local
  watchlist (unique CoinGecko IDs), broad catalog search including
  `bitcoin-silver-2`, CoinGecko/CMC market-page research and Coinbase spot
  pairs. A saved ID does not assert trading volume or wallet support.
- `/news.html` — independent publisher-attributed headline feed.
- `/mining.html` — Silver Pool coin **readiness snapshot** and BTCS Core
  network telemetry when connected, with a user-input expected-value mining
  calculator. BTCS has a locally exercised backend; BTC/BCH/LTC/DOGE are
  disabled candidates from public Silver Pool staging configuration.
- `/features.html` — searchable platform capability roadmap.
- `/data-hub.html` — compatibility redirect for old bookmarks to the new
  Coin Watch / Crypto News / Mining destinations.

Read [the provider and licensing boundaries](docs/DATA-SOURCES.md) before
commercial use. Market providers, exchange pairs, mining-pool trackers and
news publishers have different rights, freshness and validity rules.

### Shared color contrast and preview status

`app/static/theme.css` and `theme.js` provide a persistent accessible
light/dark toggle to all standalone pages; the main market page shares the
same stored preference through `research.js`. Dark mode uses opaque
medium-navy cards with ice-blue links; light mode uses off-white/white cards
with deep blue text. Automated contrast tests check key foreground/background
pairs against the WCAG 4.5:1 text threshold. This **does not replace a
human browser/screenshot review** on desktop and mobile.

No public SilverScan API/data-hosting deployment, live multi-coin mining, real
pool ROI feed or commercial data entitlement is claimed by this PR.

## Run locally

The frontend and Python API are served together, on a loopback-only
development address by default. Set a valid BTCS RPC node URL and credentials
in the **local environment**; never add credentials to tracked files.

```sh
export BTCS_NETWORK=main
export BTCS_RPC_URL=http://127.0.0.1:10567
# Example matches Silver Pool's mainnet RPC default (10567); verify your installed node's config.
# Provide BTCS_RPC_USER and BTCS_RPC_PASSWORD privately from your node config
export SILVERSCAN_DB="$PWD/silverscan.db"
python3 -m app.indexer --max-blocks 100
# Re-run until caught up, or explicitly start the continuous operator CLI:
python3 -m app.indexer --follow --max-blocks 100 --interval 15
```

The CLI starts from genesis, works in batches of at most 1000 blocks, checks
parent hashes, and reverses orphaned transaction spends before reindexing a
replacement branch. It does **not** fetch coins, transfer funds, or modify the
Bitcoin Silver node. A full historical sync may take a while and needs adequate
storage and backups. For BTCS `main`, configure the already-synced node's
private RPC address. This is not a production service manager; keep a supervised
deployment and off-host backups as a future operations gate.

**Important database upgrade:** the original experimental `blocks`, `txs`
and `outputs` tables stored output amounts as floating-point values. The
new indexer deliberately creates separate `chain_blocks`, `chain_txs`,
`chain_outputs` and `chain_inputs` tables with exact integer satoshis.
Old data is retained but excluded from the new balance calculations. A
genesis-first reindex is required, rather than silently converting inaccurate
historical balances. Address pages are marked **partial** and cannot be
considered authoritative merely because a block height is shown.

Run from the repository root:

```sh
python3 -m app.main
```

Open <http://127.0.0.1:8000>. The BTCS Explorer section requires the separate
Bitcoin Silver node and valid `app/config.py` RPC settings. Markets and DEX
Scan use public third-party APIs through the **Python backend**, not through
the browser. Network access and provider limits apply. Optional Demo access
uses `COINGECKO_DEMO_API_KEY` in the server environment; never place keys in
static files. No key is required for the public endpoint, but it can return
rate-limit errors.

A static Cloudflare Pages deployment of `app/static/` alone **cannot** serve
the Python `/api/` endpoints, perform node RPC or supply market data. Such a
deployment must show unavailable states unless an independently configured,
secured backend serves `/api/` at the same origin. This branch does not
configure or certify a production backend.

Tests:

```sh
python3 -m pytest -q tests/test_market_data.py tests/test_indexer_canonical.py tests/test_http_api.py tests/test_coverage.py
node --test tests/test_static_ui.test.mjs
node --check app/static/explorer.js
node --check app/static/research.js
node --check app/static/charts.js
node --check app/static/features.js
node --check app/static/data-hub.js
python3 -m compileall -q app tests
```

The new `tests/test_market_data.py` suite uses mocked provider responses and
does not make live HTTP requests. Those tests do not prove remote uptime,
provider coverage or live production readiness.

## Price charts, graphics, and Fear & Greed

The market-first SilverScan UI includes a responsive top-100 research table,
true 7-day coin sparklines, real coin profile pages with five selectable price
history ranges, global market totals, gainers/losers, a dominance ring for
Bitcoin/Ethereum/other shares, and a Fear & Greed gauge with a historical line
chart. All graphics are **original SVG/CSS components** rendered using numeric
observations from supported providers; no CoinMarketCap/CoinGecko site charts
or branded graphics are copied.

Data sources and separate availability requirements:

- **CoinGecko:** coin markets, icons, asset profiles, historical USD price
  charts and global market capitalization/dominance. The public API may be
  rate-limited; some historical periods require a provider plan. Add optional
  `COINGECKO_DEMO_API_KEY` to the private server environment only.
- **Alternative.me:** external Crypto Fear & Greed Index, current score and
  up to 30 days of history. This is not the proprietary CoinMarketCap Fear &
  Greed indicator. Its source is displayed alongside the graphic, with a
  direct attribution link as required by the data provider.
- **DEX Screener:** external observed pairs and market data; never imply a
  verified token or a SilvEx exchange listing.
- **BTCS Core RPC:** network mining fields and L1 indexer data, not an
  independent pool-miner directory or a node consensus proof.

If upstream data fails, the UI displays unavailable/stale status instead of
inventing prices, hashrates, exchange volume, fear scores or trends. The
global top bar may show unavailable values while the separate market provider
is reachable. Chart and source timestamps belong to the underlying API
responses; this is not a real-time exchange trading terminal.

**Preview update:** If the existing `http://127.0.0.1:8100` preview is from
an earlier detached Git worktree, it will not update automatically when this
branch changes. Fetch pull request 1 and start a **new** isolated worktree on
a different port, while preserving the original files. Use the instructions
in the PR description to avoid overwriting any existing local work.

## Data sourcing & operational boundaries

- **Markets:** CoinGecko public `/api/v3/coins/markets`, USD, up to 100
  assets. Requests cached for 120 seconds per process; stale values may be
  shown for up to 10 minutes during an outage and are labeled **STALE**.
  Source: https://www.coingecko.com/.
- **DEX Scan:** DEX Screener `/latest/dex/search`, limited to 25 returned
  pairs per query, same cache and stale behavior; pairs include chain/pair ID,
  contract/mint identifiers, liquidity, volume and source links. Source:
  https://dexscreener.com/.
- **No native volume attribution:** External prices, liquidity and volume are
  **not** Silver Labs' or SilvEx's executed volume.
- **No validation guarantee:** Market and token listing is informational.
  External token names and rankings may be inaccurate, spoofed, illiquid or
  unsupported. Do not infer custody, legitimacy, verified contracts or swaps.
- **Provider controls:** Fixed HTTPS upstream hosts, timeouts, response-size
  limits, cached requests and fail-closed error states. The current Python
  HTTPServer is only a local development server, without public rate limits,
  monitoring or independent security review.
- **Indexing:** Existing SQLite explorer code is experimental. Do not show
  historical address balances as final without reorg-safe recovery and
  spent-input reconciliation; a live BTCS L2 indexer is not implemented.

The planned roadmap is **multi-coin Markets / Coin Watch → BTCS L1 explorer
hardening → verified pool analytics → DEX Scan refinement → BTCS L2 / token
and NFT indexing → SilvEx integration**. AI assistance and L3 are separate
future research, not release requirements.

## Architecture and project documents

- [Architecture](docs/ARCHITECTURE.md) — intended chain adapter and canonicality model.
- [Implementation plan](docs/IMPLEMENTATION-PLAN.md) — historical phased requirements.
- [Security](SECURITY.md) — security scope.
- [License](LICENSE) — see license for reuse rights.

All rights reserved where specified in the repository license. Public access
to source code does not imply redistribution permission.
