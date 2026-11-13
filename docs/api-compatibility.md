# Supported gateway contract

This is a text Chat Completions subset, not an unrestricted proxy of every
provider API. Unknown top-level request options return HTTP 422 before admission
or provider work. This also applies to the administrative playground endpoint.

| Field / operation | Contract |
| --- | --- |
| `POST /v1/chat/completions` | Text messages, one normalized answer, optional function tools and SSE |
| `GET /v1/models` | Configured routing aliases, not a provider model catalog |
| `model` | A configured Tollgate alias |
| `messages` | System/developer/user/assistant/tool; strings or text parts only |
| `max_tokens` | 1–8192; default 512; the supported output limit |
| `temperature` | 0–2; exact caching eligible only at 0 with privacy enabled |
| `stream` | Default false; errors after streaming starts never switch providers |
| `stream_options.include_usage` | Final usage event only when true; requires `stream=true`; unknown stream options rejected |
| `tools`, `tool_choice` | Function tools, translated by the selected adapter; provider/model capability must be verified separately |
| `user`, `X-Tollgate-Customer` | Customer identity; header takes precedence; use opaque IDs rather than contact information |
| `feature`, `environment` | Reporting tags only; no separate access control or budget boundary |
| `response_format`, `max_completion_tokens`, `seed`, `n`, other unlisted top-level options | Rejected with HTTP 422; never silently discarded |
| Responses API, embeddings, images, audio | Not implemented |

An example usage-enabled stream:

```json
{
  "model": "smart",
  "messages": [{"role": "user", "content": "Draft a brief update"}],
  "max_tokens": 128,
  "stream": true,
  "stream_options": {"include_usage": true}
}
```

Existing clients using unsupported options must remove them or wait for explicit
support. Do not substitute `max_tokens` for a provider-specific reasoning-token
option without validating that model's semantics. Nested tool JSON schemas are
passed through; this document does not promise every provider accepts every schema.

## Cost semantics

Admission reserves the sum of conservative estimates for all targets in the
chosen fallback tier. This is intentionally stricter than reserving only the most
expensive single target: a failed attempt may have done billable work before a
fallback succeeds. The routing tier is still selected atomically; fallback never
changes it. Larger chains may now require a larger available budget.

Confirmed local/pre-dispatch failures and HTTP 4xx rejections have no inferred
generation charge. Timeouts after dispatch, ambiguous transport/server failures,
empty pre-stream responses, cancellation, and interrupted streams retain an
estimated charge for the affected attempt. Successful fallback adds its usage
charge to earlier uncertain attempts. Cached responses remain free.

Ledger `uncertain_cost` is integer micro-USD included in `cost`, not an additional
charge. `cost_basis` is `conservative`, `estimated`, `reported`, `cache`, or
`unbilled`. Uncertainty marks `tokens_estimated=true`. These are operational
budget charges, not verified provider invoices; no automatic invoice correction
or customer billing collection is implemented. Configured prices still require
operator review. Cache write failures do not discard paid successful responses.
