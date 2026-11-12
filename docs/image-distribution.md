# Run Tollgate from published images

This deployment uses prebuilt backend and dashboard images. You do not need Python,
Node.js, a compiler, or a checkout of Tollgate's source. You need Docker Engine,
Docker Compose v2 or newer, and reachable PostgreSQL 16 / Redis 7 services dedicated
to Tollgate. Redis must support Lua, Streams, consumer groups, and persistence.
Use a dedicated PostgreSQL database and a dedicated Redis instance; Tollgate uses
deployment-level Redis keys, so sharing a Redis database with another Tollgate
deployment is unsupported. Managed stores are fine when they support these features.

**Publication status:** the owner selected Docker Hub namespace `myselfabii`.
The configured image names are intended release references; this does not mean
either repository or version has been published. Confirm release availability
before running the pull commands.

## Files and images

The deployment archive contains `compose.yml`, `.env.example`, this README, and
the license. All application code arrives inside the images. The backend image
runs three roles: gateway (`serve`), background accounting worker (`worker`), and
one-time migrations (`migrate`). The dashboard has its own image and optional
`dashboard` Compose profile. PostgreSQL and Redis are not started by this file.

Automatic merge builds publish matching `sha-<full-commit>` tags for backend and
dashboard. The example defaults to `myselfabii/tollgate:latest` and
`myselfabii/tollgate-dashboard:latest` for convenience after the first successful
publication. Pin both images to the same commit tag or verified digests for
repeatable production installs. Manual versioned releases remain available. Images are intended for Linux amd64 and arm64;
architecture builds still need a successful release workflow before support is
claimed for a particular release.

## First start

1. Extract the deployment archive into its own directory and enter it. If working
   from source, copy `deploy/compose.images.yml` to `compose.yml` and
   `deploy/.env.images.example` to `.env.example` in an empty directory instead.
2. Copy `.env.example` to `.env` and restrict access: `chmod 600 .env` on Unix.
   Set the two published image references, database and Redis URLs, a private
   owner email, a password of at least 12 characters, and a master key.
   Use single-quoted values in `.env` when a password contains `$`, `#`, or spaces
   so Compose preserves literal characters rather than expanding/interpreting them.
3. Generate the master key with `openssl rand -base64 32` and place its output
   in `TOLLGATE_MASTER_KEY`. Keep it private and backed up. Do not use an example
   or regenerate it on every start: existing encrypted credentials need this key.
4. Configure PostgreSQL access so Tollgate can create its tables, indexes and
   monthly partitions in its own database. Configure Redis persistence and keep
   both stores reachable on a trusted network. URL-encode reserved characters
   in connection-string credentials. `localhost` in a container refers to that
   container, not your laptop or a different container. Use reachable private
   DNS names or attach Tollgate to your existing Docker network as described below.

Start with the dashboard:

```sh
docker compose --env-file .env -f compose.yml --profile dashboard pull
docker compose --env-file .env -f compose.yml --profile dashboard up -d --wait --wait-timeout 180
```

These commands pull images, never build from source. Migrations must succeed
before gateway and worker start. The dashboard waits for gateway health.
Readiness and worker health must still be checked against your external services.
The Compose project is `tollgate`; do not run this alongside a different Tollgate
installation with that same project name on the same Docker host. Choose an
explicit different `-p` name and unused ports if you need another installation,
with its own database and Redis instance.

Open `http://localhost:3187` and sign in with your configured owner account.
The gateway is at `http://localhost:8187`. Both ports bind to loopback by default.
No public demo credentials, demo API key, or seeded demo traffic are enabled.

On a fresh database, the initial aliases still reference mock models. The mock
provider is disabled by default in this deployment. To explore without paid calls,
set `TOLLGATE_ENABLE_MOCK_PROVIDER=true` and recreate the backend services. This
enables mock routing without enabling demo identities or sample accounting data.
For real traffic, configure credentials **and** replace mock targets in Model
routing, review the illustrative prices, and create a gateway API key in the UI.
Saved credentials alone do not switch aliases to a real provider.

For API-only operation omit `--profile dashboard` from pull and up. Keep both image
variables populated because Compose interpolates the entire file, including inactive
profiles. Gateway and worker remain required. API-only configuration and key creation
use the session-authenticated admin API; the dashboard does not have to run.

## Connect your application

Point your application's OpenAI-compatible client at `http://localhost:8187/v1`
when it runs on the same host, or at the gateway's reachable private/TLS URL.
Use a gateway key created for your workspace and send `X-Tollgate-Customer` or
the request's `user` field. Requests use your configured aliases such as `smart`.
Keep gateway and provider keys on your application's/server side.

An application container sharing the Compose network can call
`http://gateway:8187/v1`. A different Docker network needs explicit connectivity;
its own `localhost:8187` will not reach Tollgate. For an existing shared Docker
network, create `network.override.yml` alongside `compose.yml`:

```yaml
networks:
  tollgate:
    external: true
    name: your-existing-private-network
```

