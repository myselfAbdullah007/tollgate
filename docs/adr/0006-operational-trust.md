# ADR 0006: Operational trust before feature expansion

Status: accepted, 2026-10-28.

The review reproduced destructive plan round trips, stale workspace forms, inaccessible sidebar controls, low text contrast and operational labels that can disagree with served requests. Passing the original smoke suite does not establish that these workflows are safe.

Decision: fix policy preservation and workspace state, make essential controls readable/reachable, repair main CI, then complete request/price/recovery correctness before adding billing automation or broader integrations. Keep an evidence-backed backlog and convert each reproduced finding into an acceptance regression before implementation.

Consequences: near-term work focuses on the current product's reliability and usability. Business additions such as feature-level margin reporting, signed budget alerts and usage endpoints follow trustworthy underlying data. Existing integer-money, request-local privacy, bounded budgets, same-tier fallback and service-isolation invariants remain requirements. This record approves no behavior change by itself.

See [IMPROVEMENT_PLAN.md](../../IMPROVEMENT_PLAN.md) and [review evidence](../audits/2026-10-28/REVIEW.md).
