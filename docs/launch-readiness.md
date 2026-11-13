# Controlled pilot launch gates

Initial recommended scope: a dedicated self-hosted installation for a SaaS team
that wants per-customer AI budgets, conservative cost controls, and reversible
redaction. Workspaces share deployment administrators. Do not offer the existing
console as isolated accounts for unrelated hosted customers.

## Engineering gates

- Run `make test`, `make check`, `make integration`, the dashboard production
  build, and Playwright on the exact release source. A skipped integration test is
  not verification of PostgreSQL/Redis behavior.
- Run `tollgate check-production` with the intended deployment environment. It
  performs offline configuration checks only and prints no secrets. A pass does
  not verify actual HTTPS termination, store connectivity, provider credentials,
  model prices, security, or capacity.
- Review [API compatibility](api-compatibility.md), especially strict request
  validation, optional SSE usage, and summed fallback reservations.
- Real PostgreSQL/Redis replay/retention tests and isolated full-stack container
  smoke passed on2026-11-13; see validation.md for exact evidence. Repeat them for
  the intended release source. Upgrade gateway and worker together during a maintenance window.
  Retain a database backup and Redis AOF backup. Do not roll back to a worker that
  reads SQL before the stream while a newer worker deletes committed events.
- Monitor request latency, uncertain charges, fallback attempts, ledger backlog,
  worker heartbeat, and accounting failures. Prometheus rules are provided;
  external paging/Alertmanager destinations are not configured or verified.
- A small, quiesced SQL+RDB restore and 440-request mock load/soak passed on
  2026-11-13; see the detailed testing report. Repeat backup/restore and secret
  rotation for the intended deployment in an isolated environment. Record
  recovery time, any missing events, and preserved reservations. Backup instructions
  alone are not proof of recoverability.
- Run load/soak tests with representative customer counts, ledger history, streaming
  concurrency, cancellations, provider failures and worker outages. Define capacity
  and SLOs from results; the historical sequential mock benchmark is insufficient.
- Obtain separate authorization for capped live-provider checks. Record model IDs,
  reviewed prices, tool/stream compatibility and invoice discrepancies. Automated
  tests must continue using only mocks/fixtures.
- Arrange an independent security/privacy review, a private disclosure contact,
  and verified detector coverage. Do not claim comprehensive PII protection.
- Verify published image digests and a clean install/upgrade before advertising
  registry installation. Local workflow files do not establish publication.

## Pilot evidence to collect

Recruit 3–5 design partners only through owner-approved outreach. Agree on one
feature and a bounded workload per partner. Record integration time, unsupported
options encountered, cost discrepancies, savings, degradation task acceptance,
incidents, and willingness to pay. Store synthetic evaluation data or customer-
approved anonymized examples; do not add prompt content to gateway logs.

Define the commercial offer and support owner before accepting paid traffic:
installation/support scope, response expectations, pricing, payment process, and
upgrade/overage consent. Manual onboarding and billing can serve a pilot; no
payment integration, contract, customer acquisition or willingness to pay is
established by this repository.

Workspace memberships, independent environment budgets, production billing sync,
automatic invoice corrections, and fully automated backup/restore remain deferred.
See the newest section of [validation](validation.md) for actual verification.
