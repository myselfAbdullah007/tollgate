# ADR 0001: Built-in deployment authentication

Status: accepted, 2026-10-28.

A self-hosted gateway should not require an external identity platform just to evaluate budgets. Use an Argon2 owner account and random, hashed, httpOnly session tokens. Protect browser writes with origin checks and a custom request header. Roles support owner/admin/viewer behavior.

Consequences: smaller installation and no external identity dependency. Administrative identity is shared across the deployment; workspace selection is not tenant login isolation. SSO, user administration and per-tenant identity belong to later scope. Demo credentials are public and must never be used on a public instance.
