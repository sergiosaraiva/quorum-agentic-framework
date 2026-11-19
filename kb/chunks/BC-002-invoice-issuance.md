---
chunk_id: BC-002
title: Invoice issuance and numbering
topics: [invoices, billing]
links: [BC-001, BC-003, BC-004]
sources: ["example: invented"]
example: true
---
EXAMPLE CHUNK (invented "Acme Orders" domain; replace with your product knowledge).

One invoice is issued per order when the order reaches `paid`. The invoice copies the order lines, unit prices, tax rates and currency at that moment; later price changes never alter an issued invoice. Invoice numbers are sequential per calendar year in the form `INV-2026-000123`, with no gaps.

An issued invoice is immutable. A correction is made by issuing a credit note that references the original invoice number and carries negative amounts. Every credit note also receives its own number from the same sequence.
