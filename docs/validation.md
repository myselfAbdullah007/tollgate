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

## Video document — 2026-11-09

Documentation-only artifact: `docs/Tollgate-Complete-Video-Description.docx`. Generated with Pandoc from a temporary Markdown source. ZIP integrity, all packaged XML parsing, Pandoc DOCX-to-text conversion and representative chapter-presence checks passed. Feature descriptions were checked against current repository documents, gateway schemas/routes/pipeline, account security and dashboard components. Word rendering was not visually inspected. Application tests/build/browser checks were not rerun because application behavior and layout did not change. No paid calls, benchmarks, external delivery or deployment occurred.

### Illustrated video document — 2026-11-09

Added eight historical demo screenshots and four explanatory diagrams. Inspected screenshot and diagram contact sheets. Preserved source aspect ratios and bounded embedded sizes for document pages. DOCX archive/XML parsing, 12 embedded media objects, 12 drawing placements, and Pandoc round-trip caption/content checks passed. Word pagination was not visually rendered. No application changes, new screenshots, runtime tests or provider calls.

### Standalone HTML edition — 2026-11-09

Generated HTML from the illustrated Markdown with Pandoc standalone/embed-resources and inline responsive/print styles. Playwright initially could not find its expected bundled browser; reran successfully using installed `/opt/google/chrome/chrome`. Offline checks at 1440×1000 and 390×844 passed: all twelve images use data URLs and decode, 28 chapter links, working chapter navigation, zero HTTP(S) requests, and no horizontal document overflow. Inspected top/figure screenshots for both viewports. Output: 2,227,241 bytes. Application suites were not rerun; application source and runtime configuration were unchanged.

## Pull-only image distribution — 2026-11-11

- `make distribution-check`: passed Compose rendering and assertions for four pull-only application roles, shared backend image, external-store settings, migration ordering, worker heartbeat health, optional dashboard, loopback defaults, and rejection of each of seven missing required settings. No Docker daemon is needed for these checks.
- `make distribution-bundle`: created `dist/tollgate-deployment.tar.gz`. Archive checks passed: exact allowlist (Compose, blank-secret environment example, README, license), custom namespace/version substitution, and invalid namespace/version rejection. No populated `.env`, application source, databases or generated credentials are included.
- Ruff for the three new scripts and Python compilation: passed. Workflow YAML parsing, Bash syntax for all workflow command blocks and `git diff --check`: passed. These are local structural checks, not a completed GitHub Actions run or actionlint verification.
- `make check`: passed Ruff, mypy (22 source files), ESLint and TypeScript. No application UI or gateway request behavior changed; no new browser interaction/layout verification or optimized dashboard build was required.
- Container build, Redis/PostgreSQL integration and new prebuilt-image smoke: not run locally. Docker CLI/Compose are installed, but `/var/run/docker.sock` is absent and no working daemon was available. This is an unavailable check, not a pass. No daemon/service was started, stopped or reconfigured.
- Added CI smoke for a fresh non-demo database using prebuilt local images, external CI stores and dashboard proxy; it checks key creation, mock fallback, streaming restoration, worker ledger delivery and metadata-only logs. This new CI path has not been executed here. The Docker Hub multi-platform build/publish workflow has not been dispatched; amd64/arm64 builds, signatures, registry visibility and publication remain unverified.
- No paid provider calls, external webhook delivery, image push, GitHub push or public deployment occurred. Docker Hub namespace remains a placeholder unless subsequently supplied.

Final local backend result: `make test` completed with **70 passed, 9 infrastructure skips in 183.92 seconds**. No infrastructure skip is treated as a passing infrastructure check.

### Owner namespace follow-up — 2026-11-11

User selected `myselfabii`. `make distribution-check distribution-bundle`, packaging-script Ruff and archive checks for default owner namespace, custom namespace/version override and blank secrets passed. Bundle now references `myselfabii/tollgate:0.2.0` and `myselfabii/tollgate-dashboard:0.2.0`. This supersedes the placeholder note above; registry existence/availability is not verified, and no image was pushed. Backend suites were not repeated for this packaging-default-only change.

### Branch preparation — 2026-11-11

Created `feat/dockerhub-distribution-and-project-guide` from main matching origin/main. Included the distribution implementation and requested illustrated documents; excluded the unrelated `nano.17345.save` file and ignored deployment build output. Removed generated HTML trailing whitespace and rechecked all 12 image sources remain embedded. Staged whitespace checks passed before commit.

## CI trigger configuration — 2026-11-12

