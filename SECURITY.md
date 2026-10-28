# Security

## Reporting

This repository has not been published and does not yet have an owner-supplied private disclosure address. Do not invent one or file sensitive details in a public issue. Before publishing, the repository owner must enable private vulnerability reporting or supply a private security contact. Publication remains a tracked release task.

## Supported version

0.1 is early-stage software for local evaluation and controlled self-hosted trials. It has automated security boundary tests, not an independent audit or compliance certification.

## Controls

Gateway keys contain 32 cryptographically random bytes and are SHA-256 hashed at rest. New keys are returned once; revocation reads authoritative state immediately. Passwords use Argon2. Session cookies contain random tokens, are httpOnly and SameSite=Lax; the database stores only their SHA-256 hash and expiry. Production deployments must enable secure cookies behind TLS.

Administrative writes validate the browser origin and require `X-Tollgate-Admin: 1`. CORS allows configured origins only. Dashboard sessions authorize the whole deployment; do not offer this console as isolated tenant accounts. Provider credentials use AES-256-GCM with a fresh nonce and authenticated context. Master keys live outside the database. Provider credentials are never returned after storage.

Vaults are request-local. Prompt and response text are excluded from metadata logs; Redis events/cache contain no vault. Deterministic cache is disabled in privacy-off mode. Regex/checksum redaction has false positives and false negatives; it does not protect names/addresses or all regional identifiers. Presidio/KMS settings fail explicitly because those optional integrations are not implemented.

## Deployment practice

Disable demo mode before real traffic. Set a private owner password, master key, database password and allowed HTTPS origin. Demo mode uses public fixture credentials and a fixed demonstration encryption key when none is set; never expose it publicly. Default Compose host mappings are loopback-only. Put the dashboard/gateway behind a trusted TLS proxy for remote access; restrict database, Redis and metrics networking. Environment credentials remain sensitive even when stored credentials are encrypted.

Review model availability and prices before live traffic. An application budget is an operational control based on configurable estimates, not a contractual guarantee about a provider invoice. Interrupted streams may be conservatively charged. A simultaneous loss of Redis/AOF before ledger delivery can lose unpersisted events; back up both durable stores and test restore procedures.

## Known limitations

No SSO, independent tenant dashboard identity, full compliance workflow, WAF, secret rotation automation, KMS, NER, distributed tracing, or comprehensive data-classification guarantee. Metadata includes customer external IDs; do not use sensitive contact information as those identifiers. Operator-supplied labels are metadata and are retained. Review retention for ledger partitions, Redis events, caches and backups.
