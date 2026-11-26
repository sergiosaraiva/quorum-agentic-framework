---
chunk_id: BC-004
title: Partial shipments
topics: [orders, shipping]
links: [BC-001, BC-002, BC-003]
sources: ["example: invented"]
example: true
---
EXAMPLE CHUNK (invented "Acme Orders" domain; replace with your product knowledge).

An order may be fulfilled in several shipments when stock is split across warehouses. Each shipment lists the order lines and quantities it carries; the sum over all shipments never exceeds the ordered quantity. The order shows `shipped` after the first shipment leaves and `closed` only after the last one is delivered.

The invoice is issued once per order, not once per shipment, so partial shipments do not create extra invoices. The 30-day refund window of each line starts at the delivery date of the shipment that carried that line.
