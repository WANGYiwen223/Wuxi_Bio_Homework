# Storage

Business repositories, transactions, migrations and checkpoints.

Implemented: `repository.py` provides SQLite sources, trusted demo sessions, scoped cases/messages/evidence, audit events, optimistic revisions and durable proposal receipts. Execution services persist actions/approvals/handoffs; workflow uses a separate checkpoint database with interrupted-call reconciliation. See `docs/REPOSITORY_STRUCTURE.md`.
