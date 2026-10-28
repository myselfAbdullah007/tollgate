# Implementation tasks

- [x] Read supplied ODT and map its feature requirements.
- [x] Inspect running services; allocate separate Tollgate ports/network/volumes.
- [x] Scaffold Python gateway, CLI, Next.js dashboard, configuration and examples.
- [x] Implement sessions, password hashing, CSRF checks, API keys and encrypted credentials.
- [x] Implement customers, plans, aliases, per-customer budget and rate admission.
- [x] Implement Redis Lua reservations, fallback, breaker, cache and settlement.
- [x] Implement PII detectors, vault, stream restorer and privacy modes.
- [x] Implement mock/OpenAI/Anthropic/Gemini adapters and fixtures.
- [x] Implement PostgreSQL monthly ledger, daily rollups, Alembic, worker replay and reconciliation.
- [x] Build all dashboard pages and persisted editing flows.
- [x] Implement mobile navigation, keyboard focus and guided setup.
- [x] Run backend unit/property/API and real PostgreSQL/Redis tests.
- [x] Build and type-check dashboard; exercise browser workflows.
- [x] Create user-requested documentation and architecture records.
- [x] Complete final validation record, deployment smoke test, and measured local benchmark.

Public release, external accounts, live provider verification, optional integrations and security review are tracked in ROADMAP.md, not silently treated as completed.

## Review follow-up backlog — 2026-10-28

- [x] Commit and push baseline using the repository owner's configured identity.
- [x] Retest current gateway, integration, dashboard and production build.
- [x] Measure contrast and sidebar reachability at desktop/mobile viewports.
- [x] Probe policy round trips, workspace state, effective preview, date filtering and tier truthfulness.
- [x] Write IMPROVEMENT_PLAN.md with priorities, business needs, phases and acceptance checks.
- [x] Phase 0: repair main CI quoting and add deterministic/regression fixtures.
- [x] Phase 1: preserve policies/workspace state; fix sidebar and text readability.
- [x] Phase 2: correct metadata redaction, optional/tool translation, preview, date filtering and operational labels.
- [x] Implement Phase 3 foundations: pricing precision, accounting/recovery, concurrency and account/session administration.
- [ ] Complete independent staging/security/capacity review before paid-traffic readiness.
- [x] Phase 4: deliver feature/customer cost reporting, usage endpoints and signed alerts.
- [ ] Phase 5: expand scale/team/integrations only after the earlier release gates pass.

Detailed findings and estimates are in IMPROVEMENT_PLAN.md. Open items are deliberately not marked complete merely because current smoke tests pass.

## Dependency PR resolution — 2026-10-28

- [x] Review all 14 open dependency PRs and reproduce the TypeScript 7 blocker.
- [x] Integrate the 13 compatible PR heads and reconcile manifests/lockfile without losing mainline fixes.
- [x] Verify clean Node 22 install, gateway tests, infrastructure tests, static checks and production build.
- [x] Finish browser/visual and remote CI gates, merge 13 compatible PRs, close incompatible PR 13 and verify zero open PRs.
