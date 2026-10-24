# Silver Scan architecture

This document describes the intended explorer and indexing boundary. It is a
design note, not a description of running software.

## Design principles

1. **The node is authoritative.** The indexer follows the node's active chain;
   it never decides validity.
2. **Canonicality is explicit.** Every entity carries its block hash,
   confirmation count, and reorg status.
3. **Ingestion is idempotent.** Replaying a block or a range must not duplicate
   rows or balances.
4. **Derived data is labeled.** An indexer result is a convenience view, not
   final settlement or proof of payment.
5. **Backfill and reindex are normal operations.** They need documented,
   measured procedures, not ad-hoc scripts.

## Proposed data flow

```text
BTCS Core RPC ──► L1 ingester ──┐
                                ├──► canonicality ──► index store ──► query API ──► web UI
BTCS L2 RPC  ──► L2 ingester ──┘
```

## Components

### L1 ingester

Reads blocks and transactions from BTCS Core, normalizes addresses and values,
and records the block hash chain. It must handle pruned nodes, missing
transactions, and restart gaps.

### L2 ingester

Reads EVM blocks, receipts, and logs from BTCS L2. Token transfers are decoded
from logs with the emitting contract recorded. Reverted transactions keep their
receipt but must not be shown as value transfers.

### Canonicality and reorgs

Tracks the active chain by block hash, not height alone. On a reorg, mark
orphaned blocks and reverse their derived effects in the same transaction that
applies the replacement chain. Expose the reorg depth and confirmation count.

### Index store

Normalized tables for blocks, transactions, inputs/outputs or EVM transfers,
addresses, tokens, contracts, and ingestion checkpoints. Migrations are
versioned. Large backfills are resumable.

### Query API

Read-only, paginated, rate-limited endpoints. Responses include the indexed
chain tip so a client can detect staleness. Search resolves a block height,
block hash, transaction hash, address, or contract.

### Web UI

Pages for blocks, transactions, addresses, tokens, and contracts. Empty and
unavailable states are explicit. No page implies finality beyond the recorded
confirmation count.

## Open decisions

- PostgreSQL for shared deployments versus SQLite for a single local instance.
- One database with L1/L2 namespaces, or separate stores per layer?
- Which L2 contract-verification flow is in scope for the first release?
- How much historical backfill is required for a useful developer testnet?
- Which API shape should the platform SDK standardize?

## Threat model (initial)

| Risk | Impact | Initial control |
| --- | --- | --- |
| Reorg mishandling | Wrong balances and history | Hash-based canonicality, transactional reorg reversal |
| Replayed ingestion | Duplicate rows or inflated balances | Idempotent keys and checkpoints |
| Malformed RPC data | Crashes or corrupt indexes | Schema validation and bounded parsing |
| Query abuse | Resource exhaustion | Pagination, rate limits, query timeouts |
| Stale index presented as live | Misleading payment status | Chain-tip metadata and explicit staleness labels |
| Public database exposure | Data leak | Loopback defaults and no bundled credentials |

## Non-goals

Silver Scan does not provide custody, signing, trading, payments, or consensus.
It indexes what the nodes report and states the limits of that view.
