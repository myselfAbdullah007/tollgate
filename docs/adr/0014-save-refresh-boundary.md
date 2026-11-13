# ADR 0014: Separate committed writes from dashboard refresh failures

Date: 2026-11-13. Status: accepted.

## Evidence

Full-stack container validation returned HTTP 200 for both customer PATCHes, then
the dashboard proxy returned a plain-text 500 for a subsequent keys GET after an
upstream socket reset. The editor treated this refresh failure as a failed save.
Two deterministic browser regressions reproduced the misleading save error and
the unreadable JSON parsing error before correction.

## Decision

A successful mutation returns its result even when the subsequent workspace read
fails. The editor can close or show its once-only key result, while a visible
workspace warning asks the user to refresh. Do not automatically retry mutations.
Actual write failures still remain in the form. Non-JSON HTTP failures produce a
readable status message instead of exposing the JSON parser error or raw body.
Workspace-change cancellation and stale-response protections remain intact.

## Validation boundary

Use isolated validation service names and network under Compose project `tollgate`,
ports 3188/8188, fresh stores and empty external provider credentials. Existing
Tollgate services on 3187/8187/55487/63987 remain running and unchanged. The change
handles refresh failure correctly; it does not claim to eliminate every transient
upstream proxy reset. See docs/validation.md for passing and failed runs.
