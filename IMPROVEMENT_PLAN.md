# Tollgate improvement and business-readiness plan

Review date: **2026-10-28**. Baseline: **172ac2a** on `main`.

The first priority is to make the existing controls readable, reachable, accurate, and safe to edit. The current mock demo and core gateway flows work, but the deeper review found issues the original smoke suite does not cover. This document is a proposed implementation backlog; the findings below have **not** been fixed by this review.

## 1. Evidence and current status

| Verification | Result in this review |
|---|---|
| `make test` | 43 passed, 6 infrastructure cases skipped as expected without test DSNs |
| `make integration` | 49 passed against Tollgate's own PostgreSQL and Redis |
| `make check` | Ruff, mypy, ESLint, TypeScript passed |
| Next.js optimized production build | Passed |
| Existing Playwright suite against Docker | 5 passed; 12.7 seconds |
| Controlled Docker deployment probe | PostgreSQL/Redis readiness, streaming, fallback, Tier 2 degradation, worker delivery and metadata privacy passed |
| Targeted feature/workflow probes | Reproduced the defects listed below; these are observations, not passing acceptance tests for future fixes |
| GitHub CI on baseline | Failed in gateway service initialization: PostgreSQL health-check quoting; downstream Compose job skipped |
| Live paid-provider verification | Not performed; mock/recorded provider data only |

Evidence: [review report](docs/audits/2026-10-28/REVIEW.md), [feature probes](docs/audits/2026-10-28/feature-probes.json), [workflow probes](docs/audits/2026-10-28/workflow-probes.json), [UI measurements](docs/audits/2026-10-28/ui-measurements.json), [deployment probe](docs/audits/2026-10-28/deployment-probes.json).

## 2. Priorities and release gates

**P0:** fix before an external pilot: accidental policy loss, incorrect workspace edits, unreachable controls, routing identifiers blocked as PII, and failing main CI.

**P1:** fix before paid production traffic: misleading operational state, compatibility/validation failures, reliable cost precision, recovery, access and capacity controls.

**P2:** improvements that make the product easier to adopt and operate at scale.

**P3:** later integrations justified by customer demand.

Effort ranges below are initial estimates for one developer familiar with the code, including tests and documentation. They are not delivery commitments. Resolve P0/P1 correctness before increasing provider breadth or adding a billing integration.

## 3. Confirmed defects to fix

