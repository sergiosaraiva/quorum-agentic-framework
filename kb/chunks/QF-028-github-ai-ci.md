---
chunk_id: QF-028
title: GitHub AI CI on every pull request
topics: [ai-ci, review]
links: [QF-027, QF-026, QF-029]
sources: [".github/workflows/ai-pr-review.yml", "docs/concepts/08-ai-ci-local-and-github.md", ".claude/skills/pr-review/SKILL.md"]
---
The GitHub AI CI is the workflow `.github/workflows/ai-pr-review.yml`, named "AI PR Review". It is the review gate. It triggers on pull requests that are opened, synchronized, reopened or marked ready for review, and skips drafts and pull requests from forks. A concurrency group per pull request cancels an older run when a new push arrives.

It has two jobs. The gate job counts earlier rounds as comments authored by `github-actions[bot]` that contain the marker `<!-- ai-review-round -->`; comments from anyone else do not count. It computes the current round and, when the round would exceed `MAX_ROUNDS` (3), adds the label `needs-human-review`, posts one comment and stops.

The review job checks out two trees. The base branch is the working directory, so `CLAUDE.md` and `.claude/**` are read from the base and a pull request cannot weaken its own reviewer. The pull request head is checked out under `pr-head/` in the workspace (actions/checkout refuses paths outside it) as data only; a step deletes its `CLAUDE.md` files, `.claude/` and `.mcp.json`. It runs `anthropics/claude-code-action` with the model from the repository variable `AI_REVIEW_MODEL`, default `opus`, and a limit of 30 turns. The prompt tells it to run the quality-guardian and regression-detective subagents on the diff, report only findings with evidence and a failing scenario, post one summary comment plus up to 20 inline comments, and on later rounds re-check earlier findings. A final step records the round by posting the marker comment.

Findings use the tiers Blocker, Warning and Info; only a Blocker blocks. The workflow does not resolve review threads, choose the model by path or split large diffs. The producer fixes each finding, replies and resolves the thread by hand, and very large diffs are a reason rungs are small.

Jobs run on the repository variable `RUNNER_LABEL`, falling back to `ubuntu-latest`. The review can be made a required status check, so it cannot be forgotten, and it is the visible record of review for the team.
