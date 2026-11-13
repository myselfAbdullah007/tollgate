# Operating Tollgate

## Start, inspect, stop

```sh
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml ps
curl --fail http://localhost:8187/readyz
docker compose -f deploy/docker-compose.yml logs --tail=100 gateway worker
# Stop only Tollgate; volumes are retained:
docker compose -f deploy/docker-compose.yml stop
```

Never use global Docker cleanup or stop unrelated services to free a port. Check published ports and choose Tollgate-specific overrides instead. `make dev` owns only its API/dashboard children. Do not run `down -v` on a valuable ledger.

## Migrations

`tollgate migrate` runs packaged Alembic upgrades through the configured async engine. Revision `0001` creates configuration records, a PostgreSQL monthly range-partitioned request ledger, and usage rollups. A PostgreSQL advisory lock serializes startup migration attempts. The gateway also runs the idempotent migration on local startup. Compose requires the migration job to finish successfully before gateway/worker startup.

Monthly partitions are created lazily by the writer under an advisory lock. Dropping an old partition deletes its ledger permanently; adopt a retention policy only after considering audit and counter rebuilding. A downgrade is deliberately refused by the initial revision, because it would destroy accounting data.

## Durable accounting and recovery

Redis AOF is configured with `appendfsync always` in the provided Compose stack. Settlement removes the request reservation, increments spend and XADDs its metadata event in one Lua execution. Pending events survive worker restarts. The worker claims stale pending events after 30 seconds and atomically acknowledges/deletes each entry after its ledger/rollup transaction. Event replay is idempotent.

On startup and every three minutes the worker captures at most 10,000 delivery events before a repeatable-read SQL snapshot, reconstructs settled counters from transactional daily rollups, and adds captured events absent from the ledger snapshot. A short global lease pauses new budget reservations/settlements, not provider generation. The commit checks lease identity atomically; expired snapshots cannot overwrite new charges. Active reservation hashes are untouched. Requests wait briefly; the lease auto-expires if the worker crashes. Reconciliation queries only captured event identities, with SQL aggregation over daily rollups. Larger backlogs defer rebuilding while delivery drains. Aggregate output still grows with customer-months, so workload capacity must be measured.

Reservations carry 180-second deadlines; request provider work has a 120-second total ceiling. A crashed process's reservation is removed on a later admission. An interrupted stream is conservatively charged at its reserved estimate, marked as estimated/error, rather than assuming the provider did no work. Deterministic privacy-enabled cache hits are checked before reservation and can be served at zero cost when budget is exhausted, while remaining inside the configured permitted tier range.

Back up PostgreSQL **and** the Redis AOF volume. Complete Redis data loss after provider billing but before ledger delivery cannot be reconstructed exactly. Never attach an old Redis volume to a different ledger and assume balances are valid. Restore both stores together, start migration/worker, inspect pending events and counters, then admit traffic.

## Secrets and provider changes

Use `make key` to generate a master key. Store it in your secret manager or protected environment. Backups without the master key cannot decrypt stored credentials. Use the transactional `tollgate rotate-master-key --maintenance` command with current/new keys, after stopping only Tollgate gateway/worker; see SECURITY.md. Do not replace the environment key alone. Environment provider keys are fallbacks, and stored per-workspace credentials take precedence.

The provider screen reports whether a key is configured; it does not claim an external health check was made. Test credentials/routing through the playground with a controlled budget after reviewing prices. No automatic paid health probes are performed.

## Observability

`/healthz` reports process availability. `/readyz` checks database and Redis connectivity. `/metrics` exposes process-level gateway request/error counters, latency histograms, fallback attempts, uncertain costs, cache failures and accounting recovery/failure counters. Redis deployments also expose worker health, delivery backlog, retained entries and metric availability. The optional observability overlay adds private-loopback Prometheus and Grafana. Log metadata never contains prompt/answer text. Request IDs connect headers with ledger rows. Detailed stage tracing remains future work. Histograms include full request/stream lifetime, not isolated gateway overhead. Counter metrics reset with each gateway process; scrape each process separately when scaling.

Committed Redis events are deleted after SQL delivery. Legacy committed entries are retired in batches of 500. Never apply arbitrary MAXLEN trimming: pending entries must survive until committed. This private ledger stream supports one ledger consumer group, not external fan-out consumers.

## Docker hosts without Buildx

The usual Compose build uses Docker Buildx. On a machine without that plugin, use the legacy builder for these Dockerfiles, then start the already built images:

```sh
DOCKER_BUILDKIT=0 docker compose -f deploy/docker-compose.yml build gateway dashboard
docker compose -f deploy/docker-compose.yml up -d --no-build
```

No host plugin installation is required for this fallback. Both images were exercised with this path in the local validation environment.

## Accounting and alert operations in 0.2

Settings shows readiness, worker heartbeat and pending delivery state. Settlement retries idempotently; a fallback SQL ledger transaction records a recovery marker and fences new requests for the workspace until reconciliation. Reconciliation clears only captured markers after a lease-validated counter update, retaining in-flight reservations. Simultaneous loss of both Redis and SQL still requires operator recovery. Malformed stream records are quarantined using source id/error metadata only.

Webhook delivery runs separately from ledger ingestion, checks only public HTTPS destinations, signs each body and retries up to five times. Receivers must deduplicate event ids. Inspect failed alerts under Insights & alerts. Webhooks are disabled until an owner configures/enables them; no real destination was contacted during tests.

Migration `0002` adds the authoritative API-key hash lookup index without rewriting stored credentials. Back up both stores before upgrades. The new worker uses rollups and bounded delivery snapshots; PostgreSQL/Redis verification and representative capacity testing remain mandatory before deployment. Further incremental rebuilds and ledger batching remain future work.

## Production preflight and alerts

Run `tollgate check-production` against the intended environment. It checks demo/mock
flags, PostgreSQL/Redis configuration, secure cookies, HTTPS origins and owner/master
key configuration without printing values or contacting providers. Exit 1 means at
least one configuration gate failed; exit 0 is not a live deployment certification.

The observability overlay loads `deploy/prometheus/alerts.yml`. Rules cover scrape
outages, worker health, backlog, accounting failures and uncertain provider cost.
Thresholds are initial operator defaults, not measured SLOs. Configure and test an
Alertmanager/paging destination separately; no external messages are sent by setup.

Upgrade gateway and worker together during maintenance. Old SQL-first reconciliation
is incompatible with concurrent deletion by the new worker; mixed-version workers
are unsupported. Back up SQL and Redis first and verify rollup integrity. The newest
validation record identifies whether real infrastructure checks passed.