| ID / priority | Finding and business impact | Planned change | Acceptance check |
|---|---|---|---|
| F01 / P0 | Plan editor keeps only CARD and two thresholds. A plan blocking CARD/EMAIL/SECRET loses EMAIL and SECRET on save; a third threshold disappears. An innocent edit can weaken privacy policy. | Edit every supported category and any number of threshold steps; preserve fields outside the edited scope; add configuration revision checks. | Open/save without edits is lossless. Editing RPM preserves all block categories and thresholds. Conflicting saves are detected. |
| F02 / P0 | Settings retains the old workspace form after switching workspaces. The next save targets the newly selected workspace with old values. | Keep workspace identity in a persistent route/context; reset/key forms on scope changes; cancel old requests; close scoped dialogs or warn about unsaved edits. | Switch between two workspaces with different names/RPM/plans. Every input and subsequent request matches the selected workspace. Delayed old responses cannot overwrite it. |
| F03 / P0 | Sidebar content is about 958 px tall without internal scrolling. Sign-out ends at 940.5 px at desktop heights of 600–900 px. The open mobile drawer also clips it. | Separate brand/workspace header, scrollable navigation, and account/footer. Use `100dvh`, `min-height: 0`, appropriate flex sizing, safe-area padding and keyboard-reachable scrolling. Collapse the decorative status card on short screens. | At 1280×720, 1366×768, 1024×600 and 390×844, all navigation and sign-out can be reached by pointer and keyboard, including zoom/reflow checks. |
| F04 / P0 | PII scanning transforms the complete request, including the model alias. A valid configured alias ending with a Luhn-valid number is rejected as CARD even when its prompt is just “Hello”. The timestamp-based existing Compose smoke can fail intermittently for this reason. | Detect/redact message text and supported tool data using explicit field traversal. Keep routing identifiers and structural fields separate. Decide safe behavior for schema keys separately from values. | A numeric alias serves normally; an actual payment-card value in a prompt is still blocked; text/tool round trips remain intact. Use stable, detector-safe test identifiers as an additional fixture improvement. |
| F05 / P0 | Main CI fails before backend tests run: the runner's Docker command interprets `-U` from the single-quoted health command as a Docker option. | Correct runner-compatible health-command quoting; validate fresh-runner setup and pin compatible dependencies. | Main gateway, dashboard and Compose jobs all complete successfully from a clean checkout. Local passing checks are not substituted for remote success. |
| F06 / P1 | Faint pink/violet text is below contrast targets in useful controls and data. Examples: table heading 3.43:1, customer link 3.93:1, budget percentage 2.40:1. | Introduce a small semantic token palette; use dark neutral text for content and dark accent/status text on light backgrounds; raise operational text sizes. Remove overlapping override blocks. | Normal text ≥4.5:1, large text ≥3:1; check controls, placeholders, badges, tables, forms, errors, hover/focus and chart labels. Validate with an accessibility engine and manual review. |
| F07 / P1 | `tool_calls: null` causes HTTP 500. | Use typed message/tool models; normalize valid null optional fields and reject invalid shapes with a consistent client-error envelope. | Supported null forms normalize successfully or return documented 4xx; malformed lists/arguments never trigger 500. Include SDK-level contract tests. |
| F08 / P1 | Text-part system content passes the gateway schema but raises TypeError in the Anthropic translator. | Normalize all supported system/developer/tool text representations; explicitly reject unsupported shapes before routing. | Equivalent string/text-part conversations work in adapter fixtures for streaming and non-streaming requests. Translation failure is not mislabeled as provider downtime. |
| F09 / P1 | Playground preview uses a generic privacy mode instead of the selected customer's plan. Default preview permits a card that the actual request blocks with 422. | Resolve the selected customer/plan for preview; show the effective policy, blocked category and what will actually be sent. | Preview and send agree for off/mask/reversible/block, category blocks and customer plan changes. Preview never persists the vault. |
| F10 / P1 | Request-log date selector does not send a date constraint. A 60-day-old record remains returned for a seven-day request. | Persist filter state in the URL; send explicit start/end UTC boundaries; filter in SQL before count/pagination. Use identical boundaries for cards, chart and logs. | Changing range changes results with seeded old/boundary records; pagination, exports and links preserve filters. |
| F11 / P1 | A customer can be displayed as Tier 2 while a quality-locked request correctly serves Tier 0. Current overview language claims actual degradation based on a plan-derived eligibility value. | Separate “budget utilization/eligible tier” from “actual tier served per alias”. Derive degradation counts from request events. Label exhausted/overage/quality-locked states explicitly. | A quality-locked alias never contributes a false degraded event. Single-tier aliases never appear to have served a nonexistent tier. |
| F12 / P2 | Customer details opens `/logs` without the customer filter. | Deep-link directly to the selected customer's requests; show a small customer activity history in detail view. | One click shows only that customer's requests, with the filter visible and removable. |
| F13 / P2 | Some unknown workspace collections return 200/empty instead of consistent 404. | Centralize workspace validation and error mapping. | Plans, aliases, keys, logs, usage and customer APIs agree on missing workspace behavior. |

F01/F02 were reproduced with intercepted browser fixtures; no live privacy or workspace settings were changed. F04 was reproduced in an isolated temporary application. Source locations are recorded in the review report.

## 4. UI and UX implementation plan

### A. Readability system

Use a compact semantic palette rather than increasingly specific per-component fixes:

| Token / role | Suggested starting value | Usage |
|---|---|---|
| Primary text | `#242333` | Main content, amounts, headings |
| Secondary text | `#575364` | Descriptions, table metadata, labels |
| Muted text | `#6B6578` | Timestamps and helper text; verify on each actual surface |
| Accent text | `#6441B4` | Links, selected navigation and inline actions |
| Accent surface | `#F1EBFC` | Selected rows and callouts |
| Success text | `#246B50` | Healthy/protected labels on pale green |
| Warning text | `#805500` | Near-budget labels on pale amber |
| Danger text | `#A33434` | Exhausted/failed labels on pale red |

These are starting values, not pre-certified contrast pairs. Measure final foreground/background combinations, including disabled, focus and selected states. Follow the [W3C contrast criterion](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum).

Prefer 13–14 px for operational body/table text, 12 px or more for secondary labels where space permits, and avoid essential text at 7–10 px. Keep the violet identity for actions and selected states; it should not make every data value faintly tinted. Use explicit status words alongside color. Keep tabular numerals and at least four decimal places where small request costs need to be understood.

### B. Reachable navigation and mobile behavior

