# SilverScan Feature Completion & Cline Integration Handoff

**Date:** 2026-10-29  
**Production UX:** https://silver-scan.silver-labs-technology-development.workers.dev/  
**Production features:** https://silver-scan.silver-labs-technology-development.workers.dev/features  
**Scope of this branch:** Back-end-only direct market observations and a structured feature inventory. The existing tested `app/venue_observations.py` implementation is canonical; do not create a second collector.

## Non-negotiable production/UI protection

1. Keep the existing Cloudflare `silver-scan` Worker and its approved visual design unchanged.
2. Do **not** push this development work to `main` or deploy it to Cloudflare automatically.
3. Keep Cline's substantially changed local `app/server.py`, `app/service.py`, `app/node.py`, `app/config.py`, `app/main.py`, database, and other uncommitted files intact.
4. Review/compare production assets before changing any local HTML/CSS/JS. Preserve site shell, navigation, responsive layout, branding, and both themes.
5. If feature development requires any new UI, use the same existing design components; preview locally and request approval before deployment.
6. Do not remove features just because an API is offline. Show unavailable/partial with the reason and timestamp.
7. No trading, custody, order placement, payout, transaction-signing or arbitrary-RPC proxy in the new read-only APIs.

## Complete existing feature scope

`docs/silverscan-feature-catalog.json` contains **38 existing features** from the committed `app/static/features.html` grouped into:
- Markets & Research — 11
- Mining & Proof of Work — 6
- Blockchains & On-Chain Data — 8
- DEX & DeFi — 7
- Projects & Ecosystem — 6

It also contains **18 proposed additions** inspired by the useful research functionality of broader market and on-chain platforms. These are original SilverScan feature specifications, not copied source code or UI.

**Important:** Current `display_status` labels are taken from the feature page, not independently verified tests. `verified_implementation: false` prevents turning a prototype or unverified integration into a misleading completed claim. Cline should update verification in its local implementation matrix after successful end-to-end tests, not blindly turn everything green.

### Additional 18 features

| Category | Proposed feature | Definition of done |
|---|---|---|
| Markets | Historical market snapshots | Persist dated, attributed price/rank snapshots and disclose coverage |
| Markets | Dedicated gainers/losers | Compute from comparable observations, not stale or different-venue samples |
| Markets | Recently discovered assets | Report the first independently observed chain/contract event and index start |
| Markets | Altcoin market breadth | Publish independently designed eligibility and methodology, not a proprietary cloned index |
| Markets | Fiat and crypto conversion | Provide timestamped rate-based comparisons, not executable transactions |
| Markets | Category rotation | Verify category taxonomy and price source, show period/source |
| Markets | Advanced portfolio cost basis | User-entered read-only transaction ledger, P/L and supported accounting methods |
| Markets | Multiple watchlists and alerts | User-controlled threshold notices, without executing trades |
| Markets | Exchange order-book depth | Source-licensed bids/asks, spread, depth and freshness with limitations |
| Markets | Cross-venue price comparisons | Verify asset identity and quote-normalization before comparison |
| Markets | Stablecoin issuance/supply | Contract-specific mint/burn events with index completeness disclosure |
| Chains | Token unlock/vesting calendar | Attributed on-chain events and publicly documented vesting schedules |
| Chains | Token contract risk signals | Show mint/admin/upgrade flags and verified evidence, never a guarantee |
| Chains | Chain activity analytics | Indexed TPS/fees/block intervals/coverage with chain-specific semantics |
| Chains | Verified exchange reserve addresses | Proof of wallet identity; explicitly NOT a solvency conclusion |
| Ecosystem | Crypto event calendar | Attributed verifiable project events, updates and governance |
| Ecosystem | Education/glossary | Original definitions with context, sourcing and revision dates |
| Ecosystem | Data quality/methodology | Transparent source provenance, staleness, calculation and coverage descriptions |

## Shipped in this isolated development branch

- `app/venue_observations.py`: tested read-only Coinbase Exchange and Kraken REST collectors, exact decimal prices, bounded observations, local SQLite and source status.
- `app/venue_api.py`: read-only, locally-mounted API adapter for source status, market pairs, and sampled price history.
- `tests/test_venue_observations.py`: existing offline collection and route tests.
- `docs/silverscan-feature-catalog.json` and catalog validation tests.

**Not shipped:** a full exchange firehose, global volume/cap statistics, OHLC candles, web frontend changes, historical chain indexers, automatic background scheduler, production deployment, independent listing verification, or a market-wide asset identity map.

### Local-only development operations

Run in the actual development repository after safely integrating this branch:

```bash
python3 -m pytest -q tests/test_feature_catalog.py
python3 -m unittest discover -s tests -p 'test_venue_observations.py' -v
python3 -m app.venue_observations --venue coinbase --market BTC-USD
python3 -m app.venue_observations --venue kraken --market XXBTZUSD
```

The two collector commands make outbound read-only requests **only when explicitly invoked**. They can fail because of network reachability, rate limits, provider API changes, or licensing constraints. Test with mock fixtures before enabling any recurring job.

To integrate the API without overwriting the current local backend:

```python
from app.venue_api import handle_get
from app.venue_observations import VenueStore

# See docs/DIRECT-VENUE-ENGINE-HANDOFF.md for construction and lifecycle.
# Inside existing read-only GET routing:
result = handle_get(request_path_with_query, venue_store)
if result is not None:
    http_status, json_payload = result
    # Send JSON via the existing validated response helper.
```

Endpoints after Cline mounts them:
- `GET /api/venues/sources`
- `GET /api/venues/markets?venue=coinbase`
- `GET /api/venues/history?venue=kraken&market=XXBTZUSD`

Both read **stored** observations; neither accesses the exchange APIs when requested by a browser.

### Data handling rules

- A venue trading pair like `BTC/USD` is **not** a verified blockchain asset identity.
- Prices are in the venue's quote currency; base volume is in base-asset units. Do not label all prices USD or sum rolling 24h volumes over repeated samples.
- Sampled last-trade prices are **not** verified OHLCV candles.
- Source health reflects the **last collection attempt**, not a synchronous live probe.
- Do not claim verified circulating supply, market cap, proof of reserves, or volume without independent supporting measurements.
- Validate permissions for public redisplay of exchange market data before exporting it to production.

## Next implementation order for Cline and SilverScan

**Gate A — visual parity/local service:** Snapshot hosted pages; make the local version display the **same** interface; preserve all newer local source/data; restore local routes and report exact working port. Do not publish.

**Gate B — chain indexing:** Finish BTCS node/RPC and index synchronization, Ethereum/BNB event indexing, Solana mint/program indexing; store checkpoints and reorg/rollback semantics. Distinguish lookup-only vs comprehensive indexed coverage.

**Gate C — independent market backend:** Integrate venue collector read-only routes and add verified asset mapping, source coverage, independent market statistics, DB persistence, scheduled collection with backoff, and local health dashboards.

**Gate D — DEX research:** Pool discovery from on-chain factory/program events, swap decoding, liquidity snapshots and volume aggregation with verified protocol and token identities.

**Gate E — broaden existing 38 features:** Test each individual capability with genuine source data and implement incomplete components. Do not mark complete based on a UI mock.

**Gate F — 18 proposed features:** Implement and test independently with complete source attribution, methodology, and privacy/security review.

**Release gate:** Compare local and hosted UI visually; run relevant tests; obtain user approval; only then merge and deploy. The production Cloudflare Worker remains unchanged during development.
