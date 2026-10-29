# Silver Scan — Silver Labs Explorer & Research Terminal

**Development prototype — not a hosted, complete or audited market service.**

Silver Scan is an independent Silver Labs product, separate from any explorer
owned by the Bitcoin Silver organization. It combines a BTCS L1 block explorer
prototype with a developing multi-coin market research terminal.

## Capabilities in this branch

| Section | Implementation | Important limitation |
|---|---|---|
| BTCS L1 Explorer | Python RPC block/transaction lookup, address views, SQLite indexing | Local prototype; partial indexing and reorg gaps; not a canonical proof |
| Markets | CoinGecko-backed, USD market-cap page with ranks, prices, volume and supply | External reference data; first 100 assets; no historical charts or verified chain identity |
| Coin Watch | Watch/unwatch provider IDs saved in this browser | No login, cloud sync or alerts; display limited to top-100 market snapshot |
| DEX Scan | DEX Screener token/pair search with chain, pair and token contract identity | External research only, no SilvEx listing, trade or swap |
| BTCS L2 / NFT / token indexing | Future phased integration | Not implemented or operational |
| Pool analytics / SilvEx integration | Planned verified API adapters | No live integration is claimed |

All research responses state the external source, retrieval timestamp and stale
cache condition. Data is never invented when providers or backends fail. The
ticker alone must never be used to identify a token; DEX pairs include the
source's chain and pair address, while market items retain stable CoinGecko IDs.

## Run locally

The frontend and Python API are served together, on a loopback-only
development address by default. Set a valid BTCS RPC node URL and credentials
in the **local environment**; never add credentials to tracked files.

```sh
export BTCS_NETWORK=main
export BTCS_RPC_URL=http://127.0.0.1:10567
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
python3 -m pytest -q tests/test_market_data.py tests/test_indexer_canonical.py tests/test_http_api.py
node --test tests/test_static_ui.test.mjs
node --check app/static/explorer.js
node --check app/static/research.js
python3 -m compileall -q app tests
```

The new `tests/test_market_data.py` suite uses mocked provider responses and
does not make live HTTP requests. Those tests do not prove remote uptime,
provider coverage or live production readiness.

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