Keep the account and sign-out region reachable without relying on a tall monitor. Put optional status messaging below core navigation only when there is room. Make the middle region scrollable without scrolling the entire sidebar out of view. Do not reduce text to solve overflow. On mobile, add dialog-style focus handling, Escape, outside-click close, background scroll management, and return focus to the opener. Test actual drawer contents, not only that it opens/closes.

### C. Operational truth and decision support

- Replace unconditional “Gateway connected” with observed API/worker/provider states and a last-checked timestamp. Distinguish a stored credential from verified connectivity.
- Display effective privacy and budget policies; remove universal claims when any plan has privacy disabled or a budget is exhausted.
- Count active customers by requests in the selected period, rather than total configured customers.
- Show current spend, in-flight reserved amount, hard limit, overage allowance, reset time and effective per-alias behavior together.
- Explain reserved versus settled balance in response diagnostics and the playground. Do not present a conservative reservation estimate as the final bill.
- Show estimated token/cost badges prominently. Surface data truncation/sampling and worker ingestion delay rather than silently mixing partial and full metrics.
- Include cost by customer, plan, feature and model, plus top budget risks. Keep errors/fallbacks separate from financial degradation.

### D. Forms and daily workflows

Add lossless round-trip forms, dirty-state protection and field-level errors. Keep immutable IDs understandable and copyable. Avoid sending all workspace reads on every search keystroke; fetch only page-relevant data, with cancellation and pagination. Use scoped data loading so a provider-list failure does not blank an otherwise usable customer page. Make clipboard failures visible and add copy feedback that works in HTTPS deployments.

Show provider source accurately when stored keys override environment keys. Add credential validation as an explicit controlled operation, with no automatic paid probe. Include key last-used time, safe rotation guidance, expiry/scopes and server-only SDK instructions. Use deployment-aware API/documentation URLs; hard-coded localhost links will break for remote users.

Make request export clearly say whether it exports a page or all filtered rows. Add asynchronous full-range export later. Neutralize spreadsheet formula prefixes in CSV fields and keep export access audited.

### E. Frontend maintainability

Split the large dashboard component into a persistent workspace shell, page components, typed resource hooks and dedicated editors. Replace multiple overlapping CSS override layers with tokens and component styles. Keep state scoped to the entity/workspace it edits. Add component/interaction tests for data loss, workspace switches, stale responses, height constraints, date filters and dialogs; screenshots alone will not catch these behaviors.

## 5. Gateway, accounting and operations improvements

These are code-review findings and known design limits; items without a targeted reproduction are not presented as proven production incidents.

### Cost and budget correctness — P1

1. Store versioned pricing as integer micro-USD per million tokens, not whole micro-USD per token. This represents fractional token rates without introducing floating-point money. Compute integer ceiling division at the final rounding boundary; use the same price version for reservation and settlement.
2. Record input/output/cached-input pricing, effective date and model availability. Validate prices/routing together before configuration activation. Do not silently assume an example table is an invoice-grade price source.
3. Use model-specific tokenizers when available, retain a conservative fallback, and label all estimates. Test Unicode, tools, large inputs, maximum output, cancellation and missing usage.
4. Decide and document the cache-at-limit policy. Current behavior returns 402 even for a primed zero-provider-cost cache hit because reservation happens first. If continuing safe cached replies is desired, check privacy-safe cache after rate admission but before reserving provider cost. Keep workspace isolation and abuse limits.
5. Consider stepping farther down the allowed ladder if the chosen tier's conservative reservation will not fit. Never do this for quality-locked aliases; report the decision clearly. This is a product policy change, not an unnoticed implementation adjustment.
6. Model any workspace-wide financial safety cap separately from customer budgets, with explicit behavior when reached. Customer-only caps can leave a SaaS exposed to aggregate spend across many newly created customers.
7. Define billing periods and reset boundaries explicitly, including midnight UTC and future account-specific billing anniversaries. Avoid promising local-time resets while counters use UTC.
8. Add idempotency semantics for client retries, including interrupted streams. Make provisional/uncertain provider charges visible and reconcilable rather than permanently hiding them in ordinary successful cost rows.

### Reliability and recovery — P1

