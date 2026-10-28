# Validation record

Date: 2026-10-28 (Asia/Karachi). Tests used only local mock/recorded providers; no paid model call was made. Another project's Docker services remained running.

## Verified results

| Check | Actual result |
|---|---|
| Backend unit/property/API and real Redis/PostgreSQL suite | **49 passed**, including the final malformed-input and concurrent full-request rollup cases |
| Atomic budget stress | 300 simultaneous attempts, budget for 100; exactly 100 admitted and settled without overspend, on memory and real Redis |
| Streaming restoration | Hypothesis randomized splits and every single split of a multi-placeholder response pass |
| Privacy | Cache restores current request's values; prompt PII absent from metadata ledger, cache and Redis events in tested flows |
| PostgreSQL | Temporary test database migrated; monthly partitions, daily rollups, replay idempotency and pending-event spend recovery pass |
| Static checks | Ruff, mypy (16 source files), ESLint and strict TypeScript pass |
| Next.js production build | Successful optimized standalone build; final Docker build uses Node 22 |
| Browser workflows | **5 Playwright tests pass against both development and the full Docker stack**: every page, customer budget persistence, once-shown key/revocation, PII preview/stream, mobile navigation/no document overflow |
| Dependency audit | Dashboard npm install/lock generation reports 0 vulnerabilities at execution time |
| Docker images | Gateway Python 3.12 and Next.js Node 22 images built successfully; **full stack healthy and deployment smoke passed** |
| Visual review | Desktop 1440px and mobile 390px screenshots inspected; charts rendered, mobile customer budgets converted to cards |

## Measured local demo latency

Command: `.venv/bin/python examples/load_demo.py` against the local single-process SQLite/memory demo gateway, non-streaming `mock/premium`, temperature 1 (no cache), 64-token ceiling, 40 sequential requests.

Result: **40 successful; p50 35.40 ms; p95 38.12 ms; 0 failures.**

This is end-to-end localhost request latency, including approximately 18 ms of intentional mock-provider delay and local database work. It is not isolated gateway overhead, a throughput benchmark, or a production SLO. The host was running another project concurrently. Do not extrapolate these numbers to paid provider latency or a networked deployment.

## Environment and resolved test issues

Local Python 3.14.4; Docker image Python 3.12.13; Node host 25.2.1 and image 22.22.2; Next.js 16.4.3; PostgreSQL 16; Redis 7. The final lockfile was generated with the container's Node/npm version to avoid an npm 10/11 optional-dependency mismatch.

The sandbox blocked asynchronous SQLite wakeups and Chromium sockets; those commands were rerun with the required execution approval. Next.js's build subprocess also needed unrestricted execution. The default Docker Buildx plugin was missing; the documented legacy builder successfully built the images instead. Browser smoke initially found the localhost/127.0.0.1 origin mismatch; that was corrected without removing CSRF checks. Framework route announcements were excluded from the application error assertion.

## Limits of this verification

No live OpenAI/Anthropic/Gemini credential was provided or used. Provider transports/tools/streaming were verified with recorded-shaped respx fixtures, not with an external paid model. No public hosting, GHCR push, domain reservation, security certification, independent accessibility audit, Presidio, AWS KMS, or optional observability deployment is claimed. Capacity limits and deferred features are recorded in ROADMAP.md and SECURITY.md.

Implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [Next.js deployment](https://nextjs.org/docs/app/getting-started/deploying), [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/), [Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming). Local bundled Next.js deployment/standalone guides were also read when its generated AGENTS.md became available.

## Full Compose smoke

Both images built with Python 3.12 / Node 22. The migration job exited successfully; gateway, dashboard, PostgreSQL and Redis report healthy, and the worker is running. `.venv/bin/python scripts/compose_smoke.py` passed readiness (PostgreSQL + Redis), a forced outage/fallback, streaming restoration, durable worker delivery, and metadata PII exclusion. Services use 3187, 8187, 55487 and 63987. No unrelated project was stopped.

Docker browser rerun: **5 passed in 9.9 seconds**, including every page and persisted writes against PostgreSQL/Redis.

## Deeper review — 2026-10-28

Retested the unchanged application baseline `172ac2a`: `make test` gave 43 passed and 6 expected infrastructure skips; `make integration` gave 49 passed in 22.13 seconds. `make check` and the optimized production build passed. Five browser tests against Docker passed in 12.7 seconds.

The expanded audit found issues outside that passing coverage. The original `scripts/compose_smoke.py` returned 422 during this review because its numeric timestamp alias can trigger prompt PII scanning. An isolated alias reproduction confirmed the defect. A separate controlled deployment probe using alphabetic aliases passed streaming, fallback, Tier 2 degradation, PostgreSQL/Redis readiness and worker delivery. The earlier successful smoke record remains historical evidence, not proof against this intermittent defect.

Remote main CI for 172ac2a [failed](https://github.com/myselfAbdullah007/tollgate/actions/runs/40670735966) while parsing the PostgreSQL service health command, before backend tests. Local checks and Dependabot jobs must not be reported as a successful remote CI run.

Measured readability/sidebar evidence and reproduced policy/state/API gaps are in [the audit report](audits/2026-10-28/REVIEW.md). [IMPROVEMENT_PLAN.md](../IMPROVEMENT_PLAN.md) contains the proposed remedies and acceptance checks. Findings are still open; no application fix is claimed by these observation probes.

## 0.2 implementation validation — 2026-10-28

The historical findings above describe the old baseline. F01–F13 now have implemented fixes; the improvement plan's final status section distinguishes delivered foundations from remaining staging/scale work.

| Check | Actual result |
|---|---|
| `make test` | 70 passed, 9 infrastructure-only skips in 61.73 s |
| `make integration` against Tollgate PostgreSQL/Redis | 79 passed in 69.91 s; no skips |
| `make check` | Ruff, mypy (22 source files), ESLint and TypeScript pass |
| Optimized production build | `npm run build --prefix apps/dashboard` succeeded |
| Expanded browser suite against isolated development ports 3188/8188 | 10 passed in 33.4 s |
| Visual diagnostics | Five viewports (1440×900, 1366×768, 1280×720, 1024×600, 390×844): account/sign-out controls visible, no document horizontal overflow; zero measured direct-text contrast failures on overview and six additional console pages |
| Manual image inspection | Desktop 1280×720 and mobile 390×844 screenshots inspected; readable text and reachable account controls |

Regression coverage includes policy preservation/revisions, workspace state, routing identifiers, optional tool fields, effective preview/date filters, exact pricing, invalid-usage estimates, scoped usage credentials, roles/sessions, metadata audits, transactional notifications/signatures, request limits, concurrent admission, transient accounting failure, recovery fencing, reconciliation drift/reservations and malformed-event quarantine. First 11 targeted defect tests were observed failing on the unchanged baseline before fixes. All provider tests use mock/recorded transports; no paid call was made.

Evidence: [implementation screenshots and measurements](audits/2026-10-28-implementation/ui-measurements.json). Contrast measurements are diagnostics, not an independent WCAG assessment. Playwright used the existing Chromium 1208 executable through `PLAYWRIGHT_CHROMIUM_EXECUTABLE`; the default newly requested browser binary was absent and that failed launch was not counted as a pass.

Docker rebuild/deployment smoke and remote main CI are recorded below. They are not inferred from these local results. Existing monthly demo ledger data is preserved; optional new feature tags default to `general` / `production` in reports for legacy rows. Another project's services have not been stopped or modified.

### Production browser timing correction

CI run [40681148789](https://github.com/myselfAbdullah007/tollgate/actions/runs/40681148789) passed the gateway job but exposed a production browser race: a successful customer PATCH was followed by a read refresh that a delayed search load cancelled. The save dialog incorrectly surfaced the read cancellation as a failed write. The first Docker browser rerun reproduced it (8 passed, 2 failed, the other failure was unfinished intercepted-route teardown). These runs are recorded as failures.

The loader now ignores only its own superseded read cancellation; real errors still propagate. A focused test deliberately overlaps save refresh and search refresh. Browser interception teardown ignores callbacks that finish after test teardown. Documentation and Compose configuration now expose the concurrency setting and current pricing/account/notification procedures.

Corrected full-stack results: both Python 3.12 and Node 22 images built successfully with the legacy Docker builder; the packaged migration completed and gateway/dashboard/PostgreSQL/Redis are healthy, with the worker running. The focused overlapping-read test failed on the previous production image at the expected dialog-close assertion, then passed after correction. The full Docker browser suite passed **11 tests in 28.2 s**. The controlled Compose smoke passed readiness, streaming restoration, forced fallback, durable worker delivery and PII exclusion. Static checks passed again after the UI correction. Only Tollgate gateway/worker/dashboard were replaced; database/Redis volumes and unrelated LMS containers were retained. Temporary 3188/8188 development children were stopped after verification.

### Compose wait health gate

The corrected CI run [40681881074](https://github.com/myselfAbdullah007/tollgate/actions/runs/40681881074) passed gateway and dashboard jobs, then exposed a deployment gate issue: `compose up --wait` rejects a long-running worker with no healthcheck. The prior local `--wait` invocation had the same exit status despite healthy application endpoints; endpoint/smoke/browser results remain valid, but the wait command is not counted as passing. The worker now has a Redis-heartbeat freshness healthcheck rather than a disabled check. This verifies worker progress and lets clean-start deployment gates assess the service directly.

### Final release gate

`docker compose -f deploy/docker-compose.yml up -d --no-build --wait --wait-timeout 180` now exits **0**, including a healthy heartbeat-checked worker. The controlled smoke passes again. GitHub [CI run 40682693230](https://github.com/myselfAbdullah007/tollgate/actions/runs/40682693230) for source commit `2cae69f` completed **successfully**: gateway, dashboard (including all 11 browser tests) and fresh Compose build/start/smoke jobs all passed. This is the actual CI workflow, not a Dependabot result. Subsequent validation-record edits are documentation only.

## Dependency PR validation — 2026-10-28

See [PR review](pr-review-2026-10-28.md) for the 14-PR inventory and TypeScript 7 reproduction. Integrated runtime package minima match existing lock versions. Updated editable gateway build passes with the new setuptools minimum. `make test`: 70 passed / 9 skipped in 56.80 s; `make integration`: 79 passed in 75.74 s; `make check` and production dashboard build pass. Clean Node 22 and host npm ci pass after reconciling the lock; an earlier malformed optional-dependency lock install failed and was corrected. ESLint peer-range warnings remain documented; no force or legacy-peer-deps bypass is used. Browser/visual and remote results are recorded below.

Dependency-batch browser check: 11 passed in 27.9 seconds against the optimized build on 3188/8188. Desktop/mobile screenshots inspected after the icon update; five viewport checks and six additional pages have zero measured direct-text contrast failures and no horizontal document overflow. Evidence: docs/audits/2026-10-28-prs/. Temporary validation servers stopped; running production containers were not replaced.

Final dependency gate: [CI 40685934917](https://github.com/myselfAbdullah007/tollgate/actions/runs/40685934917) for source 46151a5 passed all three jobs: gateway, dashboard and fresh Compose smoke. The exact tested source was fast-forwarded into main. GitHub confirms 13 PRs merged (1–12, 14), compiler PR 13 closed without merging, zero open PRs. Subsequent documentation-only evidence updates do not change the verified dependency set. The manual image-publication workflow was not run; existing application containers and unrelated services were not redeployed.
