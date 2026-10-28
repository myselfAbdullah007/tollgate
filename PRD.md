# Product requirements: Tollgate 0.2

## Audience and problem

SaaS engineers need predictable per-customer AI costs without turning spending caps into broken features. Operators need a single place to see who is approaching budget, trace requests, and protect sensitive inputs sent to model providers.

## Promise

Tag a request with a customer. Tollgate meters it, chooses an affordable model tier, redacts sensitive values, restores the response, and makes the decision visible. Existing applications adopt the text gateway through an OpenAI-compatible base URL.

## Primary journeys

1. Explore a seeded demo without external credentials; find customer budgets immediately.
2. Create a once-shown gateway key, copy the SDK example, send a tagged request, inspect usage.
3. Find an at-risk customer, inspect their spend/tier, update a budget or plan without searching through unrelated settings.
4. Configure a plan's budget, rate, thresholds and privacy policy; assign customer plans.
5. Add an encrypted provider key, edit an alias tier/fallback chain, test in the playground.
6. Preview what the provider sees, then stream an answer with the original values restored.
7. Filter request metadata, inspect cost/latency/privacy counts, export the current page.

## Success criteria

A developer can run the local mock demo and reach a functioning dashboard without an external account. Every navigation item leads to working content. Common configuration actions are available in context. No input PII appears in tested persisted cache/events/log records. Concurrent admissions remain within the configured reservation ceiling. A stream reconstructed from arbitrary chunk boundaries matches the non-streaming restoration.

## Release scope

Text chat and tool calling, three provider adapters plus mock, budgets/limits, reversible privacy, routing, exact cache, admin operations, durable Compose topology, tests, documentation. This release is intended for local evaluation and controlled self-hosted trials. General production readiness requires the security and operational review described in SECURITY.md.

## 0.2 business journeys

8. Open Insights & alerts to find expensive features/customers/models, distinguish estimates and actual lower-tier service, and review customer AI contribution using an optional revenue reference.
9. Create a customer-bound usage key so the SaaS can show remaining allowance without granting model access or exposing other customers.
10. Configure signed budget alerts as an owner, verify the receiver signature and inspect delivery history before relying on notifications.
11. Manage your password and sessions; owners create deployment-wide accounts, with API role/disable controls. Workspace membership remains a separate future requirement.

Lossless policy forms, concurrent-edit conflicts, working date/customer filters and reachable readable controls are acceptance requirements. Complete production-scale, live-provider and independent security review remain outside the demonstrated local verification.
