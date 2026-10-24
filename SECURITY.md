# Security policy

## Scope

This repository is a **planned development scaffold** for a BTCS L1/L2
explorer and indexer. There is no runnable service, production deployment, or
security review.

## Reporting

Do not open a public issue containing exploit details, credentials, or wallet
data. Report privately to the Silver Labs maintainers through the organization
account <https://github.com/Silver-Labs-Technology-Development>.

## Security boundaries for future work

- The indexer reads from nodes; it never signs or submits transactions.
- Node RPC credentials and database credentials are secrets and must not be
  committed or logged.
- Public API endpoints are read-only, paginated, and rate-limited.
- Reorg handling must reverse derived effects transactionally.
- An indexed result is not proof of final settlement; the UI must say so.

## Known limitations

- No implementation, test suite, or audit exists.
- No reorg, backfill, or load test has been run.
