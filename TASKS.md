# Implementation tasks

## Image distribution — 2026-11-11

- [x] Add a no-build application Compose file using external PostgreSQL/Redis.
- [x] Package configuration/docs without source code, runtime secrets or databases.
- [x] Add opt-in Docker Hub publishing, matching image versions and release instructions.
- [x] Add daemon-free Compose/archive checks and a non-demo prebuilt-image CI smoke.
- [x] Run local verification: 70 backend tests passed / 9 infrastructure skips, static checks and deployment-package checks passed.
- [ ] Execute container build and fresh-database image smoke with a working Docker daemon.
- [ ] Verify amd64/arm64 release builds and publish only with owner authorization and actual Docker Hub namespace.

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

## Video documentation — 2026-11-09

- [x] Create one Word document explaining the project and implemented features in detail for a full video.
- [x] Validate DOCX archive/XML integrity and round-trip chapter content. No runtime checks were required for this documentation-only change.

- [x] Illustrate the video document with eight existing screenshots and four explanatory diagrams; verify all twelve are embedded and source aspect ratios are preserved.

- [x] Create a shareable standalone HTML edition; verify twelve embedded images offline, chapter navigation and desktop/mobile layout.

- [x] Apply owner-provided Docker Hub namespace `myselfabii` and regenerate the deployment bundle. Container builds and publication remain pending.

## CI triggers — 2026-11-12

- [x] Configure merge-to-main CI, PR-to-main checks and manual dispatch.
- [x] Validate trigger structure and workflow shell syntax locally.

## Automatic Docker Hub publication — 2026-11-12

- [x] Gate automatic publication on successful integrated-commit CI and merged-PR identity.
- [x] Add reusable multi-platform publication, exact SHA tags, latest promotion and matching archives.
- [x] Validate workflows with actionlint, executable merge/credential/stale-run fixtures, archive tags and Compose checks.
- [x] Configure repository DOCKERHUB_USERNAME secret to the owner-provided myselfabii.
- [x] Confirm both Docker Hub secret names are configured in GitHub Actions.
- [x] Repair browser CI startup readiness after the PR trace exposed an early API health failure.
- [ ] Confirm successful first merged-PR publication and registry availability.

## Closed dependency PR remediation — 2026-11-12

- [x] Inventory all fourteen closed updates and apply them in one tested replacement branch.
- [x] Verify TypeScript 6 without weakening lint and preserve the separate TypeScript 7 deferral.
- [x] Update cryptography locks and verify decryption of ciphertext produced by the old version.
- [x] Patch minimatch audit findings with a scoped override and check clean Node 22 installation.
- [x] Run backend/static/build/browser checks and inspect desktop/mobile screenshots; stop temporary servers.
- [x] Complete hosted PostgreSQL/Redis (79 tests), dashboard (11 browser tests), Docker image builds and both deployment smokes in CI run 43175765228. Updated setup-python executes successfully; registry-publishing actions remain gated until merge.
