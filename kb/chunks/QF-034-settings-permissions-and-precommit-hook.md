---
chunk_id: QF-034
title: Settings permissions and the pre-commit framework hook
topics: [claude-code, configuration, security]
links: [QF-019, QF-029, QF-033]
sources: [".claude/settings.json", ".claude/hooks/pre-commit-framework-check.sh", ".claude/hooks/install-framework-check-hook.sh", ".claude/hooks/guard_bash.py", "scripts/framework_lint.py"]
---
`.claude/settings.json` sets Claude Code permissions in three lists.

Allow: read tools, `Edit` and `Write` only under source paths (`src`, `frontend`, `tests`, `docs`, `kb`, `questions`, `scripts`) and `README.md`, build and test commands, read-only `git` and `gh`, the KB tools and scripts, the agents, some `WebFetch` domains.

Ask: edits to `.claude/**`, `.mcp.json`, `settings*.json`, workflows and `CLAUDE.md` files, `Edit`/`Write` of any top-level `scripts/*.py` and `scripts/*/__init__.py`, `*.*proj`, `*.props`, `*.targets`, `*.rsp` and `*.user` (OD-032), `WebSearch`, `git push`, `npm ci`, `scripts/kb/remove_examples.py`, and commands that can run code or change shared state: `git --output`, `dotnet` property and logger overrides, `npm audit fix`, the local review's control flags, `gh pr merge` and `gh api` DELETE. Only `Edit(path)` rules take effect; the `Write(path)` twins are inert. The gate scripts (`ai_review_local.py`, `framework_lint.py`, `coverage_changed.py`) and the KB scripts (which load `lib` and `backends` by path) drop their own directory from `sys.path`, so a planted `scripts/json.py` cannot shadow the stdlib.

Deny: reading `.env`, key and credential files, writing `.env`, `rm` with recursive and force flags, force-push, branch deletion, hard reset, `git checkout -- <path>`, `git clean`, database update and drop, infrastructure apply and `gh repo delete`.

The PreToolUse hook `.claude/hooks/guard_bash.py` is a deterministic second layer behind the deny list. Claude Code ignores Edit ask rules for redirect targets, so the guard asks before shell output redirection except to `/dev/null`, fd dups (`2>&1`, `>&2`, `>&-`) or paths outside the repository (not under `/dev/` or `/proc/`). Commands that write files themselves remain a gap (OD-033). It blocks force and delete pushes, hard resets, `git clean -f`, `rm -rf`, `ef database update`, `terraform apply`, downloads piped into a shell, `git -c alias.*`, dotnet build-event overrides and here-strings into a shell. It fails open on a malformed payload or without `python3`. It is best effort, not a sandbox; do not rely on it in `bypassPermissions` or auto mode (OD-033).

The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` is installed by `.claude/hooks/install-framework-check-hook.sh`. The hook copies the staged index to a temporary tree with `git checkout-index` and runs `python3 scripts/framework_lint.py --root "$TMP/.claude"` on that copy, so partial staging and staged deletions are judged correctly. The `maintaining-agent-framework` skill lists what the lint checks.