Parsed `.github/workflows/ci.yml` and asserted the exact event set: push limited to main, pull_request targeting main, and workflow_dispatch. Bash syntax checks passed for all existing CI command blocks. Confirmed Docker Hub and GHCR workflows still have manual-only triggers. No application code, UI or schema changed; backend/browser/container suites were not repeated. These local structural checks do not establish a successful hosted CI run.

## Automatic Docker Hub publication — 2026-11-12

Supersedes the earlier manual-only Docker Hub trigger assertion. User explicitly authorized publication on PR merge. Actionlint 1.7.12 passed the CI and Docker Hub workflows with shellcheck disabled; the official downloaded binary archive matched its published checksum. YAML parsing and all workflow Bash syntax checks passed.

Executable local fixtures passed 5 merged-PR identity cases (matching merge, direct push, open PR, other base, other SHA), 5 credential/ref checks (including missing token rejection) and 2 current-main/latest checks. Packaging passed latest, full-SHA and semver archive checks, blank-secret checks and malformed/conflicting argument rejection. `make distribution-check distribution-bundle`, packaging-script Ruff and whitespace checks passed. Application backend/UI behavior did not change, so application suites were not repeated.

DOCKERHUB_USERNAME was configured to myselfabii using GitHub secrets; no token value was received or printed. DOCKERHUB_TOKEN is not configured. No publishing workflow has been dispatched, no images pushed and no multi-platform/runtime success is claimed. Docker info still fails because /var/run/docker.sock is absent. Historical main run 43045734775 had successful gateway/distribution jobs but failed Playwright dependency installation from temporary DNS resolution failures for security.ubuntu.com; compose-smoke was skipped. This is a failed check, not evidence of a browser regression or a passing release gate.

## Browser CI readiness — 2026-11-12

Both DOCKERHUB_USERNAME and DOCKERHUB_TOKEN are present as repository secret names. Values were not accessed and Docker Hub authentication/publication has not been exercised. PR #31 run 43171942237 passed gateway and distribution, then failed the browser beforeAll waiting for Use demo credentials. Downloaded trace shows GET /api/healthz returned 500; login renders the demo button only after this health response. CI had waited only for the frontend login HTML, allowing a gateway startup race.

Updated CI to require gateway /readyz and dashboard /api/healthz before starting Playwright, with bounded curl timeouts and an explicit failure/log path. Actionlint and three executable mocked wait-loop scenarios passed: delayed startup succeeds after both endpoints respond; persistent API or proxy failures terminate rather than starting tests. No frontend/request code changed. This local validation is not a passing hosted browser run; the updated PR workflow must run.

## Dependency remediation — 2026-11-12

Applied fourteen closed Dependabot proposals in a consolidated branch; inventory and upstream source links are in docs/pr-review-2026-11-12.md. Installed pinned Python development requirements and rebuilt editable metadata in isolated .venv (Python3.14.4). Pip check passes. Verified cryptography50.0.2 decrypts a synthetic credential encrypted with48.0.1; Python3.12-compatible Linux wheel download passes (not a Python3.12 runtime test).

Under official-checksum-verified Node22.22.2, npm lock reconciliation and ordinary clean npm ci pass. Next-documented ESLint10 plugin peer warnings are retained; no force or legacy-peer-deps bypass. Initial audit reported10 moderate entries propagated from minimatch10.2.6. Scoped override to11.0.8 for10.x users leaves3.1.5 users intact; final npm audit reports0 vulnerabilities at execution.

`make test`: **70 passed,9 infrastructure skips in114.21s**. `make check`: Ruff,mypy(22 files),ESLint10.14 and TypeScript6.0.3 pass. Separate optimized production build passes. Browser suite passes **11/11 in43.2s** through Next CLI and **11/11 in39.9s** against the standalone production server, using installed Google Chrome with Playwright1.65.0. No app logic changes or weakened checks. Generated next-env.d.ts was restored to avoid committing build output.

Captured/inspected desktop1440×900 overview/providers and mobile390×844 overview images in docs/audits/2026-11-12-dependencies. Icons rendered; mobile document has no horizontal overflow. Ports3188/8188 were available before binding and used only by temporary Tollgate children, backed by isolated /tmp SQLite, demo mocks and empty external keys. Both children were stopped and ports verified released.

All updated workflow inputs were compared with the four official action manifests; supported inputs and Node24 runtimes confirmed. Actionlint1.7.12 with shellcheck disabled passes all three workflows. Distribution checks and archive packaging pass. Docker socket remains unavailable; no local real PostgreSQL/Redis integration or container build/smoke is claimed. Hosted CI must supply those checks. No real provider calls, external webhook delivery, image publication or production deployment occurred.

