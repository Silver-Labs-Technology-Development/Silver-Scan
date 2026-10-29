# SilverScan — 38-feature implementation and acceptance matrix

**Current product reference:** https://silver-scan.silver-labs-technology-development.workers.dev/
**Feature reference:** https://silver-scan.silver-labs-technology-development.workers.dev/features
**Production UI is frozen as the approved design.**

This checklist maps the 38 features currently described in the GitHub feature directory. Existing status labels below come from the feature page's source at branch \`main\`, NOT from independent live backend verification. Even a "preview" is not "done". Before marking a feature implemented, run real-data local integration tests, quality checks, and compare against the approved Cloudflare UI.

**Important source of truth:** The user's Ubuntu checkout has a newer modular local backend (\`app/server.py\`, \`app/service.py\`, \`app/node.py\`) with extensive uncommitted changes. GitHub \`main\` has a different, older service layout. Back up local tracked and untracked changes first; reconcile files manually, do not reset/clean, and never overwrite local changes from this branch.

**Status vocabulary:** P = UI/backend preview; I = partial/integration needed; R = roadmap. "Verified" only after test evidence; no fake data.

| # | Pillar | Feature | Existing page status | Minimum concrete acceptance test |
|---|---|---|---|---|
| 01 | Markets | Crypto rankings | P | Source-attributed price and 24h volume observations, paging and unique asset IDs; don't claim market cap if supply unavailable |
| 02 | Markets | Coin profiles & charts | P | Contract/mint identity, real sampled or traded series clearly distinguished, timestamp and market coverage |
| 03 | Markets | Fear & Greed | P | Actual attributed sentiment observations, history and stale/unavailable behavior |
| 04 | Markets | Dominance & global metrics | P | Document coverage, circulating supply and price inputs; no invented global cap |
| 05 | Markets | Coin Watch | P | Locally saved unique IDs, refresh and disappearance handling, no false verified badge |
| 06 | Markets | Performance heatmap | P | Correct 24h changes from observed data, snapshot age, accessible mobile layout |
| 07 | Markets | Trending & categories | P | Source-backed trends, category mapping and dated records, no unsupported predictions |
| 08 | Markets | Exchanges & liquidity | P | Direct venue market directory, currency pair identities, quotes, order-book liquidity only when available |
| 09 | Markets | Compare coins | P | Align currency/time/source; no cross-chain symbol-only matching |
| 10 | Markets | Crypto News | P | Publisher headlines, timestamps and original links, no copied articles |
| 11 | Markets | Portfolio analytics & alerts | P | Local-only consentful portfolio storage, source times, price alerts with accurate thresholds, security review before accounts public |
| 12 | Mining | BTCS network mining | I | Live BTCS Core height, difficulty, network-estimated hashrate and error handling |
| 13 | Mining | Mining pool directory | R | Verified pool URLs/APIs, attribution, network and snapshot timestamp, no invented hashrate |
| 14 | Mining | Multi-coin algorithms | R | Per-network PoW algorithms, maturity rules and rewards grounded in nodes/specs |
| 15 | Mining | Blocks & confirmations | I | Exact canonical block hash/height/confirmations and reorg handling |
| 16 | Mining | Silver Pool integration | R | Read-only verified Silver Pool endpoints, miner/share/block metrics, privacy and access control |
| 17 | Mining | PoW-S research | R | Documented proposal data, no fabricated staking returns or payout eligibility |
| 18 | Chains | BTCS L1 explorer | I | Live Core RPC, indexed UTXOs, sync lag, reorg rollback and honest partial status |
| 19 | Chains | Multi-chain explorer adapters | R | Ethereum, BNB, Solana + other configured RPC with chain ID verification and rate limits |
| 20 | Chains | Addresses & balances | I | Native balance, token identity and partial-history completeness labels |
| 21 | Chains | Token holders | R | Exact contract/mint balance index and reorg-aware holder counts with indexed coverage |
| 22 | Chains | Smart contracts & verification | R | Read ABI and verified-source provenance; distinguish metadata from actual source verification |
| 23 | Chains | NFTs & collections | R | Canonical chain + contract/mint, metadata safety, owner history and partial coverage labels |
| 24 | Chains | Gas & network fees | R | Chain-native RPC fee estimates, currency precision and observed timestamps |
| 25 | Chains | Cross-chain relationships | R | Only independently verified bridge/wrapped asset relationships with source references |
| 26 | DEX | DEX Scan pairs | P | Chain + pair contract identity, pool liquidity snapshot and attribution |
| 27 | DEX | Liquidity monitoring | R | Pool reserves, historical observations, normalized units and manipulated-pool warnings |
| 28 | DEX | New pools & token discovery | R | Event-based discovery, checkpointed source and exact deployment timestamps |
| 29 | DEX | Whale & wallet flows | R | Traceable indexed on-chain moves with unknown-entity labels, no ungrounded identity claims |
| 30 | DEX | DeFi protocols & TVL | R | Contract-indexed positions/reserves and explicit double-counting exclusions |
| 31 | DEX | Global DeFi overview | P | Attributed external data, dated confidence/coverage labels and stale states |
| 32 | DEX | Swap routes | R | Read-only route research; disable execution/signing until separate audit |
| 33 | Projects | Rich project profiles | R | Verified project identity, network/contract listings and sourced metadata |
| 34 | Projects | Sponsored project billboards | R | Admin approval, sponsorship labels and no implied token verification |
| 35 | Projects | Campaign analytics | R | Privacy-respecting aggregate counts, consent and accurate disclosure |
| 36 | Projects | Silver Labs ecosystem | I | Read-only linked project profiles with each service's true readiness |
| 37 | Projects | Listings & integration reviews | R | Review workflow, chain identity checks, provenance and conflict-of-interest policy |
| 38 | Projects | Developer APIs & status | R | Versioned read-only API, rate limits, pagination, docs, health and provenance |

