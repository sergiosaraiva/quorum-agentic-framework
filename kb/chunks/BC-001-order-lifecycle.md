---
chunk_id: BC-001
title: Order lifecycle states
topics: [orders, lifecycle]
links: [BC-002, BC-003]
sources: ["example: invented"]
example: true
---
EXAMPLE CHUNK (invented "Acme Orders" domain; replace with your product knowledge).

An order has six states: `draft`, `placed`, `paid`, `shipped`, `closed` and `cancelled`. A normal order moves through the first five in that order. A customer edits a `draft` freely. Placing an order freezes its lines and prices. An order becomes `paid` when the sum of confirmed payments covers the order total. It becomes `shipped` when at least one shipment leaves the warehouse, and `closed` when every line is delivered or refunded and the invoice is settled.

An order can be cancelled only in `draft` or `placed`; cancelling moves it to `cancelled`. After payment, a customer undoes an order through a refund, never through cancellation. State changes are recorded with a timestamp and the acting user.