Add `-f network.override.yml` after `-f compose.yml` to each Compose command.
The network must already exist, and its PostgreSQL/Redis hostnames must match the
URLs you provide. Keep the service name `gateway` and its internal port `8187`:
the published dashboard's proxy is built for `http://gateway:8187`. Changing a host
published port is supported; setting a runtime `TOLLGATE_API_URL` on this dashboard
image does not rewrite its build-time proxy. A different internal upstream needs
a custom dashboard build. Workspace selection remains administrative scope, not
workspace-specific user authorization.

For remote access configure TLS with your reverse proxy, set
`TOLLGATE_ALLOWED_ORIGIN` to the exact browser origin, and set
`TOLLGATE_COOKIE_SECURE=true`. Attach the reverse proxy to the appropriate network
or intentionally adjust `TOLLGATE_BIND_ADDRESS`. Do not expose database/Redis
services publicly. Secure cookies should not be enabled for plain HTTP local use.

## Inspect and upgrade

```sh
docker compose --env-file .env -f compose.yml --profile dashboard ps
curl --fail http://localhost:8187/readyz
docker compose --env-file .env -f compose.yml logs --tail=100 gateway worker migrate
```

Back up PostgreSQL, Redis persistence, and the encryption master key before an
upgrade. Change both image references to the reviewed new version, pull, and stop
only this Tollgate application before applying migrations:

```sh
docker compose --env-file .env -f compose.yml --profile dashboard pull
docker compose --env-file .env -f compose.yml --profile dashboard stop dashboard gateway worker
docker compose --env-file .env -f compose.yml up --force-recreate --no-deps --exit-code-from migrate migrate
docker compose --env-file .env -f compose.yml --profile dashboard up -d --wait --wait-timeout 180
```

If migration fails, leave gateway/worker stopped and inspect the migration logs.
An image rollback does not reverse a schema migration; follow the release-specific
recovery plan. Do not reset other projects or remove external-store data to repair
an upgrade. Counter recovery needs coordinated stores and preserves in-flight
reservations. High-volume retention and independent production review remain
documented release limitations.

To stop the application, use the same Compose file and profile with `stop`.
PostgreSQL and Redis remain externally owned and are untouched. Do not use global
Docker cleanup. Changing `.env` owner credentials does not reset an existing
account; use the documented self-service/password-recovery tools.

## Automatic publication after PR merges

CI checks pull requests targeting `main` and runs again on the integrated `main`
commit after a merge. After distribution checks, backend tests, dashboard checks
and the Compose/image smoke all pass, CI confirms the exact commit belongs to a
merged PR targeting `main` and calls the reusable **Docker Hub images** workflow.
Direct main pushes, PR checks, failed CI, and manual CI runs do not automatically
publish. Merge commits, squash merges and rebase merges are recognized through
GitHub's associated-PR API and `merge_commit_sha`.

The workflow checks out the exact tested SHA, builds backend and dashboard for
Linux amd64/arm64, publishes `sha-<full-commit>` tags under `myselfabii`, requests
SBOM/provenance attestations and signs image digests with GitHub OIDC. Both image
build/sign jobs and the release bundle must succeed before a separate promotion
job updates `latest` for both images. An older run checks current main and skips
latest promotion if newer code has landed. The two repositories cannot be updated
as one registry transaction; a promotion failure can temporarily leave different
latest versions. Pin matching commit tags for reproducible deployments.

Configure these repository Actions secrets before the first publishing run:

- `DOCKERHUB_USERNAME`: the Docker Hub login with access to the `myselfabii` namespace.
- `DOCKERHUB_TOKEN`: a Docker Hub access token allowed to write both `tollgate`
  and `tollgate-dashboard` repositories. Keep the token in GitHub secrets.

The workflow fails clearly when publication credentials are missing. Configuring
this workflow does not create Docker Hub credentials or establish that a release
has been published. The existing GHCR workflow remains separately manual.

## Packaging and manual releases

From the source repository, `make distribution-check` validates Compose without a
daemon. `make distribution-bundle` creates `dist/tollgate-deployment.tar.gz` using
`latest`. For an exact merge build or manual stable release:

```sh
.venv/bin/python scripts/package_distribution.py --image-tag sha-0123456789abcdef0123456789abcdef01234567
.venv/bin/python scripts/package_distribution.py --version 0.2.0
```

The SHA above is an illustration, not an available image. Use the actual published
commit. These flags are mutually exclusive; a namespace override is supported.
Packaging reads only the example template and never copies a populated `.env`,
application source, databases or credentials.

The **Docker Hub images** workflow also supports manual dispatch from an existing
reviewed `vMAJOR.MINOR.PATCH` tag. Leave `publish=false` for a build-only run; set it
to true to publish version and major.minor tags. Manual versioned runs do not move
`latest`. Do not reuse a stable version tag to represent each main merge.

Automatic publication uploads a `tollgate-deployment-release` Actions artifact
whose environment example pins both images to that exact commit tag. Ordinary CI
also produces a `tollgate-deployment` artifact with default image references.
These artifacts are not automatic public GitHub Release downloads. Share a release
archive and actual published references after the workflow succeeds. Docker Hub
credentials are publishing credentials, never runtime application settings.
