# SilverScan Cloudflare market source connectors (October 2026)

This branch adds Cloudflare Worker **read-only** market adapters. None uses the
developer's local machine. All responses are provider-attributed, and provider
identifiers are namespaced rather than merged by ticker.

| Provider | Worker path | Requirements |
| --- | --- | --- |
| CoinLore | `/api/coinlore/markets?page=1&limit=25` | Keyless, live on-demand |
| CoinMarketCap | `/api/coinmarketcap/active?page=1&limit=25` | Keyless CMC cryptocurrency listings, rate and usage restrictions apply |
| CoinMarketCap exchanges | `/api/exchanges/cmc?page=1&limit=25` | Keyless venue identity mapping only, no independently verified safety or volumes |
| Coinbase | `/api/coinbase/pairs?offset=0&limit=25` | Public Advanced Trade spot pairs; volume is in the **base coin**, USD price only for USD-quoted pairs |
| CoinGecko | `/api/catalog/page?page=1&limit=25` | Server-side `COINGECKO_API_KEY` plus reviewed `CG_COMMERCIAL_USE_APPROVED=yes` |
| LiveCoinWatch | `/api/livecoinwatch/markets?page=1&limit=25` | Server-side `LIVECOINWATCH_API_KEY` plus reviewed `LCW_DISPLAY_APPROVED=yes` |
| MiningPoolStats | `/api/pools/market` | Still unavailable until lawful operator-approved data import can be hosted |

## Cloudflare deployment verification

Use the **existing** `silver-scan` Worker, not a new Cloudflare site.
Review its configuration and custom domains before updating. The repo currently
supplies `wrangler.worker.toml` for the Workers project; deployment command:

```sh
npx wrangler deploy --config wrangler.worker.toml
```

If Worker Builds is connected to GitHub `main`, merged changes can deploy
automatically. A passing GitHub CI workflow does **not** prove the Worker
has deployed. Check the Cloudflare production deployment's commit SHA and
actually request the above paths on the public domain.

## API credentials and quota controls

Put keys in Cloudflare Worker **Secrets**, not GitHub, browser JavaScript,
Wrangler plain-text variables, URLs, screenshots, or build logs.
Any `*_APPROVED=yes` flag requires an actual review of the provider's
display/commercial permission and terms; adding a flag does not grant rights.
Do not expose the LiveCoinWatch POST upstream endpoint to browsers.
The Cloudflare API is a GET-only read-only adapter.

The `/api/sources/status` response reports which adapters are **configured
for on-demand requests**. It does not probe their live connectivity. Providers
can return rate limits, empty data, or access denials. Do not label them
"connected" without a successful request through the deployed Cloudflare Worker.
Do not fabricate prices, sum overlapping provider counts, or label CMC/Coinbase
listings as independent chain verification.

## Continuing work

Add monitored provider health checks, Cloudflare cache quotas and alerts,
and a reviewed authorized MiningPoolStats dataset adapter when permission is
obtained. A full Bitcoin Silver node/indexer still needs persistent hosting
outside ordinary Cloudflare Workers.
