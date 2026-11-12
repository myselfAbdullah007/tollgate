# Working memory

## Context

User supplied TOLLGATE.odt and asked for a complete, tested project with easy-to-discover UI and all listed project/agent documents. Another project is running and must never be stopped for Tollgate testing.

## Environment and ownership

Repository: `/home/abdullah/Desktop/avin/tollgate`. Python virtualenv: `.venv`. Gateway: 8187. Dashboard: 3187. Tollgate-only PostgreSQL: 55487. Tollgate-only Redis: 63987. Compose project/network prefix: `tollgate`. Existing unrelated containers use 3000, 3002, 5432, 8090, 8787 and others.

## Commands

`make dev` starts only Tollgate API/dashboard children and checks port availability. `make test`, `make check`, `make integration`; `npm run test:e2e --prefix apps/dashboard`; `npm run build --prefix apps/dashboard`. Browser binaries may need `npx playwright install chromium`; optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can point to an existing compatible browser in restricted environments.

## Implementation notes

Shared admin session is deployment-scoped. Tenant selection is not independent tenant identity. Demo password/key are deliberately public and only created in demo mode. Real mode requires a private 12+ character password and valid 32-byte base64 master key.

PostgreSQL has monthly range partitions; SQLite is demo/testing only. Single-process memory mode is not multi-worker safe. All money uses integer micro-USD. Price config is illustrative and reviewable. Prompts/answers/vaults are not logged. Stream cancellation conservatively accounts for provider work. Reconciliation pauses admission/settlement briefly, includes unledgered stream events, and preserves in-flight reservations.

## Verification

Actual commands, dates and results are maintained in docs/validation.md. Never infer that optional or public deployment work has happened from a scaffolded workflow. Never reset another project's services to clear a port.

## Current running setup

The full Tollgate Compose stack is running on the ports above. Temporary local dev servers were stopped. Backend suite: 49 passing. Browser suite: 5 passing against both development mode and the full Docker stack. Docker verification is recorded in docs/validation.md. Full Compose streaming/fallback/worker smoke passed. Docker Buildx is absent on this host; use the documented `DOCKER_BUILDKIT=0` build fallback.

## Review on 2026-10-28

Baseline commit `172ac2a` was pushed to origin/main with the configured author/committer identity. IMPROVEMENT_PLAN.md and docs/audits/2026-10-28/REVIEW.md are the current prioritized backlog/evidence. The application was audited without implementing the planned changes.

Confirmed release concerns: loss of extra privacy categories/thresholds in plan editor; stale settings after workspace switching; sidebar sign-out below the viewport without internal scroll; low text contrast; PII scanning routing aliases; null tool-call 500; Anthropic system-text-part translation; generic preview versus real policy; ineffective log dates; plan-derived tier labels presented as actual service.

Retest: make test 43 passed/6 expected skips, make integration 49 passed, static checks/build passed, five Docker browser tests passed. A controlled mock deployment probe passed fallback/stream/degradation/worker checks. The old timestamp-alias Compose smoke returned 422 during review, reproduced as routing-identifier redaction. Main GitHub CI for 172ac2a failed during PostgreSQL service health-command parsing; do not report it as green or confuse Dependabot success runs with CI.

Do not silently weaken existing policies to simplify a form. Treat proposed fixes/acceptance tests as pending until implemented and validated. No paid provider verification or unrelated-service changes occurred in this review.

## 0.2 implementation — 2026-10-28

The latest section supersedes the review-only/current-running baseline above. F01–F13 are implemented with regressions. New source modules cover pricing, ingress bounds, account security, notifications and maintenance; UI shared/editor/business components and a single foreground token file keep future changes reviewable. Environment labels affect reports only. Roles are deployment-wide. Rate data is illustrative; tests use only mock/recorded transports. Account role editing is owner API only; UI creates accounts and manages self sessions/passwords. Export/validate does not import.

Remaining work: realistic load/soak/SLOs, incremental reconciliation and bounded stream retention, batching, live-provider/model price review, workspace membership and independent project budgets, advanced quality/upgrade/billing integrations. Do not infer these from the presence of reports or roles. See the newest validation section for actual release results.

Current deployed version is 0.2.0 at dashboard 3187 / gateway 8187. Final infrastructure suite: 79 passing; memory suite: 70 passing, 9 infrastructure skips. Corrected production Docker browser suite: 11 passing. `make check`, optimized build and Compose smoke pass. A real production-only overlap race was found during verification, reproduced before correction, and fixed: cancelled superseded reads cannot turn completed writes into save errors. No paid calls or external webhook delivery occurred. Development children on 3188/8188 were stopped; Tollgate and the other project continue on their own ports.

