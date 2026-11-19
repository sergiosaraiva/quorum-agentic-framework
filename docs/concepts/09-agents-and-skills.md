# 09. Agents and skills

Claude Code offers several ways to shape what a model does. They are easy to confuse and each fits a different need. This page defines each, then shows how to write good agents and skills. Check current behaviour of Claude Code features against its official documentation; the descriptions here reflect the conventions this template relies on.

## The building blocks

| Block | What it is | Loaded | Lives in |
|-------|-----------|--------|----------|
| `CLAUDE.md` | Standing project instructions | Automatically every session; sub-files when working in their folder | `CLAUDE.md`, `<dir>/CLAUDE.md` |
| Agent (subagent) | A specialised worker with its own context window, tool allow-list and model | When the session delegates to it, by explicit call or by matching its `description` | `.claude/agents/<name>.md` |
| Skill | A packaged procedure: instructions, optionally scripts and reference files | Name and description always visible; body loaded only when the task matches | `.claude/skills/<name>/SKILL.md` |
| Hook | A command run on an event (a Claude Code event configured in `settings.json`, or a git hook such as the shipped pre-commit lint, installed with `.claude/hooks/install-framework-check-hook.sh`) | By the harness or git, not by the model | `settings.json`, `.claude/hooks/` |
| MCP server | An external tool provider the model can call | Configured once; tools appear in the tool list | `.mcp.json` |

Rules of thumb: facts and rules every task needs go in `CLAUDE.md`. A role with a distinct job, tools and model is an agent. A procedure only some tasks need is a skill. Something that must happen every time, deterministically, regardless of what the model decides, is a hook (the model cannot forget a hook). Access to a system outside the repo is an MCP server.

## Agents

An agent is a Markdown file: YAML frontmatter, then the system prompt as the body.

```markdown
---
name: quality-guardian
description: Use proactively after any implementation to review correctness, security and EF Core query safety. No Write or Edit tools.
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Skill, mcp__business-kb__search, mcp__business-kb__chunk, mcp__qa-kb__search
---
# Role
...
```

| Frontmatter field | Purpose |
|-------------------|---------|
| `name` | Identifier used to call it |
| `description` | When to use it; the main delegation signal. Say what it does and when to call it proactively |
| `model` | Alias `opus`, `sonnet` or `haiku` ([model-selection-and-costs](../reference/model-selection-and-costs.md)) |
| `effort` | Reasoning effort where supported (verify the accepted values for your Claude Code version); see the effort levels in the cost reference |
| `tools` | Allow-list. Omit write tools for a reviewer; MCP tools are named `mcp__<server>__<tool>` |

Why the allow-list matters: it is the technical form of "reviewers do not edit". A reviewer without `Write` or `Edit` cannot patch what it finds. Its `Bash` is for reading, building and testing and must not write outside build output; the tool list cannot enforce that, so the agent body states it. Subagents cannot spawn subagents or ask the user, so no agent lists `Agent` or `AskUserQuestion`; orchestration and questions stay with the calling session, and an agent returns open items (`questions_to_record`) to it. Reviewers also carry no persistent memory: independence comes from a fresh context each time.

The separate context window is the other point. A subagent works through many file reads and returns only a summary, so the main session's context stays small, and a reviewer starts without the producer's assumptions ([07](07-independent-validation.md)).

### Writing a good agent body

| Guideline | Detail |
|-----------|--------|
| One role, stated first | "You review X. You do not write code." |
| Inputs and outputs explicit | What it receives (diff, ids) and the exact format it returns |
| Decision rules as tables | Which findings are blocking, which categories it owns and does not own |
| Ground rules by pointer | "Follow the grounding rule in `CLAUDE.md`" instead of copying it |
| Evidence required | Findings need file + anchor, claim, failing scenario |
| Stop conditions | What it does when the KB is down or the diff is too large |
| Size | `python3 scripts/framework_lint.py` warns above 16 KB; aim well under, and move shared material to `_SHARED-PATTERNS.md`. The same lint also checks the shared rules: Never Invent rule 7 has a single owner (any line saying "KB unreachable" must say "rule 7"), blocking decisions are not restated outside "What blocks", and an agent's `tools:` match what rule 7 asks of it |

`.claude/agents/_SHARED-PATTERNS.md` holds what several agents share: the alignment gate, loop-back rule, severity scale, citation format and common tool permissions. An agent file points to it instead of repeating it, so a rule has one owner.

## Skills

A skill is a folder with a `SKILL.md` and, if needed, `reference/` files or scripts. Only its name and short description sit in context permanently; the body is loaded when the task matches the description. This is progressive disclosure: a library of dozens of skills costs a few lines of context, not dozens of procedures.

