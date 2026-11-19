---
chunk_id: BC-005
title: Money amounts and rounding
topics: [billing, orders]
links: [BC-002, BC-003]
sources: ["example: invented"]
example: true
---
EXAMPLE CHUNK (invented "Acme Orders" domain; replace with your product knowledge).

All amounts are decimal values with two fraction digits, stored together with an ISO 4217 currency code. An order has exactly one currency; lines in another currency are rejected. Tax is computed per line and rounded half away from zero to two digits; the order total is the sum of the rounded line totals, never a rounding of the unrounded sum.

Refund and credit note amounts use the same rounding rule, so a full refund of every line equals the original invoice total exactly.