- Add crash/restart tests around reserve, upstream first byte, settlement, XADD, SQL commit, acknowledgment and reconciliation lease expiry. Verify reservations survive reconciliation and duplicate delivery never double-counts.
- Replace full ledger/retained-stream scans with SQL aggregates plus durable checkpoints and bounded pending-event lookup. The current global admission freeze will become disruptive as history grows.
- Review stale counters for customers with no ledger rows; rebuilding only keys present in an aggregate does not necessarily clear every drifted key. Specify zero-balance reconciliation explicitly.
- Add a dead-letter/quarantine policy, bounded retries and worker progress alerts for malformed events. Use unique worker instance identities, not PID alone, when scaling containers.
- Set acknowledged-event retention without trimming pending deliveries; add ledger/rollup/backup retention rules and tested recovery procedures.
- Measure queue lag, oldest unacknowledged event, reconciliation duration, failed settlements, reservation expirations, latency p50/p95/p99, provider errors, fallback counts, cache hits and actual degraded requests.
- Bound body size before full JSON parsing, concurrent requests/streams, connection pools and outstanding reservations. A request-per-minute limit alone does not cap expensive concurrent work. This addresses a relevant [OWASP resource-consumption risk](https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/).

### Data and API scalability — P1/P2

Move filtering, count and pagination into SQL. Current logs fetch at most 10,000 rows before filtering and can omit older matches; usage mixes complete daily totals with sampled metadata. Add cursor-based pagination and exact aggregate queries with clear eventual-consistency timestamps.

Replace scanning every tenant/key during authentication with an indexed hash lookup and a scoped cache whose revocation behavior is explicit. Avoid a full ledger sum on every request when the Redis counter is already initialized. Fetch customer detail by indexed identity rather than loading the whole collection. Batch worker transactions only after idempotency and rollup concurrency are covered by tests.

Protect multi-record operations with transactions and appropriate referential constraints/locking. Creating a workspace and its templates should not leave partial state after a failure. A plan must not be deleted while a concurrent customer assignment succeeds. Track configuration revisions and administrative actor/reason in metadata-only audit records.

### Security and administration — P1

Add an owner password-change/recovery procedure, session inventory/revocation, administrator invitations and role management. Enforce workspace membership at the API if customer-facing/multi-organization dashboards are offered; deployment-wide admin sessions are currently an explicit design boundary.

Add encrypted-key rotation and tested backup/restore steps before integrating KMS. Review trusted-proxy client address handling: the dashboard proxy can make independent users share a login-IP limit. Do not blindly trust forwarded headers from arbitrary clients. Add request-level abuse controls and deployment-safe secure-cookie/TLS defaults.

Expand privacy testing across real supported regional formats, Unicode, overlap, unknown placeholders, text parts and tool arguments. Names/addresses/IPv6 need explicit coverage or honest exclusions. Treat PII counters as detector matches, not compliance guarantees. Add an explicit policy for generated output and schema keys rather than promising complete sensitive-data detection.

## 6. Business features worth adding

| Addition | Business need | Minimum useful release | Success measure |
|---|---|---|---|
| Cost and margin by AI feature | A SaaS must know which feature/customer is profitable, not just its provider bill | Bounded `feature`/environment tags, customer/feature/model reports; optional revenue/allocated AI allowance import | Teams can identify the top loss-making usage segment and act without exporting raw prompts |
| Budget alerts and signed webhooks | Warn before an AI feature pauses; give the SaaS time to notify or upgrade a customer | Threshold/degraded/exhausted events, signature verification, retry/dedup and delivery log | Alerts arrive once logically, retries are visible, and customers receive useful action before exhaustion |
| Usage/allowance API and embeddable customer view | End customers need transparent entitlement and reset information | Read-only scoped customer usage/limits/reset endpoint; optional small usage widget | Fewer “why did AI stop?” support contacts and clearer upgrade decisions |
| Upgrade and overage workflow | Preserve conversion and revenue without unbounded provider spend | Plan-change preview, prorating policy decision, explicit bounded overage consent | Upgrade is intentional, auditable and cannot bypass agreed spending controls |
| Project/environment separation | Teams must isolate development, staging and production | Project/environment-scoped keys, policies, quotas and reporting | Test traffic cannot consume production allowance or expose production credentials |
| Quality guardrails for degradation | Cheaper responses must still meet the feature's quality needs | Per-feature quality lock, offline evaluation fixtures, rollout/canary and rollback | A cheaper tier meets agreed quality criteria before broad rollout |
| Operator diagnosis and audit trail | Support needs a reliable reason for a failed/degraded request | Safe error taxonomy, actual route/attempt metadata, policy version and actor/reason history | Operators explain an incident from metadata without requesting private prompts |
| Provisioning/configuration API and CLI | Large SaaS customer lifecycles should not depend on manual admin clicks | Idempotent customer/plan provisioning, import/export and dry-run config validation | New accounts and plan changes stay consistent with the SaaS source of truth |
| Provider/catalog validation | Operators need to know whether a configured route can actually run | Model/provider capability checks and price/version warnings; opt-in capped credential check | Invalid routes are caught before a live customer request |
| Team access controls | Engineering, support and finance require different permissions | Owner/admin/viewer and narrowly scoped support/finance permissions, membership and audited changes | Routine support work does not require global production-secret access |

