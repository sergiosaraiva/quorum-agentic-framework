---
name: maintaining-agent-framework
description: Keeps agents, skills and CLAUDE.md files healthy - lint frontmatter, keep file sizes bounded, run freshness checks for drifted counts and dead paths, and evaluate whether an agent or skill change actually improves behaviour. Use when an agent or skill gave wrong or outdated guidance, a framework fact drifted, files outgrew their size budgets, or a skill or agent change needs evaluating. Not for product code or product docs.
---

# Maintaining the agent framework

Framework = `.claude/agents/**`, `.claude/skills/**`, every `CLAUDE.md`. It decays in repeated ways: counts and paths drift, rules get copied into several files, files outgrow budgets, and a miss found by CI review was one local reviewers should have caught.

## 1. Lint (free, run first)

| Check | Rule |
|-------|------|
| Frontmatter parses | Valid YAML between `---` markers |
| Skill | `name` equals folder name; `description` present, at most 1024 characters, states "Use when..." |
| Agent | `name` equals filename; `description`, `tools` (never `Agent` or `AskUserQuestion`; an entry outside the known tool vocabulary and `mcp__*` warns, the legacy name `Task` is an error), `model` (`opus`, `sonnet` or `haiku`), `permissionMode` from the allowed list |
| Keys | A frontmatter key outside the agent or skill key list warns (probably a typo) |
| Support files | A `.md` inside a skill folder above 16 KB warns; a `.md` in an `agents/` subfolder warns (not loaded as an agent) |
| Deletions | `--staged` judges staged deletions too (deleting a skill folder must update the index) |
| Catalogue | Every skill folder appears in `.claude/skills/SKILL-INDEX.md` and vice versa |
| Shared rules | Never Invent rule 7 and "What blocks" live only in `agents/_SHARED-PATTERNS.md` (scan scope: `.claude/**/*.md`). Outside it: no copy of the rule 7 CLI command or of its branch bullets; every line saying "KB unreachable" says "rule 7", and every agent with KB MCP tools has such a line; two outdated blocking phrasings (a confidence-based one and a table header; the lint prints them) are banned; a line that says "block" (whole word) and names three or more of the five blocking statuses must name "What blocks". Agents in `NO_BASH_AGENTS` (`requirements-analyst`, `solution-architect`, `prompt-engineer`) list no `Bash` and have a Bash-free row in Common Tool Permissions; other agents with KB MCP tools list `Bash`; rule 7 names only agents that have a file. Limits: a blocking source naming fewer than three statuses, an unhyphenated agent name in rule 7, and anything outside `.claude/` are not caught (`docs/reference/pipeline-trial-findings.md`, F6) |

Run `python3 scripts/framework_lint.py` (stdlib only; `--root` selects the framework folder, default `.claude`, falling back to `claude-staging` with a notice while the template is not yet installed). The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` runs the full lint (`--root`) on a temp copy of the staged index, so partial staging and staged deletions are judged as committed. The lint does not check that body paths exist, that an agent's `skills:` entries have folders, or forbidden strings: do those in section 3. KB lint is separate: `python3 scripts/kb/check_chunks.py`; KB tooling tests: `python3 -m unittest discover -s scripts/kb/tests`.

## 2. Size budgets

| File | Budget |
|------|--------|
| Agent body (incl. `_SHARED-PATTERNS.md`) | at most 16 KB; the lint warns above |
| SKILL.md | at most 7 KB; move detail to `reference/` only when needed |
| CLAUDE.md | about 12 KB root (not lint-checked), smaller in sub-folders |

Over budget: cut repetition, replace prose with tables, move examples to `reference/`. A rule lives in one file; others point to it. Compaction must not drop rules, ids or paths: diff before and after.

## 3. Freshness check

| Drift | How to detect |
|-------|---------------|
| Counts (agents, skills) | Compare stated numbers with `ls` |
| Paths | Check each backticked path in a body exists (not linted) |
| Agent skills | Every skill named in an agent's `skills:` has a folder (not linted) |
| Forbidden terms | Grep for project-specific or private strings not allowed in the template (not linted) |
| Versions | Compare stack versions in CLAUDE.md with project files |
| Duplicate rules | Grep a distinctive phrase; keep one owner |
| Stale agent names | Grep for names not in the roster |

## 4. Evaluate a change

A skill or agent change is good only if behaviour improves.

| Step | Action |
|------|--------|
| 1 | Write 3-5 realistic prompts, including one the skill should not trigger on |
| 2 | Run before and after in fresh sessions |
| 3 | Check: triggered when it should (description quality), output followed the rules, no new false triggers |
| 4 | For reviewer agents, replay a known-defect diff and confirm it is flagged with file + anchor evidence |
| 5 | Keep the change only if after is better; otherwise revert |

## 5. Reporting and changing

- Record a wrong-guidance incident as a TQ (`recording-decisions`): the agent or skill, the prompt, the bad output.
- Framework edits go through `documentation-curator`, then `quality-guardian` || `regression-detective`, then `documentation-reviewer`. The author never approves its own change.
- Add a skill only when a pattern has repeated about 3 times; split a skill past ~300 lines or two patterns.
