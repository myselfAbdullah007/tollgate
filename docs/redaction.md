# Reversible redaction

A request-scoped vault detects sensitive values and swaps them for category placeholders in order of appearance. Repeated values share the same token. All text parts and tool argument strings are transformed before provider transport. Literal placeholder-looking input is neutralized to avoid collisions.

```
User:      Draft to ali@example.com; call 0300-1234567.
Provider:  Draft to [EMAIL_1]; call [PHONE_1].
Provider:  Here is your draft for [EMAIL_1].
User:      Here is your draft for ali@example.com.
```

Detectors cover email, selected phone formats, Luhn-checked cards, checksum-valid IBAN, Pakistani CNIC, Japanese My Number, IPv4 and common provider/repository/cloud secret patterns. Overlap selection favors validated high-priority detectors. Names, addresses, IPv6 and exhaustive regional formats are not covered. Do not interpret redaction as a compliance certification.

Modes: `off` sends text unchanged; `mask` replaces sensitive values irreversibly; `reversible` restores vault tokens in answers; `block` rejects sensitive requests. Specific block categories may be configured independently, with CARD blocked by default.

The vault never enters logs, Redis, PostgreSQL or cache. Metadata logs contain only category counts. No prompts or answers are retained. A redacted cache result is restored with the current request's vault, so structurally identical prompts with different email values may safely share an entry. Cache is disabled when privacy is off. Unknown model-invented placeholders become `[redacted]`.

Streaming restoration maintains a bounded buffer from an incomplete `[` onward and emits safe text before it. When the token closes it is restored once. Ordinary bracket text is preserved. Content and individual tool-call argument streams each have a separate buffer. Hypothesis tests generate arbitrary chunk splits and compare reconstructed output with non-streaming restoration. Provider output can still invent personal information unrelated to the request; this mechanism is not an output moderation or data-classification engine.
