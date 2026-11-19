---
name: routing-to-skills
description: Meta-skill that maps a task to the skills that apply. Use when an agent or user is unsure which skill covers a task, the task spans several skills, or a file path should be matched to the skill that owns it. Reads SKILL-INDEX.md and returns ranked recommendations; it does not run the skills.
---

# Routing to skills

On-demand router. It recommends; the caller reads the skill and decides.

## Workflow

1. State the task in one line and list the files involved.
2. Read `.claude/skills/SKILL-INDEX.md` (the only catalogue).
3. Match by path first, then by task keywords (tables below).
4. Confirm each candidate exists (Glob `.claude/skills/<name>/SKILL.md`).
5. Return 1-3 skills ranked, one-line reason each; the caller then reads the top one in full.

## Path to skill

| Path or file | Skill |
|--------------|-------|
| `src/Api/**` endpoints | `backend`, `creating-dtos-and-validation` |
| `src/Api/**` services, DI | `creating-application-services`, `creating-configuration-options` |
| `src/Infrastructure/Persistence/**` | `database` |
| `src/Infrastructure/Migrations/**` | `writing-postgresql-migrations` |
| Slow query, plans | `tuning-postgresql-queries`, `scaling-performance-test-data` |
| `frontend/src/app/**` components | `frontend`, `managing-state-with-signals` |
| Angular HTTP clients | `creating-angular-api-clients` |
| `frontend/**/*.spec.ts` | `writing-angular-tests` |
| `e2e/**`, Playwright | `writing-playwright-e2e-tests` |
| `tests/**` .NET | `creating-xunit-tests`, `writing-integration-tests` |
| Mutation or load tests | `running-mutation-tests`, `load-and-performance-testing` |
| `.github/workflows/**`, Dockerfile | `deploying-the-application`, `implementing-infrastructure-as-code` |
| Logging, metrics, tracing | `implementing-observability` |
| Hosting, health checks, shutdown | `managing-application-lifecycle` |
| Caching | `implementing-caching-strategies` |
| CLI tools | `creating-cli-tools` |
| `kb/chunks/**` | `writing-kb-chunks`, `reviewing-kb-chunks` |
| `questions/records/**` | `recording-decisions` |
| `docs/slices/**` | `planning-vertical-slices` |
| `.claude/**` | `maintaining-agent-framework` |
| README, guides | `updating-external-docs`; CLAUDE.md: `updating-internal-docs` |

## Task keywords

| Task | Skill |
|------|-------|
| New feature end to end | `implementing-vertical-slice-features` |
| Plan or order work | `planning-vertical-slices` |
| Before asking or assuming | `recording-decisions` |
| Review a diff for drift | `detecting-regressions`, `verifying-cross-file-coupling` |
| Review docs | `reviewing-documentation` |
| Screen usability | `evaluating-usability` |
| Rough prompt | `writing-world-class-prompts` |
| Before push | `running-local-ai-review` |
| Review a PR | `pr-review` (slash command only) |

## Rules

- Qualitative fit, not a computed score. Strong match: use it. Several plausible: read their descriptions and pick the narrowest. None: say so; do not force a skill.
- A skill with `disable-model-invocation: true` runs only when the user types it.
- Several skills apply: order them data -> service -> endpoint -> client -> UI -> tests -> docs.
- If a row names an agent instead of a skill, recommend the agent.
- Never invent a skill name; only names in `SKILL-INDEX.md`.
