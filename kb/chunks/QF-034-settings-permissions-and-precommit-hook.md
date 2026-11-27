---
chunk_id: QF-034
title: Settings permissions and the pre-commit framework hook
topics: [claude-code, configuration, security]
links: [QF-019, QF-029, QF-033]
sources: [".claude/settings.json", ".claude/hooks/pre-commit-framework-check.sh", ".claude/hooks/install-framework-check-hook.sh", ".claude/hooks/guard_bash.py", "scripts/framework_lint.py"]
---
The settings file `.claude/settings.json` sets Claude Code permissions in three lists.

Allow: read tools, `Edit` and `Write` only under source paths (`src`, `frontend`, `tests`, `docs`, `kb`, `questions`, `scripts`, `README.md`), build and test commands, read-only `git` and `gh`, the KB tools and scripts, some `WebFetch` domains and the agents.

Ask: edits to `.claude/**`, `.mcp.json`, `settings*.json`, workflows and `CLAUDE.md` files, `WebSearch`, `git push`, `npm ci`, `scripts/kb/remove_examples.py`, and commands that can run code or change shared state, for example `git` with `--output`, `dotnet` property (`-p:`, `--p:`, `--property`), restore-property and logger overrides, `npm audit fix`, the local review's control flags (`--reset`, `--max-rounds`, `--claude-bin`, `--out-dir`), `gh pr merge` and `gh api` DELETE (`-X`, `-X=`, `--method`).

Deny: reading `.env`, key and credential files, writing `.env`, `rm` with recursive and force flags, force-push (including `git push <remote> :<branch>`), branch deletion, hard reset, `git checkout -- <path>`, `git clean`, database update and drop, infrastructure apply and `gh repo delete`.

The PreToolUse hook `.claude/hooks/guard_bash.py`, wired in `hooks.PreToolUse` of the settings file, is a deterministic second layer behind the deny list (one subcommand at a time). It blocks force and delete pushes, hard resets, discarding changes, `git clean -f`, `rm -rf`, `ef database update` and `drop`, `terraform apply` and `destroy`, downloads piped into a shell, git `--output`, `git -c alias.*`, dotnet build-event overrides and here-strings into a shell. It fails open on a malformed payload or without `python3`. It is best effort, not a sandbox: the permission prompt and an operating-system sandbox are the real boundaries; do not rely on it in `bypassPermissions` or auto mode.

The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` is installed with `.claude/hooks/install-framework-check-hook.sh`, which will not overwrite a foreign hook. The hook copies the staged index to a temporary tree with `git checkout-index` and runs `python3 scripts/framework_lint.py --root "$TMP/.claude"` on that copy, so partial staging and staged deletions are judged correctly. The lint checks agent and skill files: valid frontmatter, a name matching the file or folder, a description of at most 1024 characters, a model of opus, sonnet or haiku, no `Agent` or `AskUserQuestion` tool, no legacy `Task` tool name, and a known `permissionMode`.
