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
| Agent | `name` equals filename; `description`, `tools` (never `Agent` or `AskUserQuestion`), `model` (`opus`, `sonnet` or `haiku`), `effort` where applicable |
| References | Every skill named in an agent's `skills:` has a folder; every path in a body exists |
| Catalogue | Every skill folder appears in `.claude/skills/SKILL-INDEX.md` and vice versa |
| Forbidden terms | Project-specific or private strings not allowed in the template |
| Shared rules | Never Invent rule 7 and "What blocks" live only in `agents/_SHARED-PATTERNS.md`. Any line elsewhere that says "KB unreachable" must say "rule 7" on the same line; a second blocking table and the old confidence-based blocking phrases are banned (the lint names them); a line that says "block" and names three or more blocking statuses must name "What blocks"; agents with KB MCP tools list `Bash` unless they are in `NO_BASH_AGENTS` (`requirements-analyst`, `solution-architect`, `prompt-engineer`) |

Run `python3 scripts/framework_lint.py` (stdlib only; `--root` selects the framework folder, default `.claude`, falling back to `claude-staging` with a notice while the template is not yet installed). The pre-commit hook `.claude/hooks/pre-commit-framework-check.sh` runs the same checks on staged files. KB lint is separate: `python3 scripts/kb/check_chunks.py`; KB tooling tests: `python3 -m unittest discover -s scripts/kb/tests`.

## 2. Size budgets

| File | Budget |
|------|--------|
| Agent body (incl. `_SHARED-PATTERNS.md`) | at most 16 KB; the lint warns above |
| SKILL.md | at most 7 KB; move detail to `reference/` only when needed |
| CLAUDE.md | ~10 KB root, smaller in sub-folders |

Over budget: cut repetition, replace prose with tables, move examples to `reference/`. A rule lives in one file; others point to it. Compaction must not drop rules, ids or paths: diff before and after.

## 3. Freshness check

| Drift | How to detect |
|-------|---------------|
| Counts (agents, skills) | Compare stated numbers with `ls` |
| Paths | Check each backticked path exists |
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
| 4 | For reviewer agents, replay a known-defect diff and confirm it is flagged with file:line evidence |
| 5 | Keep the change only if after is better; otherwise revert |

## 5. Reporting and changing

- Record a wrong-guidance incident as a TQ (`recording-decisions`): the agent or skill, the prompt, the bad output.
- Framework edits go through `documentation-curator`, then `quality-guardian` || `regression-detective`, then `documentation-reviewer`. The author never approves its own change.
- Add a skill only when a pattern has repeated about 3 times; split a skill past ~300 lines or two patterns.
