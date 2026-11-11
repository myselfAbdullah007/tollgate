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

Use matching explicit versions for backend and dashboard, for example
`myselfabii/tollgate:0.2.0` and
`myselfabii/tollgate-dashboard:0.2.0`, once published. Prefer version tags or
verified digests over moving tags. Images are intended for Linux amd64 and arm64;
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

## Publisher instructions

From the source repository, `make distribution-check` validates Compose without a
daemon. `make distribution-bundle` creates `dist/tollgate-deployment.tar.gz` with
the owner-selected `myselfabii` image references. To choose a release version:

```sh
.venv/bin/python scripts/package_distribution.py --namespace myselfabii --version 0.2.0
```

The namespace can be overridden with another lowercase namespace. This command reads only the example template;
it never copies a populated `.env`, application source, databases or credentials.

The manual **Docker Hub images (manual)** GitHub Actions workflow builds both
images for amd64/arm64 from an existing reviewed release tag. The tag must include
this packaging work. Configure repository secrets `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN`; the token needs write access to both image repositories.
Choose your namespace and tag, leaving **publish=false** for a build-only run.
With explicit release approval, **publish=true** pushes version and major.minor
tags, attaches build attestations, and signs image digests using GitHub OIDC.
There is no automatic push on a branch commit and no implicit `latest` tag.
Repository owners should restrict who can trigger releases and review the selected
tag before dispatch. The existing GHCR workflow remains separate.

The workflow also uploads the deployment archive as a GitHub Actions artifact;
it does not automatically create a public GitHub Release download. Give users the
archive and the actual published image names/digests after a successful release.
Docker Hub credentials are publication credentials, never application runtime
environment variables. No image publication is performed by generating this bundle.
