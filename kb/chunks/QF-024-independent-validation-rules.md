---
chunk_id: QF-024
title: Independent validation: the producer never approves its own work
topics: [validation, principles]
links: [QF-025, QF-026, QF-006, QF-030]
sources: ["docs/concepts/07-independent-validation.md", ".claude/agents/_SHARED-PATTERNS.md"]
---
Quorum has no single point of failure in how work is approved. The agent that produced a change never approves it, because a model reviewing its own output shares its own blind spots: the assumption that produced the bug lets the bug pass review.

The Independent Review Rule in `.claude/agents/_SHARED-PATTERNS.md` sets five properties:

| Property | Meaning |
|----------|---------|
| Different role | The reviewer is never the writer's role: code from code-engineer is reviewed by quality-guardian, regression-detective and test-automator |
| Fresh context | The reviewer gets the diff, the spec or design and the alignment result, not the writer's reasoning or conclusion |
| Equal or stronger model | The reviewer's model is at least the producer's. Judgement-heavy reviewers (quality, regression, security, architect, infrastructure, ux) run Opus; documentation-reviewer runs Sonnet because it checks grounding mechanically against sources |
| Read-only | Reviewers have no Write or Edit tools; Bash is for read, build and test commands and must not write outside build output. They return findings in a structured form |
| No anchoring | A prompt that hands over a hypothesis such as "confirm X is fine" is rewritten as a neutral task before delegation |

In agent files this appears as `model: opus` or `sonnet`, a `tools` allow-list with no `Write` or `Edit` and no `Agent` tool. The only exception is ux-usability-specialist, which may write a scratch mockup in the temporary directory and never a repository file. A reviewer that can "just fix it" would leave its fix unreviewed.

Scopes do not overlap. quality-guardian and regression-detective own different finding categories, and the pair is split by concern rather than duplicated, because a second reviewer of the same model with a different brief catches different things. test-automator runs only after every reviewer has returned, so tests are written for the final code. documentation-reviewer, a different agent from the curator, checks docs.

A weaker model tends to pass what it cannot follow, and false confidence is worse than no review. A human remains the final approver and decides merges.
