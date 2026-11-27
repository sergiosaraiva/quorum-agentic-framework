---
chunk_id: QF-028
title: GitHub AI CI on every pull request
topics: [ai-ci, review]
links: [QF-027, QF-026, QF-029]
sources: [".github/workflows/ai-pr-review.yml", "docs/concepts/08-ai-ci-local-and-github.md", ".claude/skills/pr-review/SKILL.md"]
---
The GitHub AI CI is the workflow `.github/workflows/ai-pr-review.yml`, named "AI PR Review". It is an optional, stronger second review gate: it runs only when the repository secret `ANTHROPIC_API_KEY` is set. Without the secret the review job is skipped by design and the check stays green, which is not a review. It triggers on opened, synchronized, reopened or ready-for-review pull requests and skips drafts and forks. A concurrency group cancels an older run on a new push.

It has two jobs. The gate job counts earlier rounds as comments authored by `github-actions[bot]` that contain the marker `<!-- ai-review-round -->`; comments from anyone else do not count. It computes the current round and, when the round would exceed `MAX_ROUNDS` (3), adds the label `needs-human-review`, posts one comment and stops.

The review job checks out two trees. The base branch is the working directory, so `CLAUDE.md` and `.claude/**` are read from the base and a pull request cannot weaken its reviewer's instructions. The workflow file is the exception: a same-repo branch can edit it and its copy runs with repository secrets before review (TQ-019). The pull request head is checked out under `pr-head/` in the workspace as data only; a step deletes its `CLAUDE.md` files, `.claude/` and `.mcp.json`. It runs `anthropics/claude-code-action` with the model from the repository variable `AI_REVIEW_MODEL`, default `opus`, and a limit of 30 turns. The prompt tells it to run the quality-guardian and regression-detective subagents on the diff, report findings with evidence and a failing scenario, post one summary plus up to 20 inline comments, and re-check earlier findings on later rounds. A final step records the round by posting the marker comment.

Findings use the tiers Blocker, Warning and Info; only a Blocker blocks. The workflow does not resolve review threads, choose the model by path or split large diffs; the producer fixes each finding and resolves the thread by hand.

Jobs run on `RUNNER_LABEL`, default `ubuntu-latest`. When the key is set, the review can be made a required status check, so it cannot be forgotten, and it is the visible record of review for the team.
