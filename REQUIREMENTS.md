# Requirements and traceability

Source: `/home/abdullah/Desktop/TOLLGATE.odt`, read on 2026-10-28. The user requested a complete implementation with particular attention to discoverable UI, testing, agent/project documentation, and preserving another concurrently running project.

| Area | Acceptance behavior | Implementation / evidence |
|---|---|---|
| Compatibility | Text chat completions, SSE streams, tools, alias listing | `schemas.py`, `providers.py`, `pipeline.py`; API/adapter tests |
| Providers | OpenAI, Anthropic, Gemini, mock | Native Anthropic translation; Google's official OpenAI-compatible endpoint; respx fixtures |
| Identity | Hashed, once-shown, revocable tenant keys; admin session | `security.py`, admin API; cookie auth and revocation tests |
| Customers | Header or `user`, auto-create, editable plan/budget | Customer resolver; dashboard customer search/editor |
| Budgets | Integer money, atomic reservation, thresholds, overage cap | Redis Lua and memory lock; 300 concurrent requests |
| Routing | Alias ladders, quality lock, fallback, circuit breaker | `pipeline.py`, `fastpath.py`; forced mock outage tests |
| Rate limits | Atomic per-customer and per-workspace sliding window | Redis Lua / demo lock; rejection has Retry-After |
| Privacy | Detectors, stable request vault, mask/block/off/reversible | `redaction.py`; checksums, block, tool input tests |
| Streaming | Split-token restoration; never change provider mid-answer | Hypothesis and interruption tests |
| Cache | Exact request + tenant + tier; temperature 0 only | Restores current vault; no cache with privacy off |
| Accounting | Durable event delivery, monthly ledger, rollups, reconciliation | Atomic Redis settlement/XADD; Postgres partitions; worker integration |
| Admin API | Tenant creation/edit, plans, aliases, keys, customers, logs, usage, providers, preview | Typed payload validation; session on every endpoint |
| Dashboard | Overview, customers/details, logs, plans, routing, keys, providers, playground, settings | Next.js; Playwright, desktop/mobile screenshots |
| Operations | Health/readiness, Prometheus, CLI commands, Compose | Dedicated network/ports/volumes; optional observability overlay |
| Documentation | All user-requested files and practical setup instructions | Root docs, docs/adr, examples, runbooks |

## Deliberate deviations from the proposed internal layout

The brief's exact file tree is a suggested architecture rather than a requirement to create empty modules. Configuration records use a tenant-scoped typed JSON payload table with a unique `(kind, tenant, name)` key. Request ledger and daily rollups have explicit relational tables. See ADR 0005. Backend modules are grouped by responsibility rather than one file per tiny stage.

Token fallback uses conservative UTF-8 byte bounds rather than a provider-specific tokenizer. Costs and estimates are explicit. Redis worker reads batches of up to 500; each event commits its ledger and rollup transaction individually for reliable replay. Throughput batch insertion remains a future optimization.

Per-tenant dashboard identities, Presidio, KMS, tracing and public release/deployment are tracked in ROADMAP.md; they are not silently stubbed. Name/domain reservation and publishing need owner identity and are not performed.

## Image distribution addition — 2026-11-11

Pull-only Compose, external-store configuration, an optional dashboard, source-free
deployment archive and a manual Docker Hub workflow are implemented. Compose and
archive checks do not establish image build, runtime or registry availability.
Actual image publication, multi-platform builds and container smoke remain pending
until run successfully; see docs/image-distribution.md and docs/validation.md.

On 2026-11-12 the user authorized automatic Docker Hub publication after PR merges.
Successful integrated-commit CI gates that publication. Exact commit tags and a
separate latest promotion replace manual-only Docker Hub delivery; manual stable
releases remain available. Credentials and a successful first hosted run are still
required. See ADR 0011.

## 0.2 acceptance additions

- Lossless policy edits, revision conflicts, effective preview, scoped workspace state and real date/customer filters have automated regression coverage.
- Readable semantic foregrounds and a scrolling sidebar with pinned account controls are measured at desktop/mobile viewports.
- Integer micro-USD charges use versioned integer per-million-token rates with ceiling division; missing/invalid usage is marked estimated. Rates remain illustrative.
- Feature/environment metadata powers SQL reports; optional customer revenue supports AI contribution only, excluding other COGS.
- Customer-bound usage keys expose only their own allowance/usage and cannot invoke chat. Environment tags do not create security or budget isolation.
- Transactional threshold events have signed HTTPS webhooks, bounded retries/deduplication and metadata delivery history. Notifications contain no prompts or answers.
- Deployment-wide owner/admin/viewer roles, self password/session controls, audit metadata, CLI reset and maintenance-only encrypted-secret rotation are implemented. Workspace-specific memberships remain deferred.

## Market-readiness hardening — 2026-11-13

- Chat options outside the supported subset fail with 422 before provider work;
  stream usage output honors `stream_options.include_usage`.
- Atomic tier admission reserves all possible fallback attempts. Unknown billable
  work after timeout/cancellation is recorded conservatively and explicitly, not
  as zero; confirmed unbilled failures remain zero. Cache outages preserve success.
- Post-commit delivery deletion, bounded legacy cleanup, stream-first snapshot
  ordering and transactional rollup aggregation replace unbounded event retention
  and full request-log loading. Real PostgreSQL/Redis integration and isolated
  container smoke passed on2026-11-13; representative capacity remains unverified.
- Fixed-cardinality operational metrics, Prometheus rules, offline production
  configuration checks and a pilot checklist support operator readiness. They do
  not establish live-provider accuracy, independent security review, recovery SLOs,
  published images, external alert delivery or shared-hosting identity isolation.

Detailed validation on 2026-11-13: 158 backend cases passed against PostgreSQL/Redis,
13 container browser cases passed, and a small quiesced SQL+Redis RDB restoration
preserved pending work and reservations. The 440-request mock exercise is bounded
local evidence, not representative production capacity. See
[the detailed report](docs/audits/2026-11-13-detailed-testing/REPORT.md).
