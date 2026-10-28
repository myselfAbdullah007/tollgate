# ADR 0004: Atomic settlement and Redis Streams

Status: accepted, 2026-10-28.

Logging should not compete with provider latency or disappear on a gateway restart. Use one Lua operation to release the reservation, charge spend and append a metadata event. Consume with a group; acknowledge only after an idempotent log/rollup transaction. Reclaim unacknowledged deliveries after worker restart.

Consequences: gateway/worker share one image and different commands. Redis persistence and backups matter. Events are retained, so acknowledged-event trimming requires a deliberate retention policy; unbounded growth is a known capacity limit. Worker reads up to 500 events but commits individually for simple failure/replay semantics.
