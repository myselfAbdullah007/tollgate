# Roadmap

## Current release: 0.1

Text gateway, customer budgets and degradation, provider fallback, reversible regex/checksum redaction including streams, exact cache, durable worker, monthly PostgreSQL ledger, admin console, local mock demo, Compose and automated tests.

## Before a public production release

- Owner confirms project name, GitHub/GHCR namespace, domain and private security disclosure contact.
- Verify chosen live model IDs and current pricing; run explicitly authorized live-provider smoke tests.
- Independent authentication, privacy, concurrency and accessibility review.
- Benchmark representative production traffic and define SLOs.
- Capacity tuning: transaction batch insert, bounded retention for event streams, SQL-native pagination/aggregation for very large admin datasets.
- Formalize encrypted-key rotation and backup/restore automation.
- Configure public HTTPS hosting; publish signed multi-platform images/SBOM through the manual release workflow.

## Next integrations

Presidio names/addresses via NER, AWS KMS envelope encryption, signed customer budget/degradation webhooks, OpenTelemetry collector/Jaeger, more detector formats (including IPv6), model-specific tokenizers and fractional price precision, user/role administration and tenant-specific dashboard identities.

## Deliberately outside 0.1

Semantic caching, embeddings, images, audio, Stripe billing sync, SSO, prompt management, jailbreak detection, Helm/Kubernetes distribution, per-tenant dashboard logins. These are intentional boundaries, not hidden partial implementations.
