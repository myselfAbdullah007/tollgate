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
| TOLLGATE_PORT | Gateway listen port, default 8187 |
| TOLLGATE_API_URL | Next.js server-side proxy target; default `http://127.0.0.1:8187`. Set at production build time |
| TOLLGATE_BOOTSTRAP_FILE | Optional YAML path; applies only on a fresh default workspace |
| TOLLGATE_PRICING_FILE | Optional pricing YAML; default `config/pricing.yaml`, loaded on gateway import |
| OPENAI_API_KEY | Optional global OpenAI credential |
| ANTHROPIC_API_KEY | Optional global Anthropic credential |
| GEMINI_API_KEY | Optional global Google credential |
| TOLLGATE_PRESIDIO_URL / TOLLGATE_KMS_KEY_ID | Reserved optional integrations; nonempty values fail clearly in this release |

Owner email/password create the initial owner record; changing the environment does not reset an existing password. Use a fresh demo database for fixtures, or a reviewed migration/administrative maintenance procedure for identity changes. Stored provider credentials override environment credentials for the selected workspace.

Runtime plans, aliases, keys, customer overrides, and workspace defaults live in the database and are edited through the dashboard/admin API. Bootstrap YAML uses integer micro-USD and exactly the fields validated by the plan/alias API. Price pairs are integer micro-USD per input/output token. Current values are illustrative conservative values, not promised provider quotes; fractional micro-USD billing precision is a roadmap item.

Compose reads `.env` through `--env-file .env`; the service explicitly overrides infrastructure DSNs to its private service network. Host publishing variables are `TOLLGATE_DASHBOARD_PORT`, `TOLLGATE_PORT`, `TOLLGATE_POSTGRES_PORT`, `TOLLGATE_REDIS_PORT`. The internal gateway still listens on 8187 in Compose. Local API listen port can also be customized directly. The two scopes should not be confused.