```markdown
---
name: creating-xunit-tests
description: Writes xUnit v3 unit tests with the built-in Assert, AAA structure, for services in isolation. Use when adding or changing business logic that has no database or HTTP dependency.
---
# Steps
...
```

### Writing a good skill

| Guideline | Detail |
|-----------|--------|
| Description is the trigger | Say what it does and exactly when to use it, including "not for ..." to prevent false matches |
| Concise body | The lint warns above 7 KB; aim for about 6 KB or less. Assume the model is capable; give only what it would not know: your conventions, order of steps, traps |
| Procedures, not essays | Numbered steps, a decision table, one minimal example |
| Detail on demand | Long tables, templates and lookups go in `reference/` files the skill names |
| One job | Two jobs are two skills |
| Verifiable | State how to check the work (a command, an expected output) |

The index `.claude/skills/SKILL-INDEX.md` lists all 39 skills in seven groups (Backend, Data, Delivery and infrastructure, Frontend, Testing and quality, Documentation and knowledge, Planning, process and framework) with the agents that use them, so an agent can choose without loading all of them. The lint checks that the index and the skill folders agree.

## Which skills each agent uses

The "Used by" column of `.claude/skills/SKILL-INDEX.md` is the source; the same map is chunk QF-033.

| Agent | Skills |
|-------|--------|
| requirements-analyst | `planning-vertical-slices`, `recording-decisions` |
| solution-architect | `planning-vertical-slices`, `implementing-vertical-slice-features`, `implementing-caching-strategies` |
| ux-usability-specialist | `frontend`, `evaluating-usability` |
| code-engineer | the backend, data, frontend and delivery build skills, `implementing-vertical-slice-features`, `running-local-ai-review` |
| quality-guardian | `backend`, `database`, `writing-postgresql-migrations`; `pr-review` through CI |
| regression-detective | `detecting-regressions`, `verifying-cross-file-coupling`; `pr-review` through CI |
| test-automator | the testing skills plus `tuning-postgresql-queries` and `scaling-performance-test-data` |
| documentation-curator | `updating-internal-docs`, `updating-external-docs`, `writing-kb-chunks`, `maintaining-agent-framework` |
| documentation-reviewer | `reviewing-documentation`, `reviewing-kb-chunks`, `verifying-cross-file-coupling` |
| infrastructure-engineer | `deploying-the-application`, `implementing-infrastructure-as-code`, `creating-configuration-options`, `implementing-observability`, `managing-application-lifecycle` |
| prompt-engineer | `writing-world-class-prompts` |

`recording-decisions` is used by every agent and `routing-to-skills` by the main session or any agent. code-engineer chooses a skill by the path it edits (the routing table is in `.claude/agents/code-engineer.md`, for example `*Endpoints.cs` to `backend`, `Dtos.cs` to `creating-dtos-and-validation`, migrations to `writing-postgresql-migrations`).

## Examples from this repo

| Need | Right block | Why |
|------|-------------|-----|
| "Always cite chunk ids" | `CLAUDE.md` | Applies to every task |
| "Review diffs for drift, without editing, on Opus" | Agent `regression-detective` | A role with its own tools and model |
| "How to write an EF Core migration safely" | Skill | Needed only on schema changes |
| "Block commits containing secrets" | Hook (or a CI check) | Must be deterministic |
| "Search the business KB" | MCP server `business-kb` | A system outside the repo |

## Choosing models and effort per agent

Defaults are in `docs/reference/model-selection-and-costs.md`: the reviewer model is equal to or stronger than the producer's. Judgement-heavy reviewers (quality, regression, security, architect, infrastructure, ux) run `opus` at high effort; `documentation-reviewer` runs `sonnet` because it checks grounding mechanically against sources; code, tests, requirements and docs run `sonnet`; prompt sharpening runs `haiku`. Change them with evidence (review quality, cost per round), one agent at a time.

## Common mistakes

| Mistake | Effect | Fix |
|---------|--------|-----|
| Vague agent `description` | The session never delegates, or delegates wrongly | Concrete triggers and "use proactively when ..." |
| Reviewer with write tools | It fixes instead of reporting; independence lost | Remove `Write` and `Edit` |
| The same rule in five files | Drift; contradictions | One owner, pointers elsewhere |
| Giant skill | Context cost on every match | Split; move detail to `reference/` |
| Procedure in `CLAUDE.md` | Paid for on every task | Make it a skill |
| Agent that quotes the whole `CLAUDE.md` | Stale copy | Point to the section |

Framework files are governed content: edits to `.claude/agents/**` and `.claude/skills/**` go through documentation-curator and the review pair ([05](05-claude-md-files.md), [07](07-independent-validation.md)).