### Hosted dependency verification

[CI run 43175765228](https://github.com/myselfAbdullah007/tollgate/actions/runs/43175765228) passed on dependency code commit `5a4f986`: gateway **79 passed in 80.48s** with PostgreSQL/Redis on Python 3.12; dashboard **11 browser tests passed in 30.8s**, clean install/lint/types/build passed; distribution passed; Docker builds and full-stack/image-only smokes passed. The image-only deployment used a fresh non-demo database and dashboard proxy, verifying key creation, mock fallback/stream restoration and durable metadata-only worker accounting. Source PR publication gates were skipped as intended. No registry publication or production deployment occurred. The following commit only records this evidence.


## Market-readiness hardening — 2026-11-13

Audit findings were converted into regressions before implementation: all nine
initial cases failed on the original code. After correction, nine passed in
48.18 s. Coverage includes unsupported options, pre-stream and non-stream timeout,
timeout then fallback success, cancellation, confirmed rejections and cache outage.
Four rollup/snapshot-ordering/backlog tests passed in 12.69 s. Expanded readiness
suite (15 tests) passed in 69.97 s, including summed admission, failed stream cleanup,
invalid partial usage, SSE usage flags, metrics and production configuration.

First full backend run: `make test` **92 passed / 10 infrastructure skips in
252.94 s**. `make check` passed Ruff, mypy (24 files), ESLint and TypeScript.
Optimized production build passed separately. Browser suite against that build
via Next CLI: **11 passed in 44.0 s**. The CLI emitted its standalone-output warning;
a separate standalone-server verification is recorded below. No layout changes
were made, so no new screenshot/layout inspection is claimed.

`PYTEST_ADDOPTS=-x make integration` was attempted against Tollgate ports and
**failed**, stopping after **16 passes / 1 failure in 73.20 s** when the first Redis
case could not connect to localhost:63987. Docker's socket is absent. PostgreSQL,
real Redis delivery/retention, container builds/smoke and restore rehearsals are not
verified for these changes. This is a release blocker, not a passing skipped gate.

Prometheus rules/config and observability overlay YAML parsed successfully;
promtool and actual Prometheus/Alertmanager execution are not verified. The
production preflight CLI was exercised with synthetic unsafe settings: exit 1,
expected failed gates, and no password value in output. It makes no network calls.

Browser services used temporary SQLite storage and ports 3188/8188, mock routing,
and empty external provider credentials. No paid providers, outbound webhooks,
production deployment, registry publication or unrelated services were used.
Generated next-env.d.ts was restored; the pre-existing nano save file was untouched.


Standalone production browser verification: **11 passed in 38.9 s**, using the
built standalone server with its static assets copied into the generated output.
Both temporary servers were stopped, their temporary database directory removed,
and ports3188/8188 verified free. No screenshot/layout changes or provider calls.


Final backend gate after the accounting metadata/cleanup refinements: `make test`
**94 passed / 10 infrastructure skips in 289.21 s**. `make check` passed again
(Ruff, mypy24 modules, ESLint and TypeScript). `git diff --check` passed; new local
Markdown links resolve. The infrastructure failure above remains unresolved and
must pass before deployment; mock snapshot tests do not substitute for it.


## Real infrastructure follow-up — 2026-11-13

Docker became available before this follow-up; no daemon or unrelated service was
started/stopped. Existing Tollgate PostgreSQL16.13 and Redis7.4.8 containers were
healthy. `make integration` first passed **104 tests in208.70s**, with no skips.
Added three real-store regressions: commit/deletion during PostgreSQL repeatable-read
snapshot, commit-before-ack crash-window recovery, and uncertain-attempt plus
successful fallback settlement. Final `make integration`: **107 passed in285.40s**,
no skips. `make check` passed (Ruff, mypy24 modules, ESLint, TypeScript).

Built backend Python3.12 and dashboard Node22 images locally from current source,
using distinct `readiness-validation` tags. Both Docker builds passed, including
the separate dashboard optimized build. npm retained the documented ESLint peer
warnings; no force/legacy dependency flags were used.

Created temporary Compose configurations derived from repository deployment files
with `validation-*` service names, a dedicated `tollgate_validation` network and
fresh validation volumes, under project `tollgate`. Only ports3188/8188 were bound;
original application/store services were untouched. Full-stack `up --wait` passed,
including worker heartbeat. Mock-only Compose smoke passed streaming restoration,
forced fallback, explicit usage events, cost metadata and durable metadata-only
ledger delivery. Smoke now accepts `TOLLGATE_SMOKE_URL` for isolated ports.

Worker outage/restart probe: stopped only validation-worker, completed a mock
request, verified its event remained in Redis and absent from SQL, restarted the
worker, and verified exactly one ledger event, deleted committed delivery and
unchanged settled cost. This is an outage/restart check, not a backup/restore or
power-loss durability certification.

Prometheus3.2.1 `promtool check rules` passed all6 alert rules; `check config` passed
with the mounted rule file. No external alert delivery was configured or attempted.

First container browser run: **10 passed /1 failed in47.4s**. Trace showed two
successful customer PATCHes followed by a keys GET500; dashboard logs reported an
upstream ECONNRESET. The editor incorrectly kept a failed-save dialog open. Two
focused regressions both failed against that image. The fix preserves successful
mutation results and shows a separate refresh warning, while actual write failures
remain form errors; non-JSON errors now have a readable HTTP status. No automatic
write retry was added. Corrected verification is recorded below.


Corrected dashboard image rebuilt successfully. Full production container browser
suite: **13 passed in46.3s**, including both regressions that previously failed.
Static checks passed again. No layout/style changes were made; browser checks
include the existing mobile navigation and sidebar visibility assertions.

Validated local image IDs (not registry publication): backend
`sha256:6a1d0cb93e81ffad1a4f97e2f3d605cdf23e2b9a69a54209db3ea51f7691995c`,
dashboard
`sha256:ba8a153ea0034be593f5c85a0fc5fc96916f0b9e71e48f56f5fbc6c2251945cb`.


Fresh non-demo pull-only verification also passed using the newly built images,
a separate `tollgate_image_validation` database and Redis DB1 in the isolated
validation stores. The configuration was derived from deploy/compose.images.yml
with only validation service/network names, loopback ports and explicit synthetic
credentials changed. `up --wait` passed; distribution_smoke.py passed dashboard
proxy, key creation, mock fallback/stream restoration and durable metadata-only
ledger delivery. This verifies local image consumption, not Docker Hub publication,
arm64 runtime, production credentials or a real model provider.

Cleanup completed: temporary validation containers, network and volumes removed; ports3188/8188 released. All pre-existing container IDs and states matched the baseline, and original Tollgate services remain healthy. Existing application images/services were not redeployed.


## Detailed testing — 2026-11-13

Expanded by 51 collected cases. Four defects reproduced in eight initial failing
cases: malformed tool selection/description, non-443 webhook acceptance, disabled
account session issuance, and missing recovery fence on an already-committed
event. Fixed with regressions; ADR 0015 records the decisions.

Final make test: 141 passed/17 infrastructure skips (224.08s). make integration:
158 passed/no skips (275.73s). make check, separate production build and distribution
configuration check passed. Container Playwright: 13 passed (44.1s). Visual audit:
11 views, no measured contrast failures/document overflow; desktop and mobile
screenshots inspected. Coverage: 83.6% statements, 67.9% branches; CLI subprocesses
not included. Production npm audit and Python runtime-lock pip-audit reported no
known vulnerabilities, not a security certification.

440 mock requests passed (200 burst at concurrency20, 240 at 2rps over120s), all
durably logged; observed p50/p95/p99 196.85/660.64/830.63ms. Worker interruption
retained and delivered a pending event once. PostgreSQL/Redis outages returned
readiness503 then200 after store restart. The disposable restart:no worker exited
on Redis disconnect; production supervision behavior was not tested here.
Quiesced SQL+RDB restore into isolated targets preserved442 records,1491096
micro-USD, one pending delivery and123 micro-USD active reservation. Snapshot1.072s,
restore/verify4.108s excludes provisioning/operator response and is not an RTO.

Failed setup/tooling attempts are documented: browser startup connection refusal,
dialect typing check, Decimal report serialization and mutable report counters.
All were corrected and relevant checks repeated. Temporary test services, volumes,
network and backup files removed; pre-existing container IDs/states unchanged,
ports3188/8188 released. Existing deployed application remains unchanged.

See [detailed report](audits/2026-11-13-detailed-testing/REPORT.md) for logs,
coverage, screenshots, dependency reports, load/restore results and reproduction.
Remaining: representative long soak/capacity, live providers/prices, intended
production backup/secret recovery, independent security/privacy/accessibility
review, runtime alerts/paging and commercial pilot evidence. Simultaneous loss of
both accounting stores remains a surfaced manual reconciliation incident.
