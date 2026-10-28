# Changelog

## 0.1.0 — 2026-10-28 (unreleased)

- Added customer-aware OpenAI-compatible text gateway and four provider choices, including a key-free mock.
- Added atomic budget reservations, graceful model tiers, quality locks, overage caps, rate limits, fallback and circuit breakers.
- Added reversible PII vaults, checksum detectors, block/mask/off modes and stream-safe restoration.
- Added tenant-scoped exact cache, metadata-only ledger, durable Redis delivery, PostgreSQL partitions, daily rollups and spend recovery.
- Added Alembic migrations and serve/worker/migrate/seed/key commands.
- Added responsive administrator dashboard with guided setup, searchable customers/logs, plans, routing, keys, providers and playground.
- Added isolated Compose deployment, CI, examples, architecture records and tests.
- Fixed demo login origins for both localhost and 127.0.0.1; bundled fonts locally.

No public release, paid-provider verification, or production security audit has been performed.

## Review and improvement plan — 2026-10-28

- Committed and pushed the initial application using the configured repository identity.
- Added a prioritized business-readiness plan, measured UI audit, workflow fixtures, and isolated feature/deployment probes.
- Reconfirmed 49 infrastructure-backed tests, five Docker browser flows, static checks and production build.
- Recorded confirmed sidebar/contrast issues, policy loss on plan save, stale workspace forms, routing-identifier redaction, validation/adapter gaps, ineffective date filtering and misleading tier labels.
- Recorded the initial main CI service-health quoting failure separately from local passing checks.
- Application fixes remain planned; this review does not claim the findings are resolved.
