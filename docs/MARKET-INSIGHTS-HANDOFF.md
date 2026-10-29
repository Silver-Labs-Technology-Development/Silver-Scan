# SilverScan market-insights implementation — Cline handoff

Date: 2026-10-29  
Development branch: `feature/direct-venue-observations`  
Draft PR: https://github.com/Silver-Labs-Technology-Development/Silver-Scan/pull/4

**DO NOT DEPLOY, MERGE TO MAIN, OR CHANGE APPROVED CLOUDFLARE UI.**  
Preserve all modified/untracked files in the local modular SilverScan checkout. The older repository app/main.py/server layout differs from the Ubuntu checkout. Port and node connections must be inspected, not assumed.

## Implemented in isolated branch

**Existing** `app/venue_observations.py` and `app/venue_api.py` provide:
- Coinbase Exchange and Kraken read-only public market pair discovery;
- Bounded REST price samples, decimal-preserving storage in a local SQLite database;
- Source health, market directory, and sample history API adapter (not auto-mounted).

**New** `app/market_insights.py` provides three additional local read-only feature APIs:
- `GET /api/insights/local/movers?venue=coinbase&window=1h&limit=10`: observed gainers and losers over 1h, 24h, or 7d, using samples at comparable times; returns coverage and exclusions.
- `GET /api/insights/local/quality`: exchange collection health, number of known pairs, sampled pairs, fresh pairs and observation lag, without a live upstream query.
- `GET /api/insights/local/compare?base_asset=native:bitcoin&quote_asset=fiat:USD`: cross-venue last-price comparison **only after explicit operator review of matching base and quote asset identities** and when fresh observations are sufficiently close in time.

All calculations retain Decimal precision, reject stale observations, and explicitly disclose that observations are **sampled last trades**, not actual trade-interval OHLCV or guaranteed executable prices.

## Tests

```bash
python3 -m pytest -q tests/test_venue_observations.py tests/test_market_insights.py tests/test_feature_catalog.py
```

The new market-insights module was independently exercised against eight offline fixture tests. GitHub CI also runs its tests; consult the actual PR checks before integration.

## Local integration (after backup, with Cline)

Read and preserve the local server's actual route contract first.

```python
from app.market_insights import InsightStore, handle_get as insights_get
from app.venue_observations import VenueStore

db_path = "data/venue_observations.sqlite3"
venue_store = VenueStore(db_path)
venue_store.initialize()
insights_store = InsightStore(db_path)
insights_store.initialize_mappings()

# In the *existing* GET dispatch only:
result = insights_get(request_path_with_query, insights_store)
if result is not None:
    status, body = result
    # Use the existing server's JSON response helper.
```

This module has **no HTTP POST, write, trading or public RPC proxy**. The operator-only `review_mapping` Python method is for explicit local confirmation of asset identity using evidence.

Example (only after the operator actually checks both identifiers and the evidence URLs):

```python
insights_store.review_mapping(
    "coinbase", "BTC-USD", "native:bitcoin", "fiat:USD",
    "https://www.coinbase.com/"
)
insights_store.review_mapping(
    "kraken", "XXBTZUSD", "native:bitcoin", "fiat:USD",
    "https://www.kraken.com/"
)
```

Do not automatically map all matching symbols; `BTC` and `XBT` here are exchange-specific native Bitcoin labels. For other assets, require chain/contract identity or a documented native asset identity. The evidence URLs above are examples of location, **not proof that a particular review was completed**.

### Readiness gates

1. **Data collection**: source-specific API terms verified; collector manually tested without leaking credentials; local bounded samples saved.
2. **History**: enough distinct historical samples exist; otherwise movers remain empty with coverage notes.
3. **Cross-venue**: manual base+quote asset mapping reviewed; last samples fresh and within 120 seconds of each other; else no comparison statistic.
4. **Frontend parity**: use the existing Cloudflare-hosted frontend design unchanged as the visual source of truth.
5. **Public release**: separate data licensing, privacy and security review, user approval, and verified production health.

## Larger feature completion queue

`docs/silverscan-feature-catalog.json` preserves all 38 features from the hosted directory and proposes 18 additions (56 total). The new module is an **implementation slice**, not a claim all 56 are complete.

Next independent slices: order-book depth with exchange license/fees, historical snapshot aggregation, verified token unlock calendar, on-chain holder distribution with checkpointed coverage, and chain activity indexes.

Avoid duplicating Cline's work on the Ethereum, Solana and BTCS indexers. Never replace his local `app/server.py` or `app/service.py` with older GitHub files.

## New implementation: historical sample series and market performance heatmap

`app/market_history.py` is a **new, strictly read-only** module using the same `data/venue_observations.sqlite3` database as the direct Coinbase/Kraken collector. It requires no separate migration. Two more local API adapters are available (but not automatically mounted in Cline's running server):

- `GET /api/insights/local/series?venue=coinbase&market=BTC-USD&window=24h&limit=180` — returns only genuine stored sample points and exposes time gaps, staleness and coverage for 1h, 24h, 7d, 30d, 90d and 1y. Missing historical intervals stay missing. Data is `sampled_last_traded_price`, **not an exchange candle series**.
- `GET /api/insights/local/heatmap?venue=coinbase&window=24h&quote=USD&limit=100` — a single-venue, same-quote, unweighted pair performance map with percent changes based on comparable observed samples, freshness checks and honest exclusions. This is **not** CoinMarketCap's market-cap-weighted top-100 heatmap.

The server can mount these without replacing existing routes or frontend code:

```python
from app.market_history import HistoryStore, handle_get as history_get
history_store = HistoryStore(db_path)

# In existing read-only GET dispatch, after validating route ownership:
result = history_get(request_path_with_query, history_store)
if result is not None:
    status, body = result
    # Serialize using current local server's secure JSON response helper.
```

Offline test contract:

```bash
python3 -m pytest -q tests/test_market_history.py tests/test_market_insights.py tests/test_feature_catalog.py
```

Only integrate into the **approved production-equivalent frontend**. Before drawing a history chart, label it as sampled price observations, show the first and last observation timestamps, and leave gaps visible. For the heatmap, keep each exchange separate, show quote currency and sample-coverage disclosure, never use market-cap sizing without confirmed supply and price data, and never represent the partial sampled pair list as the global top 100.

**Cline's reported environment, not independently verified:** local port 8084; 84 passing tests and one skipped; BTCS regtest at 127.0.0.1:19443; configured EVM/Solana RPC addresses. Do not assume mainnet or all RPC sources are connected merely because configured. Cline should separately validate visual parity by screenshot diff and solve the `Loading SilverScan…` and empty market-feed states.
