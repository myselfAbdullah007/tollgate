# Roadmap

## Current release: 0.2

The original text gateway and console plus readable/reachable navigation, lossless revisioned policy editing, workspace state protection, effective-policy preview, precise versioned pricing, SQL reporting, scoped usage keys, signed alerts, self-service sessions/passwords, deployment-wide roles and recovery controls. See CHANGELOG.md and IMPROVEMENT_PLAN.md for acceptance scope.

## Before paid production traffic

- Verify chosen live model IDs/current prices and run explicitly authorized capped provider smoke tests; bundled prices are illustrative.
- Independent authentication, privacy, concurrency and accessibility review; configure TLS and private disclosure/backup procedures.
- Representative load/soak tests and workload-specific SLOs, including failure/recovery with realistic history.
- Automate backup/restore and rehearse the maintenance-only encrypted-secret rotation runbook.
- Bounded stream retention, incremental/checkpointed reconciliation, ledger batching and larger customer/config collection pagination. SQL request-log paging and usage aggregates are already implemented.

## Business workflow follow-ups

- Independent project/environment budgets and credentials (current tags are reporting metadata).
- Explicit upgrade/proration/overage consent, plan-change previews and per-feature quality evaluation/canaries.
- Transactional configuration import, richer lifecycle provisioning, customer usage widget, owner role-management UI and workspace-specific memberships.
- Validated model capabilities and tokenizers; opt-in capped credential tests.

## Optional integrations

Presidio names/addresses via NER, AWS KMS, tracing, Stripe sync, SSO, semantic caching, embeddings/media/audio and Helm. Signed webhooks, fractional price precision and basic deployment-wide roles are implemented, not future placeholders.

Public hosting and signed multi-platform image publication remain separate operator activities. No live provider or production capacity certification is implied by local mock testing.
