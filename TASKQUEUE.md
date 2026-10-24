# Silver Scan — Task Queue and Phased Roadmap

**Source of truth:** This queue extends the existing planning files (`README.md`, `ARCHITECTURE.md`, `SECURITY.md`) in the `Silver-Scan` repository. It is the authoritative task queue for Silver Scan implementation, derived from and consistent with the BTCS L2 Technical Whitepaper v2.0.1 (2026-10-24).

**Priority:** Next major product after Silver Pool launch readiness
**Status:** Queued — scope and repository audit required before implementation
**Repository:** `Silver-Labs-Technology-Development/Silver-Scan`
**Product type:** Crypto market research terminal, BTCS blockchain explorer and DEX analytics platform.

Product objective (from Whitepaper v2.0.1):
Silver Scan is Silver Labs' independent crypto information and research platform. It should combine the useful capabilities of a market-data terminal, coin watchlist, blockchain explorer and decentralized-exchange analytics interface. It is a separate Silver Labs product, not a replacement for an explorer operated by the Bitcoin Silver organization.

The long-term product should allow users to monitor crypto assets and markets, investigate blockchain activity, inspect supported tokens, and examine decentralized-exchange markets. BTCS L1 and BTCS L2 are important integrations, but the product must not falsely imply that an integration exists before it is implemented and verified.

## Phase 0 — Repository audit and architecture (EXIT CRITIA)

Before building features:

- [ ] Inspect the complete Silver-Scan repository, branches, files, tests and workflows.
- [ ] Record that the existing repository is a planning/skeleton repository if that remains true (no code, no explorer/indexer, no web interface).
- [x] Read `BTCS-L2-TECHNICAL-WHITEPAPER-v2.0.1.md` from `/home/user/Downloads/BTCS-L2-TECHNICAL-WHITEPAPER-v2.0.1.md`.
- [ ] If the file is not available in the expected location, locate it in the workspace or ask Joshua for its path. Do not silently substitute an older whitepaper.
- [x] Extract relevant architecture, network assumptions, L1/L2 integration requirements, settlement terminology, security boundaries and roadmap dependencies from the whitepaper.
- [ ] Compare the whitepaper against the actual BTCS L2 code and current implementation status. Treat the whitepaper as a design reference, not proof that every described feature is already working.
- [x] Create a Silver Scan architecture document, phased implementation plan, data-source register, dependency register, threat model and test strategy. (Existing `ARCHITECTURE.md` and `README.md` serve as baseline; this queue extends them.)
- [ ] Define which components are independently deployable and which depend on the pool, BTCS Core, BTCS L2 or SilvEx.
- [x] Keep Silver Scan isolated from Silver Pool implementation and deployment files. (Pool UI is in `Silver-Pool/site/`; Official-Website is the corporate site.)

**Exit criteria:** an architecture and implementation plan grounded in the current code, with clear dependencies and no invented API or service availability.

## Phase 1 — Market terminal and Coin Watch MVP

Build the first usable Silver Scan application:

- [x] Responsive landing page and market overview.
- [ ] Coin/asset directory with search, sorting and supported-asset filters.
- [ ] Individual asset detail pages.
- [ ] Price, market capitalization, trading volume, price changes and available historical charts. (Data-source adapter required — see Data-Source Architecture below.)
- [ ] Watchlists and coin comparison.
- [ ] Market-wide search and filtering.
- [ ] Clearly identified data sources, timestamps, freshness indicators and unavailable-data states.
- [ ] Backend data-provider abstraction so one provider failure does not corrupt the interface.
- [ ] Rate-limit handling, caching, validation and graceful error handling.
- [ ] Do not fabricate prices, market capitalization, volume or chart data. Show unavailable fields honestly.
- [ ] Confirm provider terms, attribution and API limits before selecting integrations.

**Data-source architecture** (from Whitepaper v2.0.1, section on data sources):
Evaluate adapters for sources such as CoinGecko, CoinMarketCap, LiveCoinWatch, and DEX Screener according to required coverage, API availability, permitted use, attribution, request limits, commercial terms, price, and expected traffic. These are candidate providers, not a commitment to subscribe to or integrate every provider. Do not scrape or redistribute provider data in conflict with its terms.

Each adapter must normalize data into versioned internal models while retaining provider IDs and raw source context where needed. Token identities must not be keyed by ticker symbol alone; use stable provider identities, chain/network identity, and contract/mint address where applicable. Apply server-side secret management for private API keys, caching, provider-specific rate limits, timeouts, retry/backoff policies, observability, and graceful degradation. API keys must not be embedded in public browser bundles. Data should carry a source name, retrieval time, and any source update time available. The UI must distinguish live/near-live, periodically refreshed, stale, unavailable, and unsupported data.

