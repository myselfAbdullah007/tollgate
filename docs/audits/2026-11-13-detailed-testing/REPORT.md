# Detailed validation — 2026-11-13

The expanded suite passes after fixing four defects reproduced by eight failing
boundary cases. This is broad automated and operational testing of the current
working tree, not proof of all possible behavior or approval for paid traffic.
The existing deployed application was not updated.

## Results

| Check | Actual result |
|---|---|
| Backend, local stores (`make test`) | 141 passed, 17 infrastructure skips; 224.08 seconds |
| Backend, PostgreSQL/Redis (`make integration`) | **158 passed, no skips**; 275.73 seconds |
| New cases in this campaign | 51 additional collected cases, including 45 boundary cases |
| Static checks (`make check`) | Ruff, mypy (24 modules), ESLint, TypeScript passed |
| Dashboard production build | Passed separately from lint/typecheck |
| Production-container Playwright | **13 passed**, 44.1 seconds |
| UI measurements | 11 views, zero document overflow, zero measured text-contrast failures, sign-out visible throughout |
| Visual inspection | Desktop 1440×900, mobile 390×844 drawer and full overview inspected |
| Distribution configuration | `make distribution-check` passed |
| Frontend production dependency audit | `npm audit --omit=dev`: zero known vulnerabilities reported |
| Python runtime lock audit | pip-audit 2.10.1: zero known vulnerabilities reported |
| Cleanup | Temporary containers/network/volumes/backups removed; ports 3188/8188 free; all pre-existing container IDs/states unchanged |

Coverage measured by pytest-cov 7.1.0 / coverage 7.17.3 during the real-store suite:
**83.6% statements (1,724/2,063), 67.9% branches (470/692)**; combined reporting
metric 79.6%. This does not include subprocess/container execution. CLI coverage
is 0% in this measurement despite separate container startup/build/smoke evidence.
Main API, maintenance and repository branches still have notable gaps. Coverage
is a diagnostic, not a correctness or security score. See coverage.json.

## What was exercised

| Area | Scenarios and evidence |
|---|---|
| API contracts | Unsupported options, malformed messages/tools, invalid numeric limits and stream options; valid tool choices remain accepted |
| Authentication | Every registered administrative route rejects unauthenticated requests; disabled/expired sessions, login throttling, hashed session storage, HttpOnly/SameSite cookie assertions |
| Authorization and CSRF | Viewer mutation matrix, restricted user management, disallowed origins and missing/invalid admin header; deployment-wide roles remain intentional |
| Budget and rate races | Existing 300-request admission check; 50 concurrent settlement retries charge once; 200 rate attempts respect both scopes; memory and Redis implementations |
| Provider behavior | Mock/respx adapter tests, known rejection vs uncertain timeout, cancellation, missing usage, fallback-chain reservation, fallback success, cleanup errors, no fallback after stream output |
| Privacy and streaming | Detector fixtures, request-local restoration, tools, cache isolation, split placeholders; 300 generated Unicode/chunking examples in the new property test |
| Webhooks | HTTPS/public destination policy, port 443, mixed public/private DNS rejection, redirect refusal, five-attempt retry ceiling, invalid legacy destination revalidation |
| Accounting and recovery | SQL partitions/rollups, idempotent replay, commit-before-ack, concurrent snapshot/deletion, pending retention, duplicate recovery fences, expired reconciliation lease, reservation preservation |
| Total settlement-storage failure | Response behavior, critical diagnostic and accounting-failure metric asserted without logging prompt contents; manual reconciliation still required |
| Dashboard | Navigation, search/edit, once-shown key and revocation, playground restoration, plan round trip, workspace switching, dates, insights/settings, save/refresh race and readable write failures |
| Operations | Mock burst/soak, worker interruption, PostgreSQL/Redis readiness during outages, coordinated backup and fresh-target restore |

## Defects found and fixed

1. Invalid tool descriptions and selections reached accepted request models.
   Reject malformed descriptions, unsupported selection strings, and named choices
   that do not refer to supplied tools before provider dispatch.
2. Webhooks accepted non-443 HTTPS destinations despite the documented policy.
   Validate both saved configurations and previously stored destinations at delivery.
3. Disabled users could obtain new sessions which subsequent requests rejected.
   Reject their login before session creation.
4. Recovery retries of an already-committed event failed to create a recovery fence.
   Idempotently upsert the marker for existing as well as newly inserted events,
   without duplicating ledger charges or rollups.

Initial focused run: 8 failed / 30 passed. Corrected, expanded boundary file:
45 passed. The full 158-case real-store suite includes these fixes. See ADR 0015.

## Bounded load and outages

Only synthetic requests and the built-in mock provider were used. External
provider keys were empty. The dedicated customer used a high-budget/high-RPM plan
and an alias with mock outage/backup targets. A quarter of requests streamed;
a quarter used temperature zero with distinct requests (not a cache-hit benchmark).

- Burst: 200 requests, concurrency 20, **4.598 seconds**.
- Paced soak: 240 requests at target 2 requests/second, **120.001 seconds**.
- All 440 returned HTTP 200 and restored the synthetic email correctly; all
  streamed responses completed. All 440 reached the durable ledger.
- Combined observed request latency: p50 **196.85 ms**, p95 **660.64 ms**,
  p99 **830.63 ms**. Other local test work ran concurrently.
