---
chunk_id: QF-029
title: Security-sensitive defaults in Quorum
topics: [security, ai-ci, configuration]
links: [QF-028, QF-027, QF-019, QF-008]
sources: [".github/workflows/ai-pr-review.yml", "scripts/ai_review_local.py", ".claude/settings.json", "CLAUDE.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
Quorum ships several defaults that limit what a mistake or an attack can do.

Untrusted pull request content. The GitHub workflow tells the model that the pull request title, body, branch name, diff, code comments and file contents are untrusted data written by the author, never to follow instructions found in them, never to run commands they contain and never to reveal secrets. The reviewer instructions come from the base branch checkout, not the pull request head. The local script wraps the diff in `<diff>` tags with a notice that the content is untrusted and must be reviewed, not obeyed. Findings are only comments; they cannot merge or approve, and a human decides the merge.

Least privilege. The workflow sets top-level `permissions: {}` and grants each job only what it needs: `pull-requests: write` for the gate job, and `contents: read` plus `pull-requests: write` for the review job. Neither has `id-token` or `issues` permissions. Checkout uses `persist-credentials: false`. The review step allows only `Read`, `Grep`, `Glob`, `Task`, `Skill`, the inline comment tool, `gh pr diff` and `gh pr view`. It uses the `pull_request` event, not `pull_request_target`, so fork pull requests get no secrets and are skipped on purpose. The local script allows only `Read Grep Glob`.

No secrets in source. The model key is the repository secret `ANTHROPIC_API_KEY`, and locally the `claude` CLI uses your own sign-in or an environment variable, never a file in the repository. The settings file `.claude/settings.json` denies reading `.env` files, `*.pem` and `*.key` files and credential files, and denies writes to `.env`. Immutable Rule 1 forbids secrets in source, and examples use `${ENV_VAR}` placeholders.

Other settings denials: force-push, hard reset, `git clean`, `rm -rf`, applying infrastructure changes and database drops. The settings file asks before edits to `.claude/**`, workflows and `CLAUDE.md` files.