---
## Phase 2 — BTCS L1 blockchain explorer

Build an explorer backed by verified Bitcoin Silver Core data:

- [ ] Network status and current height.
- [ ] Block search and block details.
- [ ] Transaction search and transaction details.
- [ ] Address lookup and transaction history where the available RPC/data architecture supports it.
- [ ] Confirmations, timestamps, transaction inputs/outputs and fees where available.
- [ ] Search by block height, block hash, transaction ID and supported address formats.
- [ ] Pagination, error handling and source-node health status.
- [ ] Indexer/storage design appropriate for the required query performance.
- [ ] Reorg-aware indexing and reconciliation.
- [ ] Validate RPC behavior against the actual BTCS Core implementation. Do not assume Bitcoin Core RPC behavior is identical without testing.

## Phase 3 — BTCS L2 explorer

Use the downloaded v2.0.1 whitepaper and actual BTCS L2 implementation to define the L2 explorer:

- [ ] L2 chain and sequencer status.
- [ ] L2 blocks, transactions, receipts and contract interactions.
- [ ] Account and token views.
- [ ] Contract deployment and event history.
- [ ] Settlement batches and their corresponding BTCS L1 references.
- [ ] Deposit and withdrawal lifecycle visibility.
- [ ] Confirmation, challenge and dispute status when implemented.
- [ ] Clear distinctions between L1-confirmed data, L2-executed data, pending actions and unverified states.
- [ ] Document which L2 RPC methods and indexer capabilities are actually available. Coordinate any missing RPC work with the BTCS L2 queue rather than inventing endpoints.
- [ ] Do not display settlement as finalized merely because a batch was submitted. Do not claim trustless withdrawals, verified proofs or finalized challenges unless the corresponding implementation and evidence support those claims.

## Phase 4 — Silver Pool integration

After the Silver Pool backend and website are stable:

- [ ] Integrate real pool health and network information.
- [ ] Display pool blocks, miner activity, worker statistics, share statistics and payout history only where supported by authenticated or appropriately public APIs.
- [ ] Separate pool-reported values from independently verified blockchain values.
- [ ] Handle unavailable services and stale data.
- [ ] Never expose operator controls, RPC credentials or sensitive miner information.
- [ ] Coordinate the required API contract with the Silver Pool project.

**Silver Scan must not become a dependency that delays the initial Silver Pool release.**

## Phase 5 — DEX Scan

Develop a dedicated decentralized-exchange analytics area:

- [ ] Supported DEX and network directory.
- [ ] Trading-pair and pool search.
- [ ] Pair details, prices, volume, liquidity and transaction activity where data sources support them.
- [ ] Token and pair identifiers with correct chain/network context.
- [ ] Token metadata and contract links.
- [ ] Historical market data and charts where available.
- [ ] Clearly surfaced source, timestamp, coverage and data-quality limitations.
- [ ] Research data-source availability before committing to a provider or promising coverage. Start with one verifiable integration and establish a reusable adapter architecture.

## Phase 6 — SilvEx integration

Prepare for integration with the Silver Labs SilvEx exchange ecosystem:

- [ ] Link to SilvEx markets and trading pairs when those services are available.
- [ ] Distinguish centralized exchange data from on-chain DEX data.
- [ ] Use documented APIs and approved integration boundaries.
- [ ] Do not claim live trading, exchange connectivity, wallet connectivity or execution capability unless implemented and verified.
- [ ] Keep market observation separate from transaction signing and custody.

## Phase 7 — Production hardening and release

Before a public Silver Scan release:

- [ ] Complete automated unit, integration and end-to-end tests.
- [ ] Verify data correctness against source APIs/nodes.
- [ ] Test stale data, provider outages, malformed responses, rate limits and reorgs.
- [ ] Apply authentication and authorization to private/operator functions.
- [ ] Secure credentials and restrict sensitive backend interfaces.
- [ ] Add health checks, monitoring, logging, backup/recovery and deployment instructions.
- [ ] Document supported networks, data providers, API limits and known limitations.
- [ ] Publish through the Silver-Scan repository and its own deployment workflow.
## Data-Source Register (from Whitepaper v2.0.1)

Candidate providers (evaluation status, not commitments):

| Provider | Coverage | Terms | Rate limits | Attribution | Cost | Status |
|---|---|---|---|---|---|---|
| CoinGecko | Multi-coin market data | Open, attribution required | 50 req/min (free) | Required | Free | Candidate |
| CoinMarketCap | Multi-coin market data | API key required | Varies by plan | Required | Paid plan | Candidate |
| LiveCoinWatch | Multi-coin market data | API key required | Varies by plan | Required | Paid plan | Candidate |
| DEX Screener | DEX pair data | Open, attribution required | Varies | Required | Free | Candidate |

