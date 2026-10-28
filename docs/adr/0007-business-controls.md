# ADR 0007: Useful business controls with explicit boundaries

Status: accepted, 2026-10-28.

Use integer per-million-token prices with integer micro-USD charges; tag bounded feature/environment names for reporting; create threshold/degradation events in the accounting transaction. Deliver signed public-HTTPS webhooks asynchronously with DNS pinning and bounded retries. Expose customer-bound read-only usage keys. Keep roles deployment-wide until real workspace membership exists.

Financial recovery uses idempotent settlement retries and an authoritative SQL recovery marker that fences admission until reconciliation. Preserve in-flight reservations and quarantine malformed stream records without retaining raw payloads. Use SQL pagination/aggregates for request history and key-hash lookup indexing. Independent load/security review, incremental reconciliation, stream retention and actual project/environment isolation remain required follow-ups.

Configuration editors preserve all supported fields and submit revisions. Exports exclude credentials and validation is dry-run only. AI contribution uses explicitly supplied revenue and excludes other business costs; no claim of full gross margin or measured savings is made.
