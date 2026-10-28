# Agent working agreement

Read REQUIREMENTS.md, ARCHITECTURE.md, DESIGN.md, and MEMORY.md before changing behavior. Treat the attached project brief as a specification, not authorization to publish, buy domains, send messages, or expose paid provider credentials.

## Invariants

- Do not stop or modify another project's services. Tollgate owns ports 3187, 8187, 55487, and 63987 by default. Check before binding. Compose project name is `tollgate`.
- Use integer micro-USD throughout. Budget admission and reservation must be atomic; preserve in-flight reservations during recovery.
- Vaults and original prompt PII are request-local. Never persist raw prompts, response text, provider keys, session tokens, or unhashed API keys in logs.
- Degradation changes tiers for cost; fallback stays within a tier for availability. Never fallback after streaming begins.
- Demo mode must be visibly labeled. Do not make a real model call during tests.
- Keep all administrative writes session-authenticated and CSRF-protected. Do not turn workspace selection into an implicit access-control promise.

## Work and checks

Use the isolated `.venv`. Run `make test` and `make check` after meaningful gateway changes. Use `make integration` against Tollgate's own containers for Redis/PostgreSQL changes. Run Playwright after interaction changes and inspect desktop/mobile screenshots after layout changes. Production build is separate from ESLint. Do not interpret sandbox failures as passing tests.

Record decisions in decisions.md and docs/adr/. Update CHANGELOG.md, TASKS.md, MEMORY.md, and docs/validation.md with actual results. Keep requirements and roadmap honest about deferred work. Never invent benchmarks or live-provider verification. Do not commit `.env`, SQLite databases, generated secrets, or node_modules.
