# Tollgate

**Meter, limit, and protect AI usage per customer — without breaking the product when budgets get tight.**

Tollgate is a self-hosted, OpenAI-compatible LLM gateway for SaaS applications. Tag requests with a customer ID. Tollgate tracks their spend, moves them to less expensive model tiers, and replaces sensitive input with placeholders that are restored in the answer — including streamed answers.

## Start here

Requires Python 3.12+, Node 22+, and npm. Docker is optional for the local demo.

```sh
cp .env.example .env
make install
make dev
```

Open **http://localhost:3187**. Click **Use demo credentials**, then sign in.

- Email: `admin@tollgate.local`
- Password: `tollgate-demo-2026`
- Demo API key: `tg_live_demo_tollgate_local_only`
- Gateway and interactive API reference: http://localhost:8187/docs

The mock provider needs no external API key. Demo activity is clearly labeled and seeded only into a fresh database. Real requests update the same dashboard. The local demo uses SQLite and a single-process memory fast path; use Docker for PostgreSQL, Redis, and the durable worker.

### Docker

```sh
cp .env.example .env
make key >> .env
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
```

The Compose project is named `tollgate`. It has separate volumes and an isolated network. Host ports are **3187** (dashboard), **8187** (API), **55487** (PostgreSQL), and **63987** (Redis). Database and Redis ports bind only to loopback. No script stops, kills, or reconfigures other projects. Override published ports with `TOLLGATE_DASHBOARD_PORT`, `TOLLGATE_PORT`, `TOLLGATE_POSTGRES_PORT`, and `TOLLGATE_REDIS_PORT` in the Compose environment. Set `TOLLGATE_ALLOWED_ORIGIN` to the browser origin if changing the dashboard port.

For local development, start the API with `TOLLGATE_PORT=8188 .venv/bin/tollgate serve` and the dashboard with `TOLLGATE_API_URL=http://127.0.0.1:8188 npm --prefix apps/dashboard run dev -- --port 3188`. Update the allowed browser origin too. `make dev` checks its default ports and refuses to occupy another application's port.

### Send your first request

```sh
curl http://localhost:8187/v1/chat/completions \
  -H 'Authorization: Bearer tg_live_demo_tollgate_local_only' \
  -H 'X-Tollgate-Customer: cus_acme' \
  -H 'Content-Type: application/json' \
  -d '{"model":"smart","messages":[{"role":"user","content":"Email ali@example.com a refund update"}],"stream":true}'
```

For an existing OpenAI SDK application, change `base_url` to `http://localhost:8187/v1`, use a gateway API key, and send `X-Tollgate-Customer` (or the `user` field). See [examples](examples/).

![Tollgate overview](docs/screenshots/overview.png)

## Why Tollgate

- **Customers come first.** Plans, budgets, usage, and rate limits match your SaaS customers rather than internal provider accounts.
- **Degrade gracefully.** At configurable spend thresholds, switch to a less expensive tier. Quality-critical aliases can lock quality. A hard budget stops requests only when no reservation fits.
- **Keep answers useful.** Providers see `[EMAIL_1]`; your customer sees the original email address. The request-local vault never enters the database, event stream, or cache.
- **Stay available.** Each tier has a fallback chain; repeated failures open a 30-second circuit breaker.
- **Try everything locally.** The built-in mock exercises streaming, fallback, degradation, and privacy without paid model calls.

### Degradation versus fallback

Degradation is a **vertical** budget decision between model tiers. Fallback is a **horizontal** reliability decision within the chosen tier. An outage does not switch tiers or silently increase the configured reservation ceiling. Configure target prices and chains carefully; the UI exposes both dimensions.

### Architecture

```mermaid
flowchart LR
  App[SaaS backend] --> Auth[Key auth + customer]
  Auth --> Rate[Atomic rate limits]
  Rate --> Budget[Tier + cost reservation]
  Budget --> Privacy[Request-local PII vault]
  Privacy --> Cache[Tenant-scoped exact cache]
  Cache --> Router[Fallback + circuit breaker]
  Router --> Models[OpenAI / Anthropic / Gemini / Mock]
  Models --> Restore[Stream-safe restoration]
  Restore --> App
  Budget <--> Redis[(Redis)]
  Router --> Events[Atomic settlement + Redis Stream]
  Events --> Worker[Durable worker]
  Worker --> PG[(PostgreSQL ledger + rollups)]
  Dashboard[Next.js dashboard] --> Admin[Session-protected admin API]
  Admin --> PG
```

