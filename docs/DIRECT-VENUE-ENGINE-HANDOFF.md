# SilverScan independent venue observation engine — Cline handoff

**Isolation:** branch feature/direct-venue-observations. No production/static UI or existing service files are changed. Do not merge into production main without review.

## Delivered code

- app/venue_observations.py: bounded, read-only Coinbase Exchange and Kraken Spot market directory/ticker collectors. Records Decimal-safe price strings and source health in a standalone SQLite database.
- app/venue_api.py: adapter function returning (HTTP status, JSON) for GET /api/venues/sources, /api/venues/markets?venue=..., /api/venues/history?venue=...&market=... .
- tests/test_venue_observations.py: offline stubbed exchange API tests.

Market identities are scoped to the venue and original exchange pair ID, not coin ticker. Coinbase last price and rolling base-currency volume are separate; a precise USD volume is **not** asserted. Kraken estimated quote volume explicitly uses rolling 24h VWAP × rolling base volume.

**Do not present these price samples as executed trade OHLCV, total exchange volume, market capitalization, circulating supply, verified coins, or aggregated coin-wide prices.** Licensing restrictions still apply before public redistribution.

## Manual local integration

1. Preserve and back up the current local working tree (including untracked files) before merging anything.
2. Review differences between GitHub main and the newer local app/server.py/service.py architecture.
3. Import these *new*, standalone modules only. Avoid overwriting existing files with the old GitHub server.
4. Test: python3 -m unittest discover -s tests -p 'test_venue_observations.py' -v
5. Poll a small pair sample from a terminal after verifying API terms:
   python3 -m app.venue_observations --venue coinbase --market BTC-USD
   python3 -m app.venue_observations --venue kraken --market XXBTZUSD
6. Inspect data/venue_observations.sqlite3 (keep under gitignore).
7. Optional local server integration: instantiate VenueStore(db_path), initialize it, and call app.venue_api.handle_get(self.path, store) inside the existing **GET-only** dispatch. If it returns None, fall through to the preexisting server. Serialize the body via the existing JSON response helper. Handle SQLite availability safely. Do not expose a write or arbitrary proxy endpoint.
8. For local UI, add functionality only behind the **approved Cloudflare visual design**. No redesign, no production deploy, no live Worker configuration change.
9. Add server-side polling under your own scheduler/service manager, capped to known markets and respectful of provider limits, after verifying external network responses.

## Scope boundaries and next work

- This is a **sample-collection engine**, not a full live exchange index, public dataset license, background daemon, or complete historical trade tape.
- Build native trade ingestion for true OHLCV and venue-observed volume; eventually add websockets and resilient queue workers.
- Build explicit cross-venue coin identity mapping by network/contract or verified native chain identity; do NOT deduplicate different assets based solely on symbol.
- Connect to the user's active local modular server after inspecting its current route contract.
- Keep all production Cloudflare assets unchanged. User approves its current design.
- Do not push to main or change Cloudflare until the user reviews local changes.
