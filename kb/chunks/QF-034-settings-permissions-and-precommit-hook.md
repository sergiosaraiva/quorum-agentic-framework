---
chunk_id: QF-034
title: Settings permissions and the pre-commit framework hook
topics: [claude-code, configuration, security]
links: [QF-019, QF-029, QF-033]
sources: [".claude/settings.json", ".claude/hooks/pre-commit-framework-check.sh", ".claude/hooks/install-framework-check-hook.sh", "scripts/framework_lint.py"]
---
The settings file `.claude/settings.json` sets Claude Code permissions in three lists.

Allow: read tools, `Edit` and `Write` only under source paths (`src`, `frontend`, `tests`, `docs`, `kb`, `questions`, `scripts` and `README.md`), build and test commands, read-only `git` and `gh` commands, the KB MCP tools, a short list of documentation domains for `WebFetch`, and the twelve agents.

Ask: edits to `.claude/**`, `.mcp.json`, `settings*.json`, `.github/workflows/**` and `CLAUDE.md` files, `WebSearch`, `git push` and `npm ci`.

Deny: reading `.env` files, keys and credential files, writing `.env`, `rm` with recursive and force flags in every spelling, force-push and branch deletion, `git reset --hard`, `git clean`, database update and drop, and applying infrastructure changes.

The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` is installed with `.claude/hooks/install-framework-check-hook.sh`, which refuses to overwrite a pre-commit hook it did not create. The hook copies the staged index to a temporary tree with `git checkout-index` and runs `python3 scripts/framework_lint.py --root "$TMP/.claude"` on that copy, so partial staging and staged deletions are judged correctly. Only when the lint script is absent does it run an inline check. The lint checks agent and skill files: valid frontmatter, a name that matches the file or folder, a description of at most 1024 characters, a model of opus, sonnet or haiku, and no `Agent` or `AskUserQuestion` tool.
