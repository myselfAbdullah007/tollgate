# ADR 0013: Conservative attempt accounting and bounded delivery retention

Date: 2026-11-13. Status: implemented; real PostgreSQL/Redis integration verified.

## Context

The market-readiness audit reproduced zero-cost accounting after provider timeouts
and silent discard of unsupported request options. Recovery loaded all ledger rows
and retained all successful Redis deliveries. The user authorized implementation.

## Decisions

1. Reserve the sum of candidate estimates in the selected tier. Preserve uncertain
   costs per attempted provider, including cancellation and pre-stream failure;
   distinguish known local/4xx rejections. Report uncertainty as metadata, never
   fabricate exact invoice usage. Keep successful answers if cache writes fail.
2. Reject unknown top-level chat and stream options. Honor `include_usage` for SSE.
   Document the supported subset rather than imply complete provider compatibility.
3. Commit ledger and daily rollups before atomically acknowledging/deleting Redis
   delivery entries. Retire legacy committed entries in batches of 500. Never
   trim arbitrary stream length or discard uncommitted events.
4. Freeze settlements, capture at most 10,000 retained events **before** the SQL
   snapshot, then use transactionally maintained daily rollups and only the
   captured ledger identities. This ordering makes concurrent worker deletion
   safe. Deduplicate by `(request id, created_at)`. Preserve reservations and
   recovery markers unless the lease-checked rewrite succeeds. Above the backlog
   limit, defer reconciliation while the worker drains; admission fences remain.
5. Expose fixed-cardinality operational metrics and offline production configuration
   checks. Provide alert rules without inventing external paging destinations.

## Consequences and limits

Long fallback chains reserve more budget. Conservative charges can exceed the real
provider invoice; operators must review them. The event stream is a private ledger
delivery queue, not an archival or general-purpose fan-out stream. Rollup aggregation
still scales with customer-days; counter rebuild output scales with customer-months.
An undelivered backlog is retained without a hard storage cap to avoid data loss.
This improves steady-state retention, not arbitrary-scale capacity certification.

Upgrade gateway and worker together with backups and a maintenance window. Mixed
workers using the old SQL-first snapshot and new deletion protocol are unsupported.
No live-provider calls, production deployment, publication, external messages,
security certification or invented load claims are authorized by this implementation.
