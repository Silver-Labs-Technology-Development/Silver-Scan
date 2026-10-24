# Silver Scan Implementation Plan

Version: 1.0.0
Date: 2026-10-24
Repository: ~/Silver-Labs/Silver-Scan / Silver-Scan
Branch: main
Priority: Priority 2 - after Silver Pool repair

## 1. Phase 0 - Repository and Architecture (Current)

### 1.1 Audit Complete
- [x] Repository audit documented in docs/REPOSITORY-AUDIT.md
- [x] Existing docs/ARCHITECTURE.md reviewed (candidate design note, not authorizing implementation)
- [x] README.md scope and boundaries confirmed (planned, no working code)
- [x] License, security, and repository facts documented
- [ ] docs/IMPLEMENTATION-PLAN.md creation in progress

### 1.2 Working Application Foundation
- [ ] Add minimal FastAPI/Flask application skeleton
- [ ] Configure Python environment and dependencies
- [ ] Verify pip install -e . or equivalent works
- [ ] Add src/ directory with initial module structure
- [ ] Add basic health check endpoint
- [ ] Run pytest and verify 0 tests pass initially (baseline)
- [ ] Record exact build/test commands and results

### 1.3 GitHub Actions Workflow
- [ ] Create .github/workflows/ci.yml
- [ ] Add Python lint (ruff/pylint)
- [ ] Add Python type checks (mypy)
- [ ] Add test suite execution
- [ ] Add production build step
- [ ] Add deployment verification step (local only)
- [ ] Include repository-boundary test rejecting product-specific paths from other repos

### 1.4 Environment Configuration
- [ ] Create .env.example with safe placeholders
- [ ] BTCS_RPC_URL=http://127.0.0.1:29444
- [ ] BTCS_RPC_USER=test
- [ ] BTCS_RPC_PASSWORD=test
- [ ] BTCS_RPC_WALLET=pooltest
- [ ] BTCS_POOL_ADDRESS=
- [ ] BTCS_POOL_FEE=2.0
- [ ] BTCS_MIN_PAYOUT=0.01
- [ ] BTCS_STRATUM_HOST=127.0.0.1
- [ ] BTCS_STRATUM_PORT=3333
- [ ] BTCS_POOL_DB=data/pool.sqlite3
- [ ] Add .gitignore entries for .env, data/, __pycache__/, .pytest_cache/
- [ ] Never commit actual secrets

### 1.5 Repository-Boundary CI Check
- [ ] Add CI step that scans for disallowed paths/imports from other repositories
- [ ] Example: reject import silver_pool or import official_website from Silver-Scan
- [ ] Example: reject references to ../Silver-Pool/ or ../../Official-Website/
- [ ] Document the check and its rationale

## 2. Phase 1 - Market Terminal and Coin Watch

### 2.1 UI Foundation
- [ ] Add responsive HTML/CSS template with product identity
- [ ] Add market overview page structure
- [ ] Add searchable coin list placeholder
- [ ] Add asset detail page placeholder
- [ ] Implement stale-data indicators and loading/error/empty states

### 2.2 Provider Abstraction
- [ ] Create providers/ directory with base provider interface
- [ ] Implement CoinGecko adapter (public API, no auth required)
- [ ] Terms: Free tier, 50 requests/minute, attribution required
- [ ] Cache with TTL respecting rate limits
- [ ] Source timestamp display
- [ ] Stale-data marker (>5m old = stale)
- [ ] Implement CoinMarketCap adapter (requires API key)
- [ ] Terms: Free tier, 333 requests/day, attribution required
- [ ] Rate limit handling
- [ ] Error states when quota exhausted
- [ ] Implement LiveCoinWatch adapter (requires API key)
- [ ] Terms: Rate limits, attribution
- [ ] Implement DEX Screener adapter
- [ ] Terms: Rate limits, attribution
- [ ] Create provider registry and fallback logic

### 2.3 Data Display
- [ ] Price with source attribution and update timestamp
- [ ] Market cap, 24h volume, 24h change
- [ ] Stale-data indicator (red when >5m old)
- [ ] Empty states for no data / API failure
- [ ] Rate-limit handling (503 or graceful degradation)

