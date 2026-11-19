---
chunk_id: QF-033
title: Which skills each Quorum agent uses
topics: [agents, skills]
links: [QF-005, QF-006, QF-007, QF-008, QF-019, QF-027]
sources: [".claude/skills/SKILL-INDEX.md", ".claude/agents/code-engineer.md", ".claude/agents/test-automator.md"]
---
The skill index `.claude/skills/SKILL-INDEX.md` has a "Used by" column that names the agents expected to load each of the 39 skills. Skills with no stage-specific user are loaded by the main session.

| Agent | Skills |
|-------|--------|
| requirements-analyst | `planning-vertical-slices`, `recording-decisions` |
| solution-architect | `planning-vertical-slices`, `implementing-vertical-slice-features`, `implementing-caching-strategies` |
| ux-usability-specialist | `frontend`, `evaluating-usability` |
| code-engineer | the build skills below, `implementing-vertical-slice-features`, `running-local-ai-review` |
| quality-guardian | `backend`, `database`, `writing-postgresql-migrations`; `pr-review` through CI |
| regression-detective | `detecting-regressions`, `verifying-cross-file-coupling`; `pr-review` through CI |
| test-automator | `creating-xunit-tests`, `writing-integration-tests`, `writing-angular-tests`, `writing-playwright-e2e-tests`, `running-mutation-tests`, `load-and-performance-testing`, `tuning-postgresql-queries`, `scaling-performance-test-data` |
| documentation-curator | `updating-internal-docs`, `updating-external-docs`, `writing-kb-chunks`, `maintaining-agent-framework` |
| documentation-reviewer | `reviewing-documentation`, `reviewing-kb-chunks`, `verifying-cross-file-coupling` |
| infrastructure-engineer | `deploying-the-application`, `implementing-infrastructure-as-code`, `creating-configuration-options`, `implementing-observability`, `managing-application-lifecycle` |
| prompt-engineer | `writing-world-class-prompts` |

`recording-decisions` is used by all agents and `routing-to-skills` by the main session or any agent.

code-engineer picks a skill by the path it edits: `*Endpoints.cs` uses `backend`; `Dtos.cs` and validators use `creating-dtos-and-validation`; `*Service.cs` uses `creating-application-services`; options classes and `appsettings*.json` use `creating-configuration-options`; `src/Infrastructure/Persistence/**` uses `database`; migrations use `writing-postgresql-migrations`; Angular components, stores and API clients use `frontend`, `managing-state-with-signals` and `creating-angular-api-clients`; a whole feature uses `implementing-vertical-slice-features`; a Dockerfile, workflow or infrastructure file uses `deploying-the-application` and `implementing-infrastructure-as-code`, with infrastructure handed to infrastructure-engineer.