Final release gate: worker heartbeat healthcheck is enabled; full Compose `up --wait` exits 0. GitHub CI run 40682693230 for 2cae69f passed gateway, dashboard and Compose smoke. See docs/validation.md; do not confuse earlier failed verification attempts with this final result.

## Dependency PR work — 2026-10-28

The 14-PR review is tracked in docs/pr-review-2026-10-28.md and ADR 0008. Thirteen compatible PRs are merged into main; PR 13 is closed without merging after clean local and remote TypeScript 7 lint failures. Do not remove lint coverage to force the upgrade. Reconciled npm lock must pass clean Node 22 npm ci; host-only package-lock generation previously missed optional native entries. Live provider tests and image publication are not part of this maintenance task.

PR resolution completed: source 46151a5 passed CI 40685934917 (gateway/dashboard/Compose smoke). Local checks: 79 infrastructure tests, 70 memory tests with 9 expected skips, 11 browser tests, static checks/build and inspected screenshots. Final GitHub open-PR count is zero. Running application containers were not redeployed; temporary 3188/8188 validation services were stopped.

## Video documentation — 2026-11-09

Created `docs/Tollgate-Complete-Video-Description.docx` at the user’s request. Includes narration, screen directions, detailed implemented features, scope boundaries, recording sequence, video description, glossary, and repository sources. DOCX integrity, XML parsing and Pandoc round-trip content checks passed. No application/service changes or new runtime/live-provider verification.

The video document now embeds 12 images: eight existing 2026-10-28 demo captures and four new explanatory diagrams. Editable source is `docs/Tollgate-Complete-Video-Description.md`; diagram assets are in `docs/video-assets/`. ZIP/XML, image-count/placement and round-trip caption checks passed. Image contact sheets were visually inspected; Word pagination was not rendered.

The portable edition is `docs/Tollgate-Complete-Video-Description.html` (~2.23 MB decimal). All twelve images and styles are embedded. Playwright with installed Google Chrome passed offline image loading, zero remote requests, chapter anchor navigation and no horizontal overflow at 1440×1000 and 390×844. Inspected desktop/mobile top and figure screenshots. No application or service changes.

## Pull-only image distribution — 2026-11-11

User requested image-based consumption without source checkout, accepting separate backend/dashboard packaging after discussion. Added `deploy/compose.images.yml` and `deploy/.env.images.example` for externally managed PostgreSQL/Redis, non-demo identities, required configuration, shared backend gateway/worker/migration roles and optional dashboard. Keep the internal `gateway:8187` address: dashboard rewrites remain build-time.

`make distribution-check` validates config without a daemon; `make distribution-bundle` packages Compose, blank-secret example, instructions and license in `dist/tollgate-deployment.tar.gz`. Scripts and workflow structure checks passed; `make check` passed. The manual Docker Hub workflow defaults publish=false and selects an existing reviewed tag that must include packaging. CI now also defines a fresh-database image-only smoke; it has not run here. Docker daemon/socket unavailable, so local image builds, infrastructure smoke, multi-platform release and publication remain pending. No other services or paid providers were touched. Docker Hub namespace was requested asynchronously; keep placeholders until supplied. See ADR 0010 and docs/image-distribution.md.

Final local backend result: `make test` completed with **70 passed, 9 infrastructure skips in 183.92 seconds**. No infrastructure skip is treated as a passing infrastructure check.

Namespace follow-up: user supplied `myselfabii`. This supersedes the placeholder-namespace notes above. Environment examples, packaging default, Docker Hub workflow default and guide now use `myselfabii/tollgate` and `myselfabii/tollgate-dashboard`. Regenerated archive and reran Compose checks, packaging namespace/version override and blank-secret checks, and script Ruff successfully. Providing a namespace did not publish or authorize a registry push; build/runtime/publication checks remain pending.

## CI triggers — 2026-11-12

PR #28 is merged. On fresh branch `ci/run-on-main-merges` from origin/main, changed CI triggers from all pushes/PRs to main pushes, PRs targeting main, and manual dispatch. This covers merge commits, squash merges, rebase merges and direct main pushes without duplicate branch-push runs. Local YAML trigger assertions and workflow Bash syntax checks passed. No application behavior changed, so application suites were not repeated. Registry releases stay manual; asked the user separately whether successful merges should publish Docker Hub images, and no answer has arrived yet.