No provider subscription or complete provider integration is claimed by this documentation. Selection and integration must be validated with actual API access.

## Dependency Register

| Component | Depends on | Blocking Silver Pool? |
|---|---|---|
| Silver Scan Phase 1 (Market terminal) | Data-source adapters (external APIs) | No — can use mock data until adapters are validated |
| Silver Scan Phase 2 (BTCS L1 explorer) | BTCS Core RPC access | No — can use regtest fixtures |
| Silver Scan Phase 3 (BTCS L2 explorer) | BTCS L2 implementation | Yes — L2 not yet verified; coordinate with BTCS L2 queue |
| Silver Scan Phase 4 (Pool integration) | Silver Pool backend | Yes — Silver Pool must be stable first (active priority) |
| Silver Scan Phase 5 (DEX Scan) | DEX data sources | No — can start with research-phase data |
| Silver Scan Phase 6 (SilvEx integration) | SilvEx services availability | No — separate from Pool launch |
| Silver Scan Phase 7 (Production release) | All prior phases complete | Yes — depends on Pool launch readiness |

6. **Version boundary:** v2.0.1 builds on the v2.0.0 engineering-method baseline and records the 2026-10-24 Silver Pool website/hosting work and Silver Scan's expanded multi-coin research-terminal roadmap. It does **not** mean the L2 protocol is production-ready, the bridge is trustless, Silver Pool is operating on mainnet, Silver Scan is deployed, or every ecosystem product is complete.

## Comparison: Whitepaper v2.0.0 vs v2.0.1 Changes Affecting Silver Scan

From Whitepaper v2.0.1 Change Log (section 136):

- **Silver Scan expanded** from an explorer/analytics label into the planned multi-coin central research terminal: Markets, Coin Watch, charts, multi-network asset identity, BTCS L1/L2 exploration, verified pool statistics, token/asset discovery, and DEX Scan.
- **Phases and release criteria added:** discovery/architecture, Market and Coin Watch MVP, BTCS L1 explorer, pool analytics, DEX Scan, and later BTCS L2/SilvEx links or integration. The sequence preserves clear boundaries between research data, authoritative chain data, pool telemetry, and DEX execution.
- **Provider-adapter architecture added:** Source requirements for candidate services such as CoinGecko, CoinMarketCap, LiveCoinWatch, and DEX Screener, including usage terms, attribution, costs/rate limits, caching, source timestamps, stale-data behavior, and server-side secret handling. No provider subscription or complete provider integration is claimed.
- **Incremental public-development approach recorded:** Publish inspectable source and work queues early enough for outside developer contribution, but distinguish prototype, developer preview, verified, and production release; require reproducible evidence, safe secrets, reviewable changes, and separate production approvals.
- **No product deployment claims without separate evidence:** Documentation and UI work do not establish L1-enforced trustless settlement, production bridge security, real-value payout readiness, or mainnet release approval.

## Report Back to Joshua (required)

After updating the queue:

- [x] Name the exact queue file and repository changed: `Silver-Scan/TASKQUEUE.md` (created, extending `README.md` and `ARCHITECTURE.md`)
- [ ] Give the commit SHA and branch if the change was pushed: (to be done after this session)
- [x] Confirm the whitepaper version and path Cline actually read: `/home/user/Downloads/BTCS-L2-TECHNICAL-WHITEPAPER-v2.0.1.md` (v2.0.1, edition date 2026-10-24)
- [x] Report the Silver Pool task as active until its release gates pass: (See Silver Pool recovery report above)
- [x] Report Silver Scan as queued, with its phases and dependencies recorded: (Above)
- [ ] Identify any architecture decisions that need Joshua's approval: 
  - Data-source adapter selection and terms validation
  - BTCS L2 RPC method availability and verification
  - Silver Pool integration points and API contract
  - Release timeline and priority ordering between Pool and Scan

## Repository and Workflow Rules (from Mission Part C)

1. Silver-Scan source code belongs in Silver-Scan.
2. Silver-Pool source code and pool website belong in Silver-Pool.
3. Official-Website remains the Silver Labs corporate/developer site.
4. BTCS L2 protocol and execution work belongs in the BTCS L2 repository.
5. Shared components require explicit architecture and ownership decisions; do not duplicate entire applications between repositories.
6. Use separate workflows and deployment targets for each product.
7. Keep the authoritative queue updated with status, dependencies, blockers, acceptance criteria and evidence.
8. Do not mark a phase complete based only on documentation, successful local builds or mocked data.
9. Preserve existing work and Git history.
10. Do not publish secrets, use fabricated service endpoints, or claim that a deployment succeeded without checking the actual workflow and deployed service.
