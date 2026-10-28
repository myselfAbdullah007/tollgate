# ADR 0003: Integer micro-USD

Status: accepted, 2026-10-28.

Binary floating-point accumulations can drift and make budget comparisons ambiguous. All balances, reservations, settlement costs and database money columns use integer micro-USD. UI USD fields convert once at the administrative boundary.

Consequences: arithmetic and concurrency assertions are exact at the configured precision. Per-token prices currently use whole micro-USD and therefore cannot exactly represent every fractional provider rate. Values in the example table are conservative illustrations; fractional-rate precision is tracked before a billing-grade release. Display conversion is not used for admission.