### 2.4 Mock Data and Demo Mode
- [ ] Add mock data only in test fixtures, labelled as such
- [ ] Add --demo or NODE_ENV=development flag for demo mode
- [ ] Never present demo data as live data in production UI
- [ ] Add explicit "demo mode" banner when active

### 3. Phase 2 - BTCS L1 Explorer

### 3.1 RPC Capability Definition
- [ ] Define required BTCS Core RPC methods
- [ ] getblockcount, getblockhash, getblock, gettransaction, getrawtransaction
- [ ] getaddressinfo, getbalance, getmempoolinfo, gettxoutsetinfo
- [ ] Document available methods vs. planned methods
- [ ] Test actual RPC methods against running BTCS Core node

### 3.2 Backend Data Adapter
- [ ] Create adapters/btcs_l1.py - isolated backend data adapter
- [ ] Implement block query: height -> hash -> full block data
- [ ] Implement transaction query: hash -> transaction details
- [ ] Implement address query: address -> activity summary
- [ ] Handle RPC failures gracefully (retries, circuit breaker, error responses)
- [ ] Add health endpoint: /api/health/btcs-l1 returning status and chain tip

### 3.3 Data Display
- [ ] Block height, hash, timestamp, miner, confirmation count
- [ ] Transaction hash, size, weight, virtual size, fee, status (confirmed/unconfirmed)
- [ ] Address activity: incoming/outgoing transactions, confirmation status
- [ ] Clearly distinguish unavailable, unconfirmed, and confirmed data
- [ ] Empty states when RPC is offline or data not yet indexed

### 3.4 Indexing and Database
- [ ] Choose storage: SQLite (local single-instance) vs PostgreSQL (shared)
- [ ] Design schema: blocks, transactions, address_activity, checkpoints
- [ ] Implement incremental indexing (new blocks only since last checkpoint)
- [ ] Implement backfill procedure (resumable, measured)
- [ ] Implement reorg handling: mark orphaned blocks, reverse derived effects
- [ ] Add health monitoring: lag, last indexed block, indexing speed

### 4. Phase 3 - BTCS L2 Explorer

### 4.1 Whitepaper Verification
- [ ] Inspect actual BTCS L2 RPC, settlement, batch, confirmation, and withdrawal interfaces
- [ ] Verify contract verification flow before implementing explorers
- [ ] Distinguish L2 execution from L1 anchoring/settlement in design

### 4.2 Adapter Development
- [ ] Create adapters/btcs_l2.py with verified interfaces only
- [ ] Show blocks, transactions, accounts, tokens, NFTs when capabilities available
- [ ] Display settlement and challenge/finality status only where supported by verifiable records
- [ ] Clearly label unsupported functionality and incomplete trust assumptions
- [ ] Do not invent RPC methods, claim trustlessness, or infer finality from visible transactions

### 5. Phase 4 - Silver Pool Analytics

### 5.1 API Contract Definition
- [ ] Define versioned, read-only API contract for pool statistics

### 5.2 Data Display
- [ ] Show pool health, current statistics, blocks, miners/workers and payout history only when pool backend supplies data
- [ ] Keep explorer operational if pool is offline (unavailable states)
- [ ] Until Silver Pool API deployed: use unavailable states or test fixtures labelled as fixtures
- [ ] Never simulate live operation when pool is down

### 6. Phase 5 - DEX Scan and SilvEx Integration

### 6.1 Documentation Verification
- [ ] Inspect SilvEx repository/API documentation and verify endpoints before integrating
- [ ] Verify actual data sources and reliability before building analytics

### 6.2 Analytics Building
- [ ] Build read-only market/pair, liquidity, volume, swap and transaction analytics
- [ ] Where reliable data exists, display with source attribution
- [ ] Keep trading, wallet connections, signatures, and fund-moving operations out of scope
- [ ] Document chain/network identity and data-source reliability

### 7. Phase 6 - Security, Quality and Release Readiness

