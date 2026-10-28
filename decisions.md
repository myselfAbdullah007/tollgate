# Decision log

| Date | Decision | Reason / record |
|---|---|---|
| 2026-10-28 | Keep ports 3187 / 8187 / 55487 / 63987 and Compose project tollgate | Another project already owns common ports; never stop it |
| 2026-10-28 | Built-in shared admin identity | Small self-hosted footprint; [ADR 0001](docs/adr/0001-built-in-auth.md) |
| 2026-10-28 | Redis fast path plus PostgreSQL ledger | Atomic admission and durable audit history; [ADR 0002](docs/adr/0002-fast-path-ledger.md) |
| 2026-10-28 | Integer micro-USD | Avoid float drift; [ADR 0003](docs/adr/0003-integer-money.md) |
| 2026-10-28 | Atomic Redis settlement + Streams | Charge and event publication cannot diverge in ordinary operation; [ADR 0004](docs/adr/0004-streams.md) |
| 2026-10-28 | Typed config records, explicit relational ledger | Keep administrative configuration compact without weakening money tables; [ADR 0005](docs/adr/0005-config-records.md) |
| 2026-10-28 | Separate zero-infrastructure demo | Make first use possible without Docker or paid credentials; memory mode is single-process only |
| 2026-10-28 | Gemini compatibility API | Use Google's maintained OpenAI-shaped endpoint for text/tools/SSE |
| 2026-10-28 | No prompt or answer retention | Metadata-only logs reduce privacy risk and still support operational diagnosis |
| 2026-10-28 | Bundle fonts locally | Avoid external font requests and offline rendering regressions |
| 2026-10-28 | Keep optional NER/KMS explicit on roadmap | Unsupported settings fail clearly rather than pretending to protect data |
| 2026-10-28 | Prioritize policy safety, readable/reachable controls and truthful operational state before feature expansion | Proposed delivery order and acceptance gates; [ADR 0006](docs/adr/0006-operational-trust.md), IMPROVEMENT_PLAN.md |

| 2026-10-28 | Versioned precise pricing, scoped usage keys, transactional signed alerts and explicit deployment-wide roles | Useful business controls without implying billing accuracy or workspace identity isolation; [ADR 0007](docs/adr/0007-business-controls.md) |

| 2026-10-28 | Integrate compatible dependency PRs, rebuild the lock under Node 22, defer unsupported TypeScript 7 | Preserve current application fixes and lint coverage; [ADR 0008](docs/adr/0008-dependency-pr-resolution.md) |
