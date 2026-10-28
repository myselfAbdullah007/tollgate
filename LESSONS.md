# Lessons and regression notes

- Browser origins matter even locally: localhost and 127.0.0.1 are distinct. Demo mode accepts both explicitly; production uses configured origins. Do not remove CSRF origin checks to fix a local mismatch.
- A placeholder may split at any byte-independent text chunk boundary. Content and tool-argument streams need separate restoration buffers. Property tests catch failures that hand-picked splits miss.
- Cache only redacted responses and restore with the current request's vault. Cross-customer cache reuse must never reuse the original caller's email. Disable cache entirely when privacy mode is off.
- Charge and event publication belong in one Redis transaction/script. Acknowledgment belongs after the ledger/rollup transaction. Replayed events must be idempotent.
- Rebuilding spend from only the ledger can erase charges waiting in the stream. Include unledgered events and freeze settlement during the snapshot; never reset active reservations.
- A reservation TTL must exceed total allowed upstream work, including fallback attempts. Individual socket idle timeouts alone are insufficient.
- A successful TypeScript build does not run ESLint. Exercise persisted UI behavior in a real browser; a page that renders is not enough.
- Generic `[role=alert]` selectors include Next.js's empty route announcer. Assert the application's error banner rather than treating every framework announcement as an error.
- Sandboxing may block asynchronous SQLite wakeups or Chromium socket operations. Escalate the relevant test command after the actual failure; do not mark it passing or modify unrelated services.
- Bundle fonts so a self-hosted administrative console does not depend on a third-party stylesheet request.
