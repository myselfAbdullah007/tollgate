# Architecture

Tollgate ships a Python FastAPI gateway/worker/migration CLI and a Next.js dashboard. Production-style development uses PostgreSQL 16 and Redis 7; a zero-infrastructure demo uses SQLite and an in-process fast path under an asyncio lock.

## Request flow

Key authentication → customer resolution → atomic customer/workspace rate admission → request-local redaction → budget/tier reservation → exact cache → provider routing → restoration → settlement/event publication.

The brief lists redaction after budgeting. This implementation detects/block-checks before reserving so rejected sensitive inputs never leave an abandoned cost reservation. The estimation sees the actual redacted provider payload. No provider call occurs before budget admission.

`Pipeline` holds the orchestration; `FastPath` owns atomic state, `Vault` owns originals only during a request, `Providers` translates transport, `Repository` owns durable configuration/ledger access. Each boundary is independently exercised in tests.

## Storage and identity

`records` holds named tenant-scoped configuration and shared deployment identity/session records, with a unique kind/tenant/name constraint. Sensitive provider payloads contain AES-256-GCM ciphertext; API keys and session tokens are hashed before storage. Argon2 hashes administrator passwords.

`request_logs` stores metadata and BIGINT cost. On PostgreSQL it is range-partitioned monthly by UTC ISO timestamp, with a composite request/time primary key and tenant/customer/time index. UUIDv7 request IDs preserve chronological locality. The writer creates monthly partitions under a PostgreSQL advisory lock. SQLite stores an ordinary table for local testing.

`usage_daily` stores requests, tokens and spend per tenant/customer/day. The worker commits log insertion and rollup update together. Replaying an event checks the ledger identity and does not update the rollup twice. Alembic revision 0001 creates the initial schema. Migration jobs are serialized by an advisory lock. Configuration updates use the unique record identity.

The dashboard is a shared administrative console. Every admin read/write needs a session. Viewer role blocks writes; owner/admin may manage all deployment workspaces. There is no tenant-specific login separation in this release.

## Fast-path state

Redis stores settled spend per billing month; a hash of request reservations; a sorted set of deadlines; sliding-window rate entries; privacy-safe cache responses; circuit-breaker state; and a durable event stream. Budget admission computes tier and reserves the most expensive possible target within that tier in one Lua script. Reservation deadlines are 180 seconds and upstream work is bounded to 120 seconds.

Settlement removes a reservation once, increments settled spend, and appends a metadata event atomically. The worker uses a consumer group, acknowledges after the ledger transaction, and reclaims stale pending delivery. Redis AOF uses synchronous fsync in the default Compose deployment.

Every three minutes, reconciliation takes a short Redis admission/settlement lease, obtains a consistent ledger snapshot, adds stream events not included in that snapshot, and rewrites settled counters atomically if its lease is still valid. In-flight reservation hashes remain untouched. Requests wait for the freeze; lease expiry prevents an old snapshot overwriting newer charges. A full simultaneous Redis/disk loss before ledger delivery cannot be recovered from Postgres alone.

## Providers, privacy, streams

OpenAI and Google's supported compatibility endpoint share an adapter transport. Anthropic translates system messages, tools/tool results, usage, and SSE content/tool deltas. Live credentials stay inside the gateway. Fixtures verify transport shapes without external model calls.

The router chooses a tier once and retries only eligible failures within it. It probes the first normalized streaming event before returning headers; after client streaming begins, failures become error events with no model switch. Responses carry actual model, tier, request ID and cache status.

The vault detects all text parts and tool arguments, deduplicates values, and assigns placeholders in occurrence order. The restorer buffers incomplete bracket tokens across chunks. Content and each tool-call argument stream have separate restorers. Unknown tokens are masked. Cache is tenant/request/routing-scoped and disabled in privacy-off mode. Prompt/answer text is not logged.

## Deployment boundaries

Next.js proxies `/api/*` to the internal gateway, keeping browser session cookies same-origin. CSRF checks verify origin and require an admin request header on writes. CORS is restricted to configured origins. Compose uses an isolated project/network/volumes and nonconflicting published ports. Docker images run as non-root. Optional Prometheus/Grafana do not expose model data.

See docs/operations.md for recovery and docs/adr/ for tradeoffs.

## 0.2 extensions

`pricing.py` stores versioned integer micro-USD rates per million tokens and rounds each charge upward. `limits.py` bounds request bytes and idle upload time; the fast path limits in-flight requests per workspace. Configuration writes use revision comparison and database row locks; key lookup has a hash-expression index. Logs are filtered/paged in SQL and reporting aggregates the full selected range rather than a sampled prefix.

Accounting retries idempotent settlement. If fast-path settlement fails, authoritative SQL accounting and a recovery marker commit together; admission is fenced until worker reconciliation incorporates captured markers. Reservations survive reconciliation. This improves single-store failures but cannot durably record an outcome if Redis and PostgreSQL both fail simultaneously. Operators must monitor failures. Reconciliation still scans history and retained events; checkpointing/retention remain scale work.

`notifications.py` creates deduplicated alert outbox records in the ledger transaction. Worker delivery runs separately from ledger ingestion, with HMAC timestamp/body signatures, public-address validation, pinned DNS, no redirects and bounded retries. Delivery is at least once; receivers deduplicate by event id. `admin_security.py` manages deployment-wide roles and self-service security. Vaults and provider plaintext remain request-local. Feature/environment tags affect reporting only. `business.tsx`, `editor.tsx` and `ui.tsx` separate business/security views, policy forms and shared controls from dashboard orchestration.
