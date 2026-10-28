# Security

## Reporting

This repository has not been published and does not yet have an owner-supplied private disclosure address. Do not invent one or file sensitive details in a public issue. Before publishing, the repository owner must enable private vulnerability reporting or supply a private security contact. Publication remains a tracked release task.

## Supported version

0.2 is early-stage software for local evaluation and controlled self-hosted trials. It has automated security boundary tests, not an independent audit or compliance certification.

## Controls

Gateway keys contain 32 cryptographically random bytes and are SHA-256 hashed at rest. New keys are returned once; revocation reads authoritative state immediately. Passwords use Argon2. Session cookies contain random tokens, are httpOnly and SameSite=Lax; the database stores only their SHA-256 hash and expiry. Production deployments must enable secure cookies behind TLS.

Administrative writes validate the browser origin and require `X-Tollgate-Admin: 1`. CORS allows configured origins only. Dashboard sessions authorize the whole deployment; do not offer this console as isolated tenant accounts. Provider credentials use AES-256-GCM with a fresh nonce and authenticated context. Master keys live outside the database. Provider credentials are never returned after storage.

Vaults are request-local. Prompt and response text are excluded from metadata logs; Redis events/cache contain no vault. Deterministic cache is disabled in privacy-off mode. Regex/checksum redaction has false positives and false negatives; it does not protect names/addresses or all regional identifiers. Presidio/KMS settings fail explicitly because those optional integrations are not implemented.

## Deployment practice

Disable demo mode before real traffic. Set a private owner password, master key, database password and allowed HTTPS origin. Demo mode uses public fixture credentials and a fixed demonstration encryption key when none is set; never expose it publicly. Default Compose host mappings are loopback-only. Put the dashboard/gateway behind a trusted TLS proxy for remote access; restrict database, Redis and metrics networking. Environment credentials remain sensitive even when stored credentials are encrypted.

Review model availability and prices before live traffic. An application budget is an operational control based on configurable estimates, not a contractual guarantee about a provider invoice. Interrupted streams may be conservatively charged. A simultaneous loss of Redis/AOF before ledger delivery can lose unpersisted events; back up both durable stores and test restore procedures.

## Known limitations

No SSO, independent tenant dashboard identity, full compliance workflow, WAF, unattended secret rotation, KMS, NER, distributed tracing, or comprehensive data-classification guarantee. Metadata includes customer external IDs; do not use sensitive contact information as those identifiers. Operator-supplied labels are metadata and are retained. Review retention for ledger partitions, Redis events, caches and backups.

## 0.2 operational controls

All admin writes retain session/CSRF enforcement. Viewer accounts can perform their own password/session operations and privacy preview, but cannot write configuration. Owner alone manages accounts and webhook secrets. Roles apply across the deployment; selecting a workspace does not authorize a separate tenant identity.

Webhook destinations require public HTTPS port 443 with no URL credentials; every resolved address is checked, the connection is pinned, original Host/TLS server name retained, redirects disabled. Receivers verify `t=<unix>,v1=<hex HMAC-SHA256>` against `timestamp + "." + raw_body`, enforce their own freshness window and deduplicate the body event id. Secrets are encrypted and shown once. Delivery is bounded to five attempts; operators should inspect failed delivery history.

Use `tollgate reset-password --help` for interactive recovery. For master-key rotation, stop only Tollgate gateway/worker, retain the old key securely, supply current `TOLLGATE_MASTER_KEY` and new `TOLLGATE_NEW_MASTER_KEY`, run `tollgate rotate-master-key --maintenance`, update the running services' master key and restart them. The database re-encryption is transactional; back up the database and rehearse recovery first. Do not rotate while old-key processes are running. No production rotation was performed during development.

Ingress is limited to 300 KB and 15 seconds idle between body chunks. Per-workspace concurrent request defaults to 100. Pricing/model configuration remains operator-reviewed; this release does not establish live provider billing accuracy or workload capacity. Recovery fencing reduces single-store accounting risk; simultaneous loss of both accounting stores still requires operator response.
