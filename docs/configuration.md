# Configuration

Copy `.env.example` to `.env`. Never commit a populated `.env`.

| Setting | Default / purpose |
|---|---|
| TOLLGATE_DEMO | false in application; true in example/Compose. Enables public demo credentials, example activity, and demo origin aliases |
| TOLLGATE_DATABASE_URL | `sqlite+aiosqlite:///./tollgate.db` locally; Compose overrides with its PostgreSQL service |
| TOLLGATE_REDIS_URL | Empty means single-process memory. Compose uses its own Redis |
| TOLLGATE_MASTER_KEY | Base64 of exactly 32 random bytes; `make key` generates it. Required outside demo |
| TOLLGATE_ADMIN_EMAIL | `admin@tollgate.local`; initial owner only |
| TOLLGATE_ADMIN_PASSWORD | Required outside demo, minimum 12 characters; initial owner only |
| TOLLGATE_ENABLE_MOCK_PROVIDER | true; disable for a live deployment if desired |
| TOLLGATE_COOKIE_SECURE | false locally; set true behind HTTPS |
| TOLLGATE_ALLOWED_ORIGIN | Dashboard origin, default `http://localhost:3187`; comma-separated origins supported |
| TOLLGATE_MAX_CONCURRENT_REQUESTS | 100 in-flight requests per workspace; range 1–10000 |
| TOLLGATE_PORT | Gateway listen port, default 8187 |
| TOLLGATE_API_URL | Next.js server-side proxy target; default `http://127.0.0.1:8187`. Set at production build time |
| TOLLGATE_BOOTSTRAP_FILE | Optional YAML path; applies only on a fresh default workspace |
| TOLLGATE_PRICING_FILE | Optional pricing YAML; default `config/pricing.yaml`, loaded on gateway import |
| OPENAI_API_KEY | Optional global OpenAI credential |
| ANTHROPIC_API_KEY | Optional global Anthropic credential |
| GEMINI_API_KEY | Optional global Google credential |
| TOLLGATE_PRESIDIO_URL / TOLLGATE_KMS_KEY_ID | Reserved optional integrations; nonempty values fail clearly in this release |

Owner email/password create the initial owner record; changing the environment does not reset an existing password. Use Settings for your own password or `tollgate reset-password` for interactive initial-owner recovery; all affected sessions are revoked. Stored provider credentials override environment credentials for the selected workspace.

Runtime plans, aliases, keys, customer overrides, and workspace defaults live in the database and are edited through the dashboard/admin API. Bootstrap YAML uses integer micro-USD and exactly the fields validated by the plan/alias API. Versioned price pairs are integer micro-USD per million input/output tokens (`unit: micro_usd_per_million_tokens`); settlement rounds the combined charge upward to a whole micro-USD. Legacy per-token config is converted explicitly. Values are illustrative, not verified provider quotes.

Compose reads `.env` through `--env-file .env`; the service explicitly overrides infrastructure DSNs to its private service network. Host publishing variables are `TOLLGATE_DASHBOARD_PORT`, `TOLLGATE_PORT`, `TOLLGATE_POSTGRES_PORT`, `TOLLGATE_REDIS_PORT`. The internal gateway still listens on 8187 in Compose. Local API listen port can also be customized directly. The two scopes should not be confused.

## Business controls

Add `feature` and `environment` to chat request JSON (defaults `general`, `production`); only bounded alphanumeric, underscore and hyphen labels are accepted. Do not place contact details or secrets in these retained metadata tags. Insights & alerts groups their cost; these tags do not isolate budgets or permissions.

Create a usage key under API keys, choose read-only usage access and bind a customer external ID. `GET /v1/usage` with its bearer token returns that customer's budget, spend, reserved amount, remaining allowance and UTC reset. The bound identity takes precedence over a supplied customer header; the key cannot invoke chat.

Owner webhook setup lives in Settings. Save the once-shown signing secret securely and enable delivery only after configuring a receiver. Threshold, degraded and exhausted events are deduplicated by customer/month/type/threshold. Delivery history appears in Insights & alerts. New events follow the current enabled policy; old unconfigured events are not backfilled. See SECURITY.md for signature verification and retry semantics.

The owner account API is `/admin/v1/users`; roles are owner/admin/viewer across the deployment. The console creates accounts; owner PATCH supports role/disable changes with a revision. Workspace-specific membership is deferred. Configuration export and `/configuration/validate` exclude secrets and perform no import. `tollgate validate-config --file config/bootstrap.example.yaml` validates bootstrap YAML offline without applying it.
