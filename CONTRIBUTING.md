# Contributing

Start with README.md, AGENTS.md and ARCHITECTURE.md. Install with `make install`; run `make dev` with no external provider keys. Preserve other projects' processes and ports.

Use a small branch with a concrete before/after description. Include tests for changed behavior at its owning boundary. Do not add tests that simply duplicate an implementation. Critical boundaries are budget concurrency, provider translation, stream restoration, tenant/cache isolation, key lifecycle and durable accounting.

Before a pull request, run `make test`, `make check`, the dashboard production build, and browser tests for UI changes. Storage/Redis changes also need `make integration` against Tollgate's isolated containers. Document commands and actual results, including skipped checks. No test may call a paid provider.

Use Python types and Ruff formatting. Dashboard code uses TypeScript strict mode and ESLint. Keep product language understandable: implementation details belong in setup/diagnostics rather than routine operator actions. Keep controls labeled and layouts usable on mobile.

Record architectural changes in docs/adr and decisions.md. Update requirements, roadmap and changelog when scope changes. Never include secrets, original prompts or private customer data in fixtures/screenshots. Report security concerns privately as described in SECURITY.md.
