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

Redis AOF is configured with `appendfsync always` in the provided Compose stack. Settlement removes the request reservation, increments spend and XADDs its metadata event in one Lua execution. Pending events survive worker restarts. The worker claims stale pending events after 30 seconds and acknowledges after its ledger/rollup transaction. Event replay is idempotent.

On startup and every three minutes the worker reconstructs settled counters from a repeatable-read ledger snapshot plus stream events absent from that snapshot. A short global lease pauses new budget reservations/settlements, not provider generation. The commit checks lease identity atomically; expired snapshots cannot overwrite new charges. Active reservation hashes are untouched. Requests wait briefly; the lease auto-expires if the worker crashes. Current reconciliation loads ledger rows into memory and is intended for early-stage scale; large installations need SQL aggregation and bounded event retention.

Reservations carry 180-second deadlines; request provider work has a 120-second total ceiling. A crashed process's reservation is removed on a later admission. An interrupted stream is conservatively charged at its reserved estimate, marked as estimated/error, rather than assuming the provider did no work. Deterministic privacy-enabled cache hits are checked before reservation and can be served at zero cost when budget is exhausted, while remaining inside the configured permitted tier range.

Back up PostgreSQL **and** the Redis AOF volume. Complete Redis data loss after provider billing but before ledger delivery cannot be reconstructed exactly. Never attach an old Redis volume to a different ledger and assume balances are valid. Restore both stores together, start migration/worker, inspect pending events and counters, then admit traffic.

## Secrets and provider changes

Use `make key` to generate a master key. Store it in your secret manager or protected environment. Backups without the master key cannot decrypt stored credentials. Use the transactional `tollgate rotate-master-key --maintenance` command with current/new keys, after stopping only Tollgate gateway/worker; see SECURITY.md. Do not replace the environment key alone. Environment provider keys are fallbacks, and stored per-workspace credentials take precedence.

The provider screen reports whether a key is configured; it does not claim an external health check was made. Test credentials/routing through the playground with a controlled budget after reviewing prices. No automatic paid health probes are performed.

## Observability

`/healthz` reports process availability. `/readyz` checks database and Redis connectivity. `/metrics` exposes process-level gateway request/error counters. The optional observability overlay adds private-loopback Prometheus and Grafana. Log metadata never contains prompt/answer text. Request IDs connect headers with ledger rows. Detailed stage tracing and latency histograms are future work.

Retained Redis events currently grow with traffic; do not trim pending events. Add a reviewed acknowledged-event retention procedure before sustained high-volume deployment.

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

Migration `0002` adds the authoritative API-key hash lookup index without rewriting stored credentials. Back up both stores before upgrades. The current worker retains events and scans history for reconciliation; representative capacity testing, checkpointing, batching and a reviewed retention policy remain pending.
