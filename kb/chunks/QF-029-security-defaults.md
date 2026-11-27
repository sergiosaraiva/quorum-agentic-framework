---
chunk_id: QF-029
title: Security-sensitive defaults in Quorum
topics: [security, ai-ci, configuration]
links: [QF-028, QF-027, QF-019, QF-008]
sources: [".github/workflows/ai-pr-review.yml", "scripts/ai_review_local.py", ".claude/settings.json", "CLAUDE.md", "docs/concepts/08-ai-ci-local-and-github.md"]
---
Untrusted pull request content. The workflow tells the model that the pull request title, body, branch name, diff, files and every conversation or review comment from any user are untrusted data, never to follow instructions in them, run commands they contain or reveal secrets. The reviewer instructions come from the base branch checkout, not the pull request head. The workflow file is not protected that way: a same-repo branch can edit it and the edited copy runs with the secrets before review; an environment secret behind required reviewers is the recommended fix (TQ-019). The local script wraps the diff in `<diff>` tags with an untrusted-content notice. Findings are comments only; a human merges.

Least privilege. The workflow sets top-level `permissions: {}`: `pull-requests: write` for the gate job, `contents: read` plus `pull-requests: write` for the review job, no `id-token` or `issues`. Checkout sets `persist-credentials: false`. The review step allows `Read`, `Grep`, `Glob`, `Agent`, `Skill`, the inline comment tool, `gh pr diff` and `gh pr view`, and `--disallowedTools` denies edits, web access and build, test, script or git Bash; the base `settings.json` allow list also applies in CI. The action `settings` input turns on `blockReadsOutsideWorkingDirectories` and denies `Read(//proc/**)` and `Read(//home/runner/work/_temp/**)`. It uses `pull_request`, not `pull_request_target`, so fork pull requests get no secrets and are skipped. The local script runs `claude -p` read-only: `--tools Read,Grep,Glob` restricts the tools, `--disallowedTools` blocks Bash, the write and web tools and `mcp__*`, `--strict-mcp-config` skips configured MCP servers, `ENABLE_CLAUDEAI_MCP_SERVERS=false` turns off claude.ai connectors, and `blockReadsOutsideWorkingDirectories` (Claude Code 2.1.257 or later) fences reads to the repository.

No secrets in source. The model key is the repository secret `ANTHROPIC_API_KEY`, and locally the `claude` CLI uses your own sign-in or an environment variable. `.claude/settings.json` denies reading `.env`, `*.pem`, `*.key` and credential files and writing `.env`. Immutable Rule 1 forbids secrets in source; examples use `${ENV_VAR}` placeholders.

Other settings denials: force-push, hard reset, `git clean`, recursive force delete, infrastructure apply and database drops. Settings ask before edits to `.claude/**`, workflows and `CLAUDE.md` files.
