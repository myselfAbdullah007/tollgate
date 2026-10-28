# ADR 0002: Redis fast path, PostgreSQL source of truth

Status: accepted, 2026-10-28.

Budget and rate admission must be atomic under concurrency. Redis Lua owns fast admission, in-flight reservations, cache and breakers. PostgreSQL owns configuration and the durable ledger, with monthly range partitions and daily rollups.

Consequences: deployments operate two durable stores. Reconciliation must include unledgered stream events and preserve active reservations; a ledger-only counter reset is unsafe. The zero-infrastructure demo uses SQLite/memory under one process and does not claim distributed semantics.
