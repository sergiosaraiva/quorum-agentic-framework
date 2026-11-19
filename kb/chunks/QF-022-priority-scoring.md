---
chunk_id: QF-022
title: Slice priority scoring formula
topics: [slices, planning]
links: [QF-020, QF-021]
sources: ["docs/slices/IMPLEMENTATION-GUIDE.md", "docs/concepts/06-vertical-slices-and-planning.md", "docs/slices/INDEX.md"]
---
Quorum computes the priority of a vertical slice instead of guessing it. The formula, in `docs/slices/IMPLEMENTATION-GUIDE.md`, is:

priority = (2 x Value + 2 x Urgency + Unblocks) / Effort

Value, Urgency and Effort are integers from 1 to 5; Unblocks is an integer from 0 to 5. Value is business benefit. Urgency is the cost of delay. Unblocks is how many other slices wait on this one. Effort is the relative size, so a larger effort lowers the priority.

The next slice to build is the one with the highest priority among slices that are `Ready` and whose hard dependencies are all `Done`. Ties go to the slice that unblocks more. Any exception to "dependencies first" is a recorded decision, not a habit.

Worked example with the invented Acme Orders slices of `docs/slices/INDEX.md`: VS-001 Orders (create and list) with Value 5, Urgency 5, Unblocks 3 and Effort 3 scores (10 + 10 + 3) / 3 = 7.67. VS-002 Invoices with 4, 3, 2 and 3 scores (8 + 6 + 2) / 3 = 5.33. VS-004 Order search with 3, 2, 0 and 2 scores (6 + 4 + 0) / 2 = 5.00. VS-003 Refunds with 3, 2, 1 and 5 scores (6 + 4 + 1) / 5 = 2.20. VS-001 goes first; after it is `Done`, VS-002 outranks VS-004, and VS-003 waits for VS-002.

The scores sit in columns of the status table in `docs/slices/INDEX.md`. Inputs are re-scored when scope changes, and a slice that grows beyond a few days is split, with its rungs renumbered in the spec rather than in chat.
