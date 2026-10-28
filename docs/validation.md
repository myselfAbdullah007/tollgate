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