- Two further requests exercised stopped-worker delivery and backup pending work.
  Worker interruption retained one event, then restart delivered it once, leaving
  441 load-customer ledger rows and an empty stream.
- PostgreSQL stop and Redis stop each made `/readyz` return 503; each store restart
  restored gateway readiness to 200. Source Redis used AOF with fsync always.
- The disposable configuration deliberately uses `restart: no`. Its worker exited
  when Redis disconnected; deployed Compose uses `restart: unless-stopped`.
  The outage test establishes gateway/store readiness and recovery data behavior,
  not an automatic worker-restart-policy test or power-loss durability proof.

These results are not production throughput estimates or an SLO. They do not
cover a long soak, representative multi-customer history, saturation, real model
latency, or production hardware/network/storage failure modes.

## Backup/restore rehearsal

Stopped the test worker, completed one additional synthetic request, then stopped
the gateway. Added an active synthetic 123 micro-USD reservation. With writes
quiesced, captured a PostgreSQL custom-format dump and Redis RDB snapshot. Restored
into a fresh database and a fresh Redis volume/container; source stores were kept
intact. Ran the worker against the restored targets.

- Snapshot: PostgreSQL **50,026 bytes**, Redis **63,360 bytes**.
- Coordinated snapshot commands: **1.072 seconds**.
- Restore and verification commands after creating the target DB/removing the prior
  disposable restore container: **4.108 seconds**. This excludes outage detection,
  provisioning and operator response, so is not a production RTO.
- Restored ledger: **442 records**, **1,491,096 micro-USD**, matching Redis spend.
- One pending event delivered and removed; the active **123 micro-USD** reservation
  remained intact.

This verifies a quiesced small-fixture SQL + RDB restore, not online backups,
point-in-time recovery, off-site backups, encryption/secret recovery, or an AOF
backup/restore. Temporary backup files were deleted after validation.

## Failed setup/tooling attempts retained honestly

- First browser attempt: 2 failures / 11 not run due to connection refusal. The
  initial Compose startup overlapped recreation of the newly built backend,
  preventing dashboard startup. Explicitly started the dashboard, waited for
  health, then reran: 13 passed. The first UI capture also failed for this reason;
  the corrected capture completed all 11 measurements.
- Initial static check rejected a dialect-specific insert type assignment. Corrected
  the PostgreSQL/SQLite union annotation; the complete static check passed.
- First backup verifier completed its assertions but could not JSON-serialize
  PostgreSQL's Decimal SUM result. A diagnostic retry encountered the already
  delivered event. Repeated restoration into fresh targets reproduced the reporting
  error; converting the exact integer aggregate to int fixed it. Fresh restore and
  verification then passed. No application accounting value was rounded or changed.
- The exercise report originally referenced a mutable status dictionary that grew
  to 442 after its two follow-up requests. The script now snapshots the load counters;
  the saved report separates 440 load requests from the two operational requests.

## Reproduction and artifacts

The unit/integration regressions live in apps/gateway/tests. Standard commands are
`make test`, `make check`, `make integration`, `npm run build --prefix apps/dashboard`
and the dashboard Playwright script. Infrastructure tests use Tollgate stores and
isolated test databases/Redis DB 15; do not target other projects' stores.

`compose.fixture.yml` is a synthetic, disposable fixture using only validation
services, separate volumes/network and local readiness-validation image tags.
Build the backend image from the current tree and dashboard image before use.
Copy the fixture into a fresh temporary directory as `compose.yml`, ensure ports
3188/8188 are free, then start it with `docker compose -f ... up -d --wait`.
Run `.venv/bin/python scripts/detailed_container_validation.py --work-dir <directory>
--output-dir <results-directory>`. The helper requires fresh fixture records;
run once per fresh stack. It leaves the gateway/worker stopped and restore targets
available for inspection. Remove only those validation services and named validation
volumes/network afterward; never use project-wide orphan cleanup.

Validated backend image:
`sha256:28a10e2890bf9ef85aa8277f814ad6475c9802e23166573dc87ac251cfc46bb9`.
Dashboard image (unchanged source since its previous successful image build):
`sha256:ba8a153ea0034be593f5c85a0fc5fc96916f0b9e71e48f56f5fbc6c2251945cb`.
Host tests used Python 3.14; backend container uses Python 3.12. Dependency auditing
used a separate temporary virtual environment; coverage tools were installed only
in the project .venv. Dependency locks were not changed.

See backend-local.log, backend-integration.log, static-checks.log, browser.log,
production-build.log, coverage.json, container-exercises.json, ui-measurements.json,
PNG captures, npm-audit.json, python-audit.json and cleanup.json.

## Remaining launch evidence

- Capped live-provider/model/tool/usage/price verification, separately authorized.
- Representative capacity, long-duration soak and cancellation-heavy network load.
- Intended deployment backup automation, retention, off-site/PITR recovery and secret rotation.
- Independent security/privacy review and broader detector evaluation; vulnerability
  databases reporting zero findings do not establish absence of vulnerabilities.
- Browser engines beyond Chromium and a full keyboard/screen-reader accessibility audit.
- Runtime alert firing and external paging delivery.
- Simultaneous storage loss remains a manual reconciliation incident.
- Paid pilot onboarding, support/commercial terms and demonstrated willingness to pay.

No registry publication, existing-application redeployment, paid model call or
unrelated-service modification occurred.
