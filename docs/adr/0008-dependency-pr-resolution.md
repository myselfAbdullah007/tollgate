# ADR 0008: Validate dependency updates together and defer unsupported compilers

Status: accepted, 2026-10-28.

Resolve the 14 open dependency PRs as a reviewed integration batch, preserving each compatible PR head in the merge history. Existing mainline policy, accounting and CI fixes take precedence when resolving conflicts. Regenerate a consistent dashboard lock in a clean Node 22 environment and validate with ordinary npm ci; do not use force or legacy-peer-deps to bypass installation problems.

PR 13 proposes TypeScript 7.0.2. Its CI run 40681492099 fails with `typescript-eslint does not support TS 7.0`; a separate clean local reproduction gives the same error. The installed parser supports TypeScript below 6.1. Retain TypeScript 5.9.3 and ignore TypeScript >=7 updates until a compatible lint stack is available. Do not disable lint rules or remove the TypeScript lint configuration to make that PR appear green.

The other 13 updates cover GitHub actions, Python minimum requirements, ESLint, Node types and icons. Python runtime lockfiles already contain the requested versions; the minimum-version changes align package metadata with the tested deployment. GitHub action manifests retain the inputs used here and run on Node 24; CI uses hosted runners. Manual image publication remains owner-triggered and is not executed by this maintenance task.

Acceptance requires gateway/infrastructure checks, static analysis, production dashboard build, browser flows, screenshot inspection and CI of the integrated result. Record individual dispositions and actual results in docs/pr-review-2026-10-28.md and docs/validation.md.
