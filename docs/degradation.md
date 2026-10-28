# Budgets and graceful degradation

A customer's budget is their override, if present, otherwise the assigned plan's monthly budget. Billing periods use UTC calendar months. Money is integer micro-USD. Settled spend plus active reservations determine utilization.

Plans default to Tier 1 at 80% and Tier 2 at 95%. An alias defines target chains per tier. Thresholds choose the highest crossed tier, clamped to the alias's available tiers. An alias with `allow_degrade: false` always uses Tier 0. Admission still enforces its hard budget; quality locks are not unlimited spend.

For a selected tier, the reservation ceiling uses the most expensive target's input and maximum output cost. Input estimation uses a conservative UTF-8 byte count; output reserves four times the requested token ceiling to cover the mock/byte fallback. This is deliberately conservative and may reject requests close to a cap even if their eventual charge would be small. No floating-point amount is used for admission or settlement.

Redis checks the balance, chooses the tier and reserves the estimate atomically. Fifty concurrent requests cannot all observe the same unreserved balance. A successful request settles actual token usage and releases the reservation. `allow_overage` adds the explicit plan overage cap; it never means unlimited use.

Fallback retries within the selected tier on rate limits, timeout or eligible upstream errors before streaming begins. Five recent failures open the circuit for 30 seconds. A provider outage does not silently select another tier. An interrupted stream produces an error event and is conservatively accounted, without switching provider mid-answer.

Responses expose `X-Tollgate-Tier`, `X-Tollgate-Model-Served`, `X-Tollgate-Budget-Remaining-Usd`, `X-Tollgate-Cache`, `X-Request-Id`. Remaining budget is a conservative balance after reservation, not a provider invoice. Logs include final settled costs.
