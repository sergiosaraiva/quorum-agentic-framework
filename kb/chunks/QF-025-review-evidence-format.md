---
chunk_id: QF-025
title: Review evidence format and severity levels
topics: [validation, review]
links: [QF-024, QF-026, QF-006]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/07-independent-validation.md", ".claude/skills/pr-review/SKILL.md", "scripts/ai_review_local.py"]
---
A Quorum review finding without evidence cannot be acted on or disputed, so every reviewer agent reports in one form: `id`, `category`, `severity` (`status` for documentation-reviewer), `file` plus an `anchor`, `scenario`, `fix` and an optional `confidence`. The scenario is a concrete input or sequence that fails. A finding without a failing scenario is dropped. A bare "looks fine" is not a result; a clean review states what was checked.

| Severity | Meaning |
|----------|---------|
| Critical | Data loss or corruption, auth bypass, secret exposure, tenant leak, a broken Immutable Rule |
| High | Wrong behaviour on a normal path, a contract break, unbounded resource growth, a missing required control such as no alignment result or no endpoint auth decision |
| Medium | Wrong on an edge path, a design violation |
| Low | Maintainability with a concrete cost |
| Info | Optional hint used by security-engineer; never blocks |

Critical and High block; Medium, Low and Info do not. Severity alone decides; unverified items (confidence 0.50 to 0.79) are listed with their would-be severity and never block. A Medium security finding does not block; if not fixed before merge it is recorded as an open question and, once the owner accepts the risk, as a decision with `accepted_risk: true` and an expiry date. Blocking per reviewer: the local AI review on `blocking` (Critical or High), ux-usability-specialist on Blocker and Major, documentation-reviewer on status `ungrounded`, `fabricated-citation`, `stale`, `conflict` or `gate-failure`, the GitHub AI review on Blocker.

Every non-blocking finding gets a disposition in the hand-off: fixed, deferred with a record, or rejected with a reason.

Stored artifacts cite a file path plus an anchor (symbol, heading or quoted literal), never line numbers; a transient review finding may keep an optional `line`.

The local review script `scripts/ai_review_local.py` is exempt from that form: it asks the model for JSON with severities `blocking`, `warning` and `info` and the fields file, line, title, evidence, failing scenario and suggestion. Reviewers must not raise anything listed in the Known Non-Issues table of the shared patterns file.