### 7.1 Automated Tests
- [ ] Provider failures (API errors, rate limiting, timeouts)
- [ ] RPC failures (node down, method not found, connection refused)
- [ ] Rate limiting behavior (per-provider limits)
- [ ] Stale data handling (TTL, stale markers)
- [ ] Malicious input validation (XSS, injection)
- [ ] Reorg handling (indexing restart/recovery)
- [ ] API authorization (where applicable)

### 7.2 Security Safeguards
- [ ] Safe defaults server-side
- [ ] Dependency checks (known-vulnerable deps avoided)
- [ ] Input validation on all APIs
- [ ] Security headers (CSP, HSTS, X-Content-Type-Options)
- [ ] No secrets in source control (.env.example only)
- [ ] Loopback defaults for RPC connections

### 7.3 Deployment Documentation
- [ ] Deployment procedure documented
- [ ] Backup/restore procedure documented
- [ ] Monitoring setup documented
- [ ] Upgrades documented
- [ ] Rollback procedure documented

### 7.4 Production Build and Deployment
- [ ] Test production build from Silver-Scan/ directory
- [ ] Verify actual published URL after deployment
- [ ] Record URL and smoke test results before calling deployed\## 8. Deliverables Checklist

### Phase 0 Deliverables
- [x] docs/REPOSITORY-AUDIT.md - created
- [ ] docs/IMPLEMENTATION-PLAN.md - to be created (in progress)
- [ ] Working application foundation in Silver-Scan/
- [ ] GitHub Actions CI workflow
- [ ] .env.example with safe placeholders
- [ ] Repository-boundary CI check
- [ ] Build and test commands recorded with exact results

### Phase 1 Deliverables
- [ ] Responsive UI foundation (market overview, search, asset detail)
- [ ] Provider abstraction (CoinGecko, CoinMarketCap, LiveCoinWatch, DEX Screener)
- [ ] Data display with attribution, timestamps, stale indicators
- [ ] Mock data in tests only, demo mode flag
- [ ] API endpoints planned (not connected to live data yet)

### Phase 2 Deliverables
- [ ] BTCS L1 RPC capability definition
- [ ] Backend data adapter (block, transaction, address queries)
- [ ] Data display with confirmation status, timestamps, fees
- [ ] Database schema and incremental indexing
- [ ] Reorg handling
- [ ] Test scenarios for failures and reorgs

### Phase 3 Deliverables
- [ ] Verified L2 RPC adapters only
- [ ] Settlement/finality status where supported
- [ ] Trust assumptions labeled

### Phase 4 Deliverables
- [ ] Versioned read-only API contract
- [ ] Pool statistics display when data available
- [ ] Unavailable states when pool offline

### Phase 5 Deliverables
- [ ] Verified SilvEx endpoints
- [ ] Read-only DEX analytics
- [ ] Trading/signing out of scope

### Phase 6 Deliverables
- [ ] Automated tests for failure modes
- [ ] Security safeguards documented and implemented
- [ ] Deployment, backup, monitoring, upgrades, rollback documented
- [ ] Production build tested from Silver-Scan/
- [ ] Actual published URL verified before deployment

## 9. Repository Isolation Rules (Reiterated)

| Allowed | Not Allowed |
|---------|-------------|
| All Silver Scan code, UI, APIs, indexers, tests, configuration, docs, CI/deployment inside Silver-Scan/ | Developing in Official-Website, Silver-Pool, or BTCS L2 repo |
| Consuming documented public APIs, RPC interfaces, versioned shared schemas | Copying application into another repository as side effect |
| CI checks rejecting product-specific paths/workflows from other repos | Overwriting uncommitted work, resetting branches, force-pushing, deleting branches |
| | Committing secrets, RPC credentials, private keys, production configuration |

## 10. Sequencing and Dependencies

- Priority 1: Silver Pool repository separation, website deployment, real backend hosting, release gates
- Priority 2: Silver Scan implementation using this specification
- Do not block architecture planning and local implementation unnecessarily
- Do not claim live data, indexing, pool integration, L2 settlement visibility, or deployment unless independently verified
- If Silver Pool repair is still in progress, continue Silver Scan's isolated work without altering Silver Pool or Official-Website

## End of Implementation Plan
