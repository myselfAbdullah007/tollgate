# ADR 0012: Apply and validate closed Dependabot updates

Date: 2026-11-12

Status: Implemented locally; hosted integration validation pending.

Closing an update PR does not apply its fixes. Consolidate the fourteen closed
updates into a tested replacement branch and PR, preserving application behavior
and checks. Raise Python minima to requested versions, pin cryptography 50.0.2 in
both locks, upgrade frontend dependencies including TypeScript 6, and update all
uses of the four requested GitHub Actions.

TypeScript 6 is accepted after lint/types/build validation. The separate TypeScript
7 ignore remains until its previously documented compiler-API blocker is resolved.
Do not weaken lint to force a compiler update.

A newly observed minimatch advisory in development tooling needs a scoped override:
replace only the vulnerable 10.x range with 11.0.8, retaining unaffected 3.x users.
Test consumers on Node 22 and retain normal package-manager validation. Remove the
override when upstream ranges support patched versions. Peer warnings are recorded,
not hidden. npm audit results describe the execution time, not security certification.

See docs/pr-review-2026-11-12.md and docs/validation.md for individual PR mapping,
source references, cross-version ciphertext checks, actual results and unavailable
container/infrastructure checks. No merge or publication is performed by this work.
