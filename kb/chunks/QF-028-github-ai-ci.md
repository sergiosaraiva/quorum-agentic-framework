---
chunk_id: QF-028
title: GitHub AI CI on every pull request
topics: [ai-ci, review]
links: [QF-027, QF-026, QF-029]
sources: [".github/workflows/ai-pr-review.yml", "docs/concepts/08-ai-ci-local-and-github.md", ".claude/skills/pr-review/SKILL.md"]
---
The GitHub AI CI is the workflow `.github/workflows/ai-pr-review.yml`, named "AI PR Review". It is an optional second review gate that runs only when the repository variable `AI_REVIEW_ENABLED` is `true`; otherwise the review job is skipped, the check stays green without being a review, and no environment or approval wait is created. When enabled, the review job runs in the environment `ai-review`, where the adopter stores `ANTHROPIC_API_KEY` as an environment secret behind required reviewers (TQ-019). Enabled without a key, the review steps are skipped with a notice. Required reviewers exist on public repositories on all plans, on private or internal ones only on GitHub Enterprise. Setup order, with `AI_REVIEW_ENABLED` last: docs/concepts/08-ai-ci-local-and-github.md. Approvers approve only `pull_request` runs of this workflow and reject runs that change `.github/**`. It triggers on opened, synchronized, reopened or ready-for-review pull requests, skips drafts and forks, and cancels an older run on a push.

It has two jobs. The gate job counts earlier rounds as comments authored by `github-actions[bot]` that contain the marker `<!-- ai-review-round -->`; others do not count. When the round would exceed `MAX_ROUNDS` (5), it adds the label `needs-human-review`, posts one comment and stops.

The review job checks out two trees. The base branch is the working directory, so `CLAUDE.md` and `.claude/**` come from the base and a pull request cannot weaken its reviewer. The workflow file is the exception: a same-repo branch can edit it and its copy runs with the secrets it can reach before review. The pull request head is checked out under `pr-head/` as data; a step deletes its `CLAUDE.md` files, `.claude/` and `.mcp.json`. It runs `anthropics/claude-code-action` with the model from variable `AI_REVIEW_MODEL` (default `opus`) and 30 turns, running the quality-guardian and regression-detective subagents on the diff and posting one summary plus up to 20 inline comments; later rounds re-check earlier findings. A final step posts the marker comment.

Findings use the tiers Blocker, Warning and Info; only a Blocker blocks. The workflow does not resolve threads or split large diffs.

Jobs run on `RUNNER_LABEL`, default `ubuntu-latest`. When enabled, the review can be a required status check.
