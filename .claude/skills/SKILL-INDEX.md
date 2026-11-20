# Skill index

The only catalogue of skills. Each row: purpose and the agents that use it. `main` = the main session or any agent that needs it. See [README.md](README.md) for what a skill is.

## Backend

| Skill | Purpose | Used by |
|-------|---------|---------|
| backend | Minimal API endpoints with authorization, error handling, DTO/service integration | code-engineer, quality-guardian, security-engineer |
| creating-application-services | DI-registered services with correct lifetimes; interfaces only at real seams | code-engineer |
| creating-dtos-and-validation | Request/response record DTOs with FluentValidation or DataAnnotations | code-engineer, security-engineer |
| creating-configuration-options | Options pattern, validated at startup; no hard-coded values | code-engineer, infrastructure-engineer, security-engineer |
| creating-cli-tools | System.CommandLine admin and CI tools (check "When NOT to build" first) | code-engineer |
| implementing-caching-strategies | Caching only for a measured need; memory vs distributed | code-engineer, solution-architect |
| implementing-observability | Structured logs, metrics, traces (OpenTelemetry, JSON logs), alerts | code-engineer, infrastructure-engineer, security-engineer |
| managing-application-lifecycle | Host startup/shutdown, background services, health checks, draining | code-engineer, infrastructure-engineer |

## Data

| Skill | Purpose | Used by |
|-------|---------|---------|
| database | EF Core entity and configuration conventions for PostgreSQL, tenancy wiring | code-engineer, quality-guardian, security-engineer |
| writing-postgresql-migrations | Generate, review, apply EF Core migrations safely (additive first) | code-engineer, quality-guardian, security-engineer |
| tuning-postgresql-queries | Measure queries on a lab database, read plans, accept changes with evidence | test-automator |
| scaling-performance-test-data | Build and verify scaled lab datasets for performance work | test-automator |

## Delivery and infrastructure

| Skill | Purpose | Used by |
|-------|---------|---------|
| deploying-the-application | Container image, CI stages, migrate step, deploy by digest, rollback, base images | infrastructure-engineer, code-engineer, security-engineer |
| implementing-infrastructure-as-code | Every infrastructure resource as reviewed code in the recorded IaC tool | infrastructure-engineer, security-engineer |

## Frontend

| Skill | Purpose | Used by |
|-------|---------|---------|
| frontend | Standalone Angular components, signals, OnPush, strict TypeScript, explicit states | code-engineer, ux-usability-specialist, security-engineer |
| managing-state-with-signals | Shared state with signal stores, computed, effects | code-engineer |
| creating-angular-api-clients | Typed HttpClient services and central error handling | code-engineer |
| evaluating-usability | Task-scoped walkthrough, heuristics, states, microcopy, UX acceptance criteria | ux-usability-specialist |

## Testing and quality

| Skill | Purpose | Used by |
|-------|---------|---------|
| creating-xunit-tests | xUnit v3 unit tests with built-in Assert, AAA | test-automator |
| writing-integration-tests | WebApplicationFactory plus Testcontainers PostgreSQL | test-automator |
| writing-angular-tests | Vitest and TestBed component and service tests | test-automator |
| writing-playwright-e2e-tests | End-to-end journeys with role-based locators | test-automator |
| running-mutation-tests | Stryker.NET gate on hot-path logic | test-automator |
| load-and-performance-testing | k6 load, stress, smoke with threshold gates | test-automator |
| detecting-regressions | Regression taxonomy: contract drift, sibling parity, config coupling, silent swallowing | regression-detective |
| verifying-cross-file-coupling | DTO to TS, EF to SQL, config to chart, pins, formula duplication | regression-detective, documentation-reviewer |

## Documentation and knowledge

| Skill | Purpose | Used by |
|-------|---------|---------|
| reviewing-documentation | Grounding, completeness, correctness review of a doc (read-only) | documentation-reviewer |
| updating-internal-docs | Terse style for CLAUDE.md, agent and skill bodies | documentation-curator |
| updating-external-docs | Natural-language style for READMEs, guides, release notes | documentation-curator |
| writing-kb-chunks | Style rules for embedding-retrieved KB chunks | documentation-curator |
| reviewing-kb-chunks | Read-only critic pass for KB chunks | documentation-reviewer |
| recording-decisions | Recall before asking; record BQ, TQ, OD in the Q&A KB; flag is not ask | all agents, requirements-analyst |
| writing-world-class-prompts | Refine a rough request into a structured prompt | prompt-engineer |

## Planning, process and framework

| Skill | Purpose | Used by |
|-------|---------|---------|
| implementing-vertical-slice-features | Build one feature end to end in the right file order | code-engineer, solution-architect |
| planning-vertical-slices | Plan as slices: ids, dependencies, readiness, priority, rungs, INDEX | requirements-analyst, solution-architect |
| running-local-ai-review | Required local AI review before push (no API key, capped rounds; with the in-session pair it is the gate) | main, code-engineer |
| pr-review | Rules for the GitHub review and the local review prompts: tiers, comment format, round cap, escalation (never auto-triggered) | quality-guardian, regression-detective (via CI) |
| maintaining-agent-framework | `scripts/framework_lint.py`, size budgets, freshness, evaluating framework changes | documentation-curator, main |
| routing-to-skills | Map a task or path to the right skills | main, any agent |
