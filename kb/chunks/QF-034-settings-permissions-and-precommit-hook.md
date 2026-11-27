---
chunk_id: QF-034
title: Settings permissions and the pre-commit framework hook
topics: [claude-code, configuration, security]
links: [QF-019, QF-029, QF-033]
sources: [".claude/settings.json", ".claude/hooks/pre-commit-framework-check.sh", ".claude/hooks/install-framework-check-hook.sh", ".claude/hooks/guard_bash.py", "scripts/framework_lint.py"]
---
The settings file `.claude/settings.json` sets Claude Code permissions in three lists.

Allow: read tools, `Edit` and `Write` only under source paths (`src`, `frontend`, `tests`, `docs`, `kb`, `questions`, `scripts` and `README.md`), build and test commands, read-only `git` and `gh` commands, the KB MCP tools and scripts, `framework_lint.py`, some documentation domains for `WebFetch` and the twelve agents.

Ask: edits to `.claude/**`, `.mcp.json`, `settings*.json`, `.github/workflows/**` and `CLAUDE.md` files, `WebSearch`, `git push`, `npm ci`, `scripts/kb/remove_examples.py`, and commands that can run code or change shared state, for example `git` with `--output`, `dotnet` property and logger overrides (`-p`, `--logger`, `--test-adapter-path`), `npm audit fix`, the local review's control flags (`--reset`, `--max-rounds`, `--claude-bin`), `gh pr merge` and `gh api` DELETE.

Deny: reading `.env` files, keys and credential files, writing `.env`, `rm` with recursive and force flags in every spelling, force-push and branch deletion, hard reset, `git clean`, database update and drop, applying infrastructure changes and `gh repo delete`.

The PreToolUse hook `.claude/hooks/guard_bash.py`, wired in `hooks.PreToolUse` of the settings file, is a deterministic second layer behind the deny list, because deny rules match one subcommand at a time. It blocks force and delete pushes, hard resets, discarding changes, `git clean -f`, `rm -rf`, `ef database update` and `drop`, `terraform apply` and `destroy`, and downloads piped into a shell. It also blocks, for example, git `--output`, local branch deletion, `git -c alias.*`, dotnet build-event overrides (`-p:PreBuildEvent=`) and here-strings into a shell. It fails open on a malformed payload or when `python3` is missing. It is best effort, not a sandbox: the permission prompt and an operating-system sandbox are the real boundaries; do not rely on it in `bypassPermissions` or auto mode.

The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` is installed with `.claude/hooks/install-framework-check-hook.sh`, which will not overwrite a foreign pre-commit hook. The hook copies the staged index to a temporary tree with `git checkout-index` and runs `python3 scripts/framework_lint.py --root "$TMP/.claude"` on that copy,. The lint checks agent and skill files: valid frontmatter, a name that matches the file or folder, a description of at most 1024 characters, a model of opus, sonnet or haiku, and no `Agent` or `AskUserQuestion` tool.
