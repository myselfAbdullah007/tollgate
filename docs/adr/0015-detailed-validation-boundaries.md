# ADR 0015: Enforce boundary contracts and fence duplicate recovery writes

Date: 2026-11-13. Status: accepted.

## Evidence

Detailed boundary testing reproduced eight failing cases across four defects:
malformed tool selections/descriptions were accepted; HTTPS webhook ports other
than 443 contradicted the documented destination policy; a disabled user could
receive an unusable new session; and retrying an already-committed event in
recovery mode omitted the recovery marker.

## Decision

Validate function descriptions and explicit tool choices before dispatch, including
that named choices reference supplied tools. Restrict webhook destinations to
HTTPS port 443 both on configuration and again at delivery, covering old records.
Reject disabled accounts before session creation. Upsert the recovery marker even
when the ledger identity already exists, without duplicating the charge/rollup.
Use dialect-specific conflict handling for SQLite and PostgreSQL.

## Verification and limits

Add boundary, role, CSRF, webhook, Unicode streaming, concurrent rate/settlement,
and real-store recovery/expired-lease regressions. Exercise only synthetic traffic
and isolated validation containers; retain actual failures and corrected results
in the detailed audit report. These checks do not establish comprehensive PII
detection, independent security assurance, paid-provider correctness or production
capacity. Simultaneous Redis and SQL settlement failure remains a surfaced manual
reconciliation incident; do not imply guaranteed accounting during total storage
loss.
