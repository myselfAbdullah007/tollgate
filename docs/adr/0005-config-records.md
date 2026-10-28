# ADR 0005: Typed configuration records and explicit ledger tables

Status: accepted, 2026-10-28.

Most administrative entities are small named tenant configurations. Store these in a record table with an enforced `(kind, tenant_id, name)` identity, typed Pydantic input schemas and API referential checks. Keep accounting in explicit relational log/rollup tables with BIGINT money, composite identity, monthly partitions and indexes.

Consequences: fewer repetitive repositories and easier schema evolution for plan/router rules. Configuration relationships are validated by the API rather than relational foreign keys; maintenance code must use the same checks. This intentionally differs from the brief's suggested one-table-per-entity layout and is unsuitable as an excuse to bypass tenant scoping or typed validation.
