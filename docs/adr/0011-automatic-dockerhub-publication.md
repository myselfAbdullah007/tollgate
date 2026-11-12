# ADR 0011: Publish Docker Hub images after successful merged-PR CI

Date: 2026-11-12

Status: Accepted; first hosted publication pending credentials and successful CI.

The user explicitly requested automatic Docker Hub publication when a PR is
merged. This supersedes the manual-only Docker Hub decision in ADR 0010.

CI runs for main pushes, PRs targeting main and manual dispatch. A publication gate
depends on all distribution/backend/dashboard/Compose-smoke jobs. On a main push,
it uses GitHub's associated-PR API to confirm the tested SHA is the merge commit
of a merged PR targeting main. Other pushes and failed checks do not auto-publish.

CI calls the reusable Docker Hub workflow at the same revision with the exact
tested SHA and explicit publish=true. It builds both application images for
amd64/arm64, pushes full-SHA tags, requests attestations and signs digests. Only
after both images and the release archive succeed does a separate job promote
latest; older commits skip promotion when main has advanced. Cross-repository
tag updates cannot be atomic, so users needing reproducibility should pin both
images to matching SHA tags or digests. A failed promotion may temporarily leave
latest aliases at different revisions.

Stable semver tags remain manual releases. Automatic merges do not overwrite a
stable version. Default deployment examples use latest; automatic release archives
pin the exact commit tag. Registry username/token are Actions secrets, available
only to the post-merge publication path or explicit manual publish. No publishing
workflow is invoked by a PR check. GHCR remains separately manual.

This configures future publication. It does not establish a successful image build,
registry push, hosted CI run, or production readiness. See docs/validation.md for
actual local checks and missing credentials.
