---
chunk_id: QF-026
title: How many review rounds: loop-back, the five re-loop cap and human escalation
topics: [validation, process]
links: [QF-024, QF-025, QF-027, QF-028]
sources: [".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/07-independent-validation.md", ".github/workflows/ai-pr-review.yml", "scripts/ai_review_local.py"]
---
Quorum allows at most five re-loops per gate chain. A blocking finding at a review gate goes back to the artifact's writer, not forward. This is the loop-back rule.

| Gate | On a blocking finding | On none |
|------|-----------------------|---------|
| quality-guardian and regression-detective (code) | Re-invoke code-engineer with the consolidated findings of every reviewer in that message, then re-run the pair | test-automator |
| test-automator (code) | Re-invoke code-engineer with the failing tests or gap, and re-run the pair before test-automator | Code pipeline complete |
| documentation-reviewer (docs, `.claude/**`, chunks) | Re-invoke documentation-curator, then re-run the reviewer | Done |

A stage is never skipped because an earlier iteration passed it, since a re-invoked writer can reintroduce a defect. The cap is five re-loops per gate chain (OD-031). If the gate still fails, the session stops and surfaces the pattern to the user once, batched, because repeated failure usually means the requirement or the design is wrong, not the code. For a framework-doc change a single shared budget of five applies across both gates.

Two further caps bound the AI CI. On GitHub, when `AI_REVIEW_ENABLED` is `true`, `MAX_ROUNDS: 5` in `.github/workflows/ai-pr-review.yml` bounds rounds across a pull request's pushes. The round count is the number of marker comments posted by `github-actions[bot]`. When the next round would exceed the cap, the workflow adds the label `needs-human-review`, posts one comment saying a human must review, and stops reviewing. Rounds resume when a person deletes the marker comments or raises `MAX_ROUNDS` (a change to the workflow that lands on the integration branch through its own pull request, because approvers reject runs that change `.github/**`); removing the label is optional housekeeping. Locally, `scripts/ai_review_local.py` keeps its round counter in `.ai-review/state.json`, stops at five rounds with exit code 3, and `--reset` after a human review drops the current branch's saved count, so the next completed round starts from 1.

A human remains the final approver. Escalation is not failure; it is the designed outcome when the loop does not converge.
