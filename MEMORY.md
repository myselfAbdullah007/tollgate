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
