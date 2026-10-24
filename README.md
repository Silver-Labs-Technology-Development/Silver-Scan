# Silver Scan

Blockchain explorer and indexing services for BTCS L1 and BTCS L2.

**Status: planned — scaffold only.** No indexer, database schema, API, or web UI
exists in this repository yet. Silver Scan defines the explorer boundary; it
does not replace a node or become a second source of consensus truth.

## Purpose

Make BTCS L1 and L2 activity searchable and explainable. A user should be able
to look up a block, transaction, address, token transfer, or L2 contract and
see a derived view that clearly states its source, confirmation state, and
limitations.

## Scope

Planned work, in dependency order:

1. **L1 ingester** — follow BTCS Core blocks, transactions, and reorgs.
2. **L2 ingester** — follow BTCS L2 EVM blocks, transactions, receipts, logs,
   and token transfers.
3. **Canonicality** — track the active chain, record reorgs, and expose
   confirmation counts instead of pretending a block is final.
4. **Index store** — normalized tables for blocks, transactions, addresses,
   token transfers, and contracts, with idempotent ingestion.
5. **Query API** — paginated read-only endpoints for search and entity pages.
6. **Web UI** — block, transaction, address, token, and contract views with
   explicit status labels.
7. **Operations** — backfill, reindex, health checks, metrics, and a documented
   recovery procedure.

## Out of scope

- Custody, signing, trading, or payment processing.
- Consensus changes or block validation.
- Replacing BTCS Core or BTCS L2 RPC as the authority.
- Guessing missing data or presenting an indexer result as final settlement.

## Planned components

| Component | Responsibility | Depends on |
| --- | --- | --- |
| `ingest-l1/` | L1 block and transaction ingestion | BTCS Core RPC |
| `ingest-l2/` | L2 EVM block, receipt, and log ingestion | BTCS L2 RPC |
| `indexer/` | Canonicality, reorg handling, backfill | Both ingesters |
| `store/` | Schema, migrations, idempotent writes | PostgreSQL or SQLite |
| `api/` | Read-only search and entity endpoints | `store/` |
| `web/` | Explorer UI | `api/` |

The directory names are proposed. They are not created yet.

## Integration points

- [btcs-core](https://github.com/Silver-Labs-Technology-Development/Silver-Labs-Bitcoin-Silver-Development)
  — L1 blocks, transactions, and chain state.
- [btcs-l2](https://github.com/Silver-Labs-Technology-Development/btcs-l2)
  — L2 EVM blocks, receipts, logs, and settlement records.
- [silver-labs-platform](https://github.com/Silver-Labs-Technology-Development/silver-labs-platform)
  — shared read client and schemas where they fit.
- [SilverPay](https://github.com/Silver-Labs-Technology-Development/SilverPay)
  and [SilverForge-Studio](https://github.com/Silver-Labs-Technology-Development/SilverForge-Studio)
  — deep links to transactions, tokens, and contracts.

## Local development

There is no runnable code yet. The intended development loop is a disposable
BTCS Core regtest node plus a disposable BTCS L2 dev node, both indexed into a
local database. Development defaults must bind to loopback.

## Safety and release status

This is a development scaffold with no implementation or audit. An explorer is
a derived view: label confirmations, reorgs, and unavailable data explicitly.
Never commit node cookies, wallet data, `.env` files, or a production database
dump.

See [`SECURITY.md`](SECURITY.md).

## Repository layout

```text
.
├── README.md
├── LICENSE
├── SECURITY.md
├── .gitignore
└── docs/
    └── ARCHITECTURE.md
```

## License

No open-source license is granted. See [`LICENSE`](LICENSE). The repository is
public for review and development, not for reuse or redistribution.

## Related repositories

- [BTCS Core](https://github.com/Silver-Labs-Technology-Development/Silver-Labs-Bitcoin-Silver-Development)
- [BTCS L2](https://github.com/Silver-Labs-Technology-Development/btcs-l2)
- [Silver Labs workspace](https://github.com/orgs/Silver-Labs-Technology-Development/repositories)
