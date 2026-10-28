# Getting started

1. Follow the local or Docker commands in README.md. Open http://localhost:3187.
2. In demo mode choose **Use demo credentials**, then sign in. The overview has sample customers, budgets and usage so all concepts are discoverable immediately.
3. Open **Playground**. Preview the prompt containing an email/phone; the preview shows placeholders. Send the request; the streamed response restores original values.
4. Open **Customers**. Search a name/ID, edit a plan or override a budget, or open customer details. Budget alerts in the header lead to customers approaching thresholds.
5. Open **Plans & budgets** to change thresholds and privacy. Open **Model routing** to connect an alias tier to a priced target and fallback.
6. Create a key under **API keys**. Copy it immediately. **Settings & setup** includes an SDK example with the gateway base URL and customer header.
7. To use real models, add a provider credential, verify the illustrative price table, then update a model alias. Provider configuration is not itself an external connectivity test.
8. Inspect **Request logs** for tier, cost, latency, cache, fallback and PII counts. Prompt/answer text is intentionally absent.

The memory/SQLite demo is one-process only. Use the Compose PostgreSQL/Redis/worker deployment to exercise durable event delivery and cross-process atomic limits.
