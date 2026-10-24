# Silver Scan

> **Status: Planned — repository and scope only.**
> No explorer, indexer, database, API, or web interface exists here.

## Purpose

Silver Scan is the blockchain explorer and indexing product boundary for Silver
Labs. It is intended to make BTCS L1 and BTCS L2 activity inspectable without
requiring users to run a node or read raw RPC responses.

Silver Scan is independent of the BTCS L2 Studio's bounded local views. A
Studio view is not an indexer, an address-history service, or a
reorganization-aware explorer.

## Proposed scope

- Index blocks, transactions, receipts, and address activity.
- Separate chain adapters for BTCS L1 and BTCS L2.
- Token and NFT event indexing after the relevant standards are finalized.
- Reorganization detection, rollback, and canonical-chain labeling.
- Bounded read APIs with pagination and explicit freshness metadata.
- A web interface that labels local, testnet, and experimental networks.

## Explicitly out of scope until reviewed and approved

- Claims of complete address history or guaranteed finality.
- Custody, signing, or transaction submission.
- Public production endpoints without operations and abuse controls.
- Treating an indexed view as consensus proof.

## Integration points

- **BTCS Core** — L1 blocks, transactions, and chain state.
- **BTCS L2** — execution blocks, receipts, and settlement records.
- **silver-labs-platform** — network identity and schema contracts.
- **SilverPay / SilverForge** — display links and asset metadata, not authority.
- **SilvEx DEX Node** — shared indexing boundaries where responsibilities
  overlap.

## Decisions required before implementation

1. Initial chain coverage and whether L1 and L2 share one data model.
2. Database, retention, reindexing, and backup policy.
3. Reorganization depth and user-visible confirmation semantics.
4. API limits, caching, and abuse controls.
5. Which token/NFT standards are actually supported.

## First milestone

A local indexer for one chain with deterministic fixture replay, a documented
reorganization test, and a read-only block/transaction view. No production
deployment.

## Repository facts

- Local workspace path: `~/Silver-Labs/Silver-Scan`
- Default branch: `main`
- Implementation: none
- Tests run: none (no code)
- License: no license selected; no reuse rights are granted
- Visibility: public planning repository

This repository is labeled planned so that its existence is not mistaken for a
working explorer.