See [ARCHITECTURE.md](ARCHITECTURE.md), [design decisions](decisions.md), and [ADRs](docs/adr/).

## Dashboard

Overview, customer search and budget editing, request details and CSV export, plan rules, visual model routing, API key lifecycle, encrypted provider credentials, a streaming playground, workspace creation/switching, and guided SDK setup. The interface supports mobile navigation, keyboard focus, `/` to focus table search, accessible dialog focus, and reduced motion. Fonts are bundled locally.

## Privacy and accounting

Email, phone, Luhn-valid payment cards, checksum-valid IBAN and Japanese My Number, Pakistani CNIC, IPv4, and common secret keys are detected in text messages, text parts, tool schemas, and tool-call arguments. Modes are `off`, `mask`, `reversible`, and `block`; plans can block selected categories independently. Cards are blocked by default. This is regex/checksum detection, not a claim to detect all personal information.

Known input values share stable placeholders within one request. Unknown generated placeholders become `[redacted]`. The stream restorer holds incomplete placeholders across chunk boundaries. Cache entries contain redacted requests/responses, never the vault, and are isolated by workspace, request, and routing configuration. Cache is disabled with privacy mode `off`. Logs contain metadata and category counts; prompts and answers are not retained at all.

Money is integer micro-USD: `$1 = 1,000,000`. Reservations use the most expensive target in the selected tier and conservative byte-based token bounds. Settlement uses provider token usage when available and marks estimates explicitly. Interrupted streams reserve-charge conservatively because providers can bill generated tokens after a disconnect. Headers show tier, target, cache status, request ID, and a conservative budget balance after reservation. Exact provider invoices can differ from the configurable pricing table, which is illustrative and must be reviewed before paid traffic.

Redis settlement and event publication are atomic. The worker acknowledges only after an idempotent ledger transaction and rollup. It reclaims pending events after crashes and reconciles spend every three minutes, preserving active reservations and including events not yet in the ledger. Redis AOF is enabled. See [operations](docs/operations.md) for recovery boundaries.

## Test and verify

```sh
make test                    # memory/SQLite, adapters, property tests
make check                   # Ruff, mypy, ESLint, TypeScript
npm run build --prefix apps/dashboard
# After starting Tollgate's PostgreSQL and Redis:
make integration             # real Lua, concurrency, partitions, worker, reconciliation
# With API/dashboard running in demo mode:
cd apps/dashboard
npx playwright install chromium
npm run test:e2e
```

The suite includes 300 concurrent reservations against a budget for 100 requests, random stream split boundaries with Hypothesis, no-input-PII persistence checks, tenant/cache isolation, recorded provider fixtures via respx, fallback before streaming, interruption after streaming, admin auth/CSRF, credential encryption, key revocation, PostgreSQL monthly partitions, worker idempotency, and mobile dashboard smoke tests. No test uses a paid provider key. [Validation results and measured local benchmark](docs/validation.md).

## Deployment status

This is early-stage software with a working local and Compose application, not a security-audited public service. Dashboard identity is shared by the deployment; workspace selection is an administrative scope, not tenant-specific login isolation. Demo mode is deliberately local-only in Compose. Disable demo mode, supply a private owner password and master key, enable secure cookies behind TLS, configure real routing, and review prices before handling live traffic. Detailed settings are in [configuration](docs/configuration.md) and [SECURITY.md](SECURITY.md).

Presidio NER, AWS KMS, signed webhooks, SSO, semantic caching, embeddings, media, Stripe sync, Helm, and tenant-specific dashboard logins are outside this release. [Public roadmap](ROADMAP.md). The working name has not been reserved or published on GitHub, GHCR, or a domain. Release publishing is manual and requires repository ownership and a private security disclosure contact.

Apache-2.0. Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
