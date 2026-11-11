# ADR 0010: Pull-only application distribution

Date: 2026-11-11

Status: Accepted for implementation; Docker Hub publication and runtime verification pending.

## Context

Users should run Tollgate from published container images without checking out its
source or building locally. PostgreSQL and Redis remain separately operated
dependencies. The current Python gateway and Next.js dashboard already have
separate Dockerfiles; the dashboard proxy target is fixed at build time.

## Decision

Publish a backend image and a dashboard image as separate artifacts. Reuse the
backend image for gateway, worker and migration roles. Supply a pull-only Compose
file with external store URLs, real-mode identities, required secrets, migration
ordering, worker health, loopback port bindings and an optional dashboard profile.
Preserve the `gateway:8187` internal address used by the dashboard build.

Provide a source-free archive containing Compose, a blank-secret environment
example, documentation and license. The archive reads from an explicit allowlist,
never a populated `.env`. A manual Docker Hub workflow builds reviewed tags for
amd64/arm64; pushing is an explicit input disabled by default. Published digests
are signed, with build attestations requested. Existing GHCR publishing stays
separate. No workflow is triggered or image published by this local work.

## Consequences

Installation requires Docker plus configuration, with no source build. Gateway and
worker remain independently restartable. Users must supply dedicated compatible
stores and backup the master key and accounting data. Dashboard hosting at a
different internal backend address needs a custom build; runtime proxy
reconfiguration and a combined application image are not part of this change.

Compose and packaging checks run without a daemon. CI adds a fresh-database,
non-demo smoke using local prebuilt images and mock targets only. Local container
build/smoke cannot run while this host's Docker daemon is unavailable; neither
cross-architecture success nor Docker Hub availability is claimed.

## Owner-selected namespace

The user supplied `myselfabii` for Docker Hub. Use it as the environment-example, packaging and workflow default. Namespace selection does not establish registry availability or authorize pushing; publication remains pending.