## Recommended delivery sequence

1. **P0 — Preserve approved UI.** Diff deployed Cloudflare homepage and feature pages against current local rendering and GitHub static assets. Recover the live HTML/CSS/JS into local with a backup and no automatic overwrite of local backend code. Never deploy without authorization.
2. **P1 — Existing services.** Restore BTCS Core RPC and local index, authenticated Silver Pool read-only endpoint contract, read-only network adapter routing, source status and existing market/research services. Verify exact URL, health and partial-data states.
3. **P2 — Independent data plumbing.** Integrate \`app/venue_observations.py\` plus \`app/venue_api.py\` from this isolated branch, backed by SQLite. Collect a small direct-exchange sample; do not expose into public UI before verifying redistribution rights.
4. **P3 — Multichain discovery.** Implement bounded and resumable EVM ERC-20 logs plus Solana SPL/Token-2022 program indexers with checkpoints, exact native units, chain identities, backfill progress and reorg handling.
5. **P4 — Market + DEX analytics.** Expand native trade-tape collection, independently build OHLCV, discover DEX pools, calculate liquidity and separate on-chain vs off-chain volumes.
6. **P5 — Advanced exploration.** Token holders, NFTs, verified smart-contract source, bridge links, mining directory, TVL and permissioned project metadata.
7. **P6 — Accounts and platform operations.** Portfolio alerts, project listings/moderation, developer API and analytics, after privacy/security reviews.

## Interfaces for Cline

- GET \`/api/venues/sources\` — last attempt/success and failure status (not a live probe).
- GET \`/api/venues/markets?venue=coinbase&limit=50\` — known direct exchange pairs and latest stored samples.
- GET \`/api/venues/history?venue=kraken&market=XXBTZUSD&limit=100\` — sampled last-price history, **not OHLCV**.

Cline must mount these routes in the *newer local server* after inspecting its dispatch. The supplied \`app/venue_api.py\` does not edit that server by itself. Data collection is started separately via explicit CLI and needs a scheduler for recurring refreshes.

## Required final feature acceptance evidence

Each feature row must record: code file/PR, API contract, real source, test command + result, local URL and screenshot, security issues, index coverage/staleness, and reviewer sign-off. Tests with mocked data demonstrate parsing correctness, **not** production data availability or permissions to redistribute venue data.

**Never mark all 38 complete just because their cards appear in the feature directory.**
