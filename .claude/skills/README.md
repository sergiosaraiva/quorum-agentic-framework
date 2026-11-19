# Skills

A skill is a folder under `.claude/skills/<name>/` holding a `SKILL.md`: packaged instructions that an agent or the main session loads on demand. The full catalogue is [SKILL-INDEX.md](SKILL-INDEX.md).

## Skill vs agent

| | Skill | Agent |
|---|-------|-------|
| What it is | Packaged instructions (rules, checklists, patterns) | An isolated subagent with its own role |
| Where | `.claude/skills/<name>/SKILL.md` | `.claude/agents/<name>.md` |
| Context | Loaded into the caller's context when needed | Its own fresh context window |
| Tools and model | Inherits the caller's | Declares its own `tools`, `model`, `effort` |
| Loading | Progressive disclosure: only the frontmatter `description` is always visible; the body loads when the task matches | Invoked explicitly or by its `description` |
| Purpose | Know-how: how to do X the project's way | Role: who does the work, and who reviews it |

An agent uses skills; a skill never spawns an agent. Reviewer agents (`quality-guardian`, `regression-detective`, `documentation-reviewer`) have no Write or Edit tools and are independent of the producer.

## How a skill loads

1. The `description` in frontmatter states what the skill does and "Use when...". It is the trigger, so keep it precise and at most 1024 characters.
2. When a task matches, the body is read. Detail beyond about 7 KB goes in a `reference/` file read only when needed.
3. When unsure which applies, use [routing-to-skills](routing-to-skills/SKILL.md).
4. A skill with `disable-model-invocation: true` (`pr-review`) is never auto-triggered; the review workflow and the local script read it by path.

## Layout

```
.claude/skills/
  README.md
  SKILL-INDEX.md
  <name>/SKILL.md        # frontmatter: name (= folder), description
  <name>/reference/      # optional detail
```

## Writing or changing a skill

- `name` equals the folder name; `description` starts with what it does and includes "Use when...".
- Tables over prose; no filler; point to other skills instead of copying them.
- Add a skill when a pattern has repeated about 3 times. Split one past ~300 lines.
- Changes follow `maintaining-agent-framework`: `python3 scripts/framework_lint.py`, size check, and independent review.
