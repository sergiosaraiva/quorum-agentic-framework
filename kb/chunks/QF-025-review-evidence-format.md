---
chunk_id: QF-025
title: Review evidence format and severity levels
topics: [validation, review]
links: [QF-024, QF-026, QF-006]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/07-independent-validation.md", ".claude/skills/pr-review/SKILL.md", "scripts/ai_review_local.py"]
---
A Quorum review finding without evidence cannot be acted on or disputed, so every reviewer reports in a fixed form: `severity`, `category`, `file` plus an anchor, `scenario` and `fix`. The scenario is a concrete input or sequence that fails, for example "a refund of 0 on an invoiced order returns 500". A finding without a failing scenario is dropped. A bare "looks fine" is not a result, and a clean review states what was checked so that silence cannot be mistaken for coverage.

| Severity | Meaning |
|----------|---------|
| Critical | Data loss or corruption, auth bypass, secret exposure, tenant leak, a broken Immutable Rule |
| High | Wrong behaviour on a normal path, a contract break, unbounded resource growth, a missing required control such as no alignment result or no endpoint auth decision |
| Medium | Wrong on an edge path, a design violation |
| Low | Maintainability with a concrete cost; nothing else is reported |

Critical and High block; Medium and Low do not. Other reviewers map onto the same rule in `_SHARED-PATTERNS.md`: ux-usability-specialist blocks on Blocker and Major, documentation-reviewer blocks on status `ungrounded`, `conflict` or `gate-failure` with confidence of at least 0.8, and the GitHub AI review blocks on Blocker, not on Warning or Info.

Every non-blocking finding gets a disposition in the hand-off: fixed, deferred with a recorded item, or rejected with a reason. None is dropped silently.

Stored artifacts never cite line numbers, because they go stale. They name the file path plus a stable anchor such as a symbol, a heading or a short quoted literal. A transient review finding may keep a `line` field as a pointer.

The local review script `scripts/ai_review_local.py` asks the model for JSON with severities `blocking`, `warning` and `info` and the fields file, line, title, evidence, failing scenario and suggestion. Reviewers must not raise anything listed in the Known Non-Issues table of the shared patterns file, so a false alarm is not argued again every round.
