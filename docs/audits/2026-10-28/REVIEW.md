# Functional, UI and business review

Date: 2026-10-28. Baseline commit: 172ac2a. Full proposed backlog: [IMPROVEMENT_PLAN.md](../../../IMPROVEMENT_PLAN.md).

## Scope and execution

Reviewed the gateway, admin API, accounting/worker, provider adapters, dashboard and CI. Ran the existing suites and added separate observation probes. Production application behavior was not changed by this review. Browser policy/workspace tests used intercepted fixture responses, so no actual privacy rules or workspace settings were weakened. Temporary API probes used an isolated SQLite app; deployment checks used only the built-in mock provider. No unrelated service was stopped.

The current implementation was committed and pushed using the repository's configured Git name/email. No additional author trailer was added.

## Test results

| Command/check | Result |
|---|---|
| `make test` | 43 passed, 6 skipped; infrastructure tests need DSNs |
| `make integration` | 49 passed, 22.13 s |
| `make check` | Ruff, mypy, ESLint, TypeScript passed |
| `npm run build --prefix apps/dashboard` | Passed |
| Existing Playwright suite | 5 passed, 12.7 s against Docker |
| `scripts/audit_deployment.py` | Passed PostgreSQL/Redis readiness, forced fallback, stream restoration, Tier 2 degradation and worker ledger delivery |
| Existing `scripts/compose_smoke.py` on this review run | Failed with 422; a numeric routing alias can be scanned as CARD. Prior successful runs do not remove this flakiness |
| GitHub CI for main 172ac2a | Failed before backend tests during PostgreSQL service setup; downstream Compose job skipped |

CI evidence: [run 40670735966](https://github.com/myselfAbdullah007/tollgate/actions/runs/40670735966). The relevant error is `unknown shorthand flag: 'U' in -U`, caused by how the runner tokenizes the single-quoted `--health-cmd` service option. Dependabot success runs are separate from the failed application CI and are not counted as evidence of a green build.

## UI evidence

At 1440×900, 1366×768, 1280×720 and 1024×600, the sign-out control ends at **940.5 px**. Sidebar scrollHeight is about **958 px**, but overflow-y is **visible**, so it has no internal scrolling mechanism. At 1280×720, the user cannot reach the lower sidebar by scrolling the document normally. In the open 390×844 mobile drawer, sign-out ends at **934.5 px**.

Screenshots: [1280×720](overview-1280x720.png), [1366×768](overview-1366x768.png), [1440×900](overview-1440x900.png), [1024×600](overview-1024x600.png), [390×844](overview-390x844.png), [open mobile drawer](mobile-sidebar-open.png), [playground](playground.png), [plans](plans.png), [providers](providers.png), [customers](customers.png), [settings](settings.png).

The direct-text contrast scan found 136 candidate instances below the selected threshold in the desktop overview DOM. This is a diagnostic count, not a count of unique WCAG violations: it includes repeated/decorative/off-screen text, and gradient/opacity/complex rendering needs manual verification. It excludes the logo but is not a full accessibility engine. Representative operational values measured against their computed backgrounds:

| Text | Ratio | Current size | Target for this size |
|---|---:|---:|---:|
| “87%” budget use | 2.40:1 | 10 px | 4.5:1 |
| CUSTOMER heading | 3.43:1 | 9 px | 4.5:1 |
| View all customers | 3.93:1 | 11 px | 4.5:1 |
| Within your plan budgets | 3.17:1 | 10 px | 4.5:1 |
| Explore requests | 3.22:1 | 10 px | 4.5:1 |
| mock/premium / customer ID | 4.29:1 | 10 px | 4.5:1 |

Reference: [W3C minimum contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum). No full accessibility certification is claimed.

## Reproduced feature and workflow findings

| Finding | Observation | Code location |
|---|---|---|
| Plan save loses policy | Fixture CARD/EMAIL/SECRET becomes CARD; three steps become two | `apps/dashboard/src/components/dashboard.tsx`, Editor initialization/submission |
| Wrong workspace form | Select “Audit second workspace”; name input stays “Acme workspace” | Same file, SettingsView state and workspace switch |
| Routing metadata treated as PII | Alias `audit-4111111111111111` creates with 200; prompt “Hello” is blocked with 422 CARD | `apps/gateway/src/tollgate/pipeline.py`, whole-request vault transform |
| Nullable tool calls | `tool_calls: null` returns 500 | `apps/gateway/src/tollgate/schemas.py`, message validator |
| Anthropic system text parts | Accepted by ChatRequest, then TypeError in translator | `apps/gateway/src/tollgate/providers.py`, system join |
| Preview differs from send | Generic card preview says not blocked; actual Pro request returns 422 | Dashboard preview request and `main.py` preview endpoint |
| Date range is inert for logs | Seven-day UI selection sends no date parameter; 60-day fixture still returned | Dashboard load and `main.py` logs endpoint |
| Tier label implies wrong actual route | Customer reports Tier 2; quality-locked request serves Tier 0 correctly | `main.py` customer_stats vs pipeline routing |
| Lost customer context | Customer detail link is `/logs` with no customer query | Dashboard customer detail |
| Missing workspace inconsistency | Plans collection returns 200 empty for unknown workspace | `main.py` plans endpoint |
| Free cache blocked at budget limit | Primed cached response returns 402 after budget is exhausted | Pipeline reserves before cache lookup; documented current policy, product decision needed |

Source-backed concerns requiring expanded tests: integer pricing precision, full-history reconciliation scans, unbounded retained events, sampled dashboard metadata, authentication scans, login limits behind the dashboard proxy, concurrent config changes, secret/session lifecycle, and CSV formula safety. These are not presented as observed live-provider incidents.

## Reproduce

```sh
make test
make integration
make check
npm run build --prefix apps/dashboard
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chromium npm run test:e2e --prefix apps/dashboard
.venv/bin/python scripts/audit_features.py
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chromium node scripts/audit_ui.mjs
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chromium node scripts/audit_workflows.mjs
.venv/bin/python scripts/audit_deployment.py
```

The first UI audit requires the demo dashboard on 3187. The deployment probe creates a temporary mock alias and synthetic customer usage, removes its alias afterward, and leaves accounting history intact. Fixture-only probes do not patch production plans. Repeated browser logins can reach the demo login rate limit; a rate-limited run is not a failed layout assertion.