Do not claim savings from a counter alone. Compare actual routed cost against a documented baseline price/model for equivalent requests; report estimated versus measured savings separately. Feature tagging should not permit arbitrary PII or unbounded cardinality in metrics.

## 7. Sequenced delivery plan

| Phase | Scope | Estimated effort | Exit gate |
|---|---|---|---|
| 0 — Establish a reliable baseline | F05 CI, deterministic smoke fixtures, pin supported toolchains, convert confirmed findings into regression tests | 1–2 developer days | Clean-checkout main CI runs all required jobs successfully; known issues remain clearly reported |
| 1 — Safe, readable console | F01–F03 and F06; workspace state/cancellation; semantic colors; reachable sidebar; UI data-loss tests | 3–5 days | No policy loss or wrong-workspace saves; readable and reachable at audited viewports and keyboard/zoom states |
| 2 — Correct request and operational behavior | F04, F07–F11, F13; effective preview; real date filters; truthful tier/status labels; customer log context | 3–5 days | Targeted probes become passing regressions; UI and API agree on actual policy and routing |
| 3 — Paid-traffic readiness | Versioned precision pricing, estimate visibility, retry/accounting/recovery tests, request concurrency limits, auth/secret lifecycle, ingestion alerts | 5–8 days | Controlled staging cost/recovery/security review passes with agreed launch thresholds; no paid call in routine CI |
| 4 — Useful business reporting | Feature/environment cost, active-customer definition, SQL pagination/aggregates, usage API and signed threshold events | 4–7 days | Operators can answer “who/which feature costs money, why, and what should happen next?” without manual data stitching |
| 5 — Scale and integrations | Worker batching/checkpoints/retention, load/soak tests, projects/teams, quality evaluation, optional integrations | 5–10+ days | Workload-specific SLOs hold with realistic history and concurrency; integrations are driven by actual customer needs |

Some phases overlap, but regression coverage, policy safety, accurate cost and trustworthy routing must precede business billing automation. Re-estimate after the first phase; the ranges are not additive launch-date promises.

## 8. Verification plan for implementation

Every confirmed finding gets a failing regression before its fix. Keep those future acceptance tests separate from today's observation probes so “audit script exited successfully” cannot be mistaken for “bug fixed”.

- **UI:** screenshot and interaction coverage at 1440×900, 1366×768, 1280×720, 1024×600 and 390×844; 200% zoom/reflow; focus visibility, drawer/dialog focus, essential contrast, scroll access and CSV safety.
- **State:** two workspaces with deliberately different settings; network delays and out-of-order responses; dirty forms; multi-category/multi-threshold round trips; stale configuration revisions.
- **Business logic:** mixed aliases with quality locks and one/many tiers, budget reset boundaries, bounded overage, cache at zero budget, reservation failures and exact integer cost fixtures.
- **Compatibility:** real SDK parsing with recorded transports; optional fields/nulls; text parts; tool calls/results; SSE content and argument splits; pre-byte fallback and post-byte failure.
- **Durability:** real PostgreSQL/Redis tests, worker crash/replay, reconciliation lease expiry, zero-ledger customers, expired reservations, Redis restoration and poison-event handling.
- **Scale:** cold/warm auth, many customer keys, >10,000 log rows, growing event history, concurrent streams and long-running soak. Set SLOs from measurements rather than inventing a target result.
- **Release:** `make test`, `make integration`, `make check`, production build, expanded Playwright, controlled Compose smoke, remote main CI and human review all pass. Live-provider smoke is a separate explicitly authorized, capped staging activity.

## 9. Defer until the foundation is reliable

More providers, semantic cache, embeddings/media/audio, prompt management, Stripe sync, SSO/enterprise identity, Helm/Kubernetes, broad NER and KMS integrations should follow demonstrated demand. They do not fix unreadable budgets, a missing sign-out button, destructive plan edits or inaccurate cost reporting. Preserve the product's focused promise: customer-aware spending controls and useful private answers.
