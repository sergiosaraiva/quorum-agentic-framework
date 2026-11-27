# {{PRODUCT_NAME}} - Project Guide

A web product: .NET 10 backend, Angular frontend, PostgreSQL. Replace every `{{PLACEHOLDER}}` when you adopt this template. Statements here are design intent, not verified fact, where no code has landed.

## Objective

`{{OBJECTIVE}}`: one paragraph. What the product does, who uses it, the current phase, and the gate that decides the next phase.

## Working Style (Autonomy and Answers)

Single owner of these rules; other files point here. They never waive the Immutable Rules, Design Principles or mandatory gates.

| Topic | Rule |
|-------|------|
| Act by default | Recall prior decisions first (search `qa-kb`). Ask only when the records do not settle it and you are blocked on a decision that is the user's: product behaviour where the KB, spec and prototype conflict or are silent, a scope change, a destructive or outward-facing action the request did not cover. Otherwise take the conventional option, state the choice in one line, continue |
| Flag is not ask | "Flag it" and "do not guess" mean: record the item (BQ business question, TQ technical question, PR description) and carry on with what is unblocked. They do not mean stop |
| Batch questions | When a stop is warranted, finish all unblocked work, collect every open item, ask once in a numbered list, recommended option first. Never one question per turn |
| Standing authorizations | A change (Spike lane: local only) ends with branch, commit (Commit Metadata), push, PR into the integration branch, and, outside the Trivial lane (`_SHARED-PATTERNS.md`), the AI review loop until a round is clean (local rounds before the first push, cap 5 via `--max-rounds`, then a human; plus the GitHub rounds, cap `MAX_ROUNDS` in `.github/workflows/ai-pr-review.yml`, default 5, when `ANTHROPIC_API_KEY` is set). Merge only when asked |
| Environment | Do not trust a header saying "not a git repository": run `git rev-parse --is-inside-work-tree` before skipping a git step |
| Answers | Lead with the result or decision, then only the detail needed to act. Gloss an internal id (VS-, BQ-, TQ-, OD-) in a few words the first time it appears |

## Never Invent (Grounding Rule)

Every product, business or behaviour claim rests on a record, not on recall.

1. Consult `business-kb` (MCP: `search`, `chunk`, `graph_traverse`, `stats`) for what the product must do, and `qa-kb` (MCP: `search`, `get`, `open`, `related`) for questions already asked and decisions already made.
2. Cite the chunk ids or record ids a decision rests on, in the code comment, doc or PR.
3. If both KBs are silent or disagree, record a question (BQ-nnn for a business owner, TQ-nnn for a technical owner) with a `decider`, and continue with unblocked work. Never fill the gap with a guess.
4. The producer of a change never approves it: independent reviewer agents validate it (see Agent Workflow).

## Team and Communication

| Role | Person | Answers |
|------|--------|---------|
| Technical lead | `{{TECH_LEAD}}` | architecture, tooling, framework upkeep |
| Product owner | `{{PRODUCT_OWNER}}` | business behaviour, scope, priorities |
| Privacy or compliance owner (optional; delete this row if none) | `{{PRIVACY_OWNER}}` | data classification, personal data in logs and URLs, retention |

Technical questions go to the technical role, business questions to the business role, data-classification and privacy questions to the privacy role (the product owner if the row is deleted); record the question with the right `decider`. One person holding several roles still answers each record in the role it belongs to (OD-022). Business readers get outcome first in plain language, ids last in brackets; technical readers get ids, paths, commands, diffs.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | .NET 10, C# 14, ASP.NET Core Minimal APIs, EF Core + Npgsql |
| Database | PostgreSQL 16+, pgvector for the KBs |
| Frontend | Angular (latest major), standalone components, signals, plain CSS/SCSS |
| Auth | Any OIDC identity provider issuing JWTs; the API validates, the product authorizes (`Auth` options in `src/Api`) |
| Deployment | A container image plus a target you choose (`{{DEPLOY_TARGET}}`), recorded as a TQ, never guessed; all infrastructure is defined as code (`infrastructure-engineer` agent) |
| CI/CD | GitHub Actions; deploy with short-lived credentials where the platform supports them, no long-lived keys in the repo (`.github/workflows/`) |
| Observability | OpenTelemetry (OTLP), structured JSON logs; the backend is the adopter's choice (`implementing-observability` skill) |
| Testing | xUnit v3 built-in `Assert`, Testcontainers (PostgreSQL), Vitest, Playwright, k6, Stryker.NET |

## Architecture Style

Vertical slices, not layered horizontals. A feature owns its DTOs, service, endpoints, entity configuration and Angular component, in one feature folder.

Layout: `src/Api` (host, `Features/<Feature>/{Endpoints,Service,Dtos}.cs`), `src/Infrastructure`, `src/Domain` (design intent; grows when logic outgrows CRUD), `tests/`, `frontend/` (`src/app/{features/<name>,core,shared}`), `docs/`, `kb/`, `questions/`, `scripts/`, `.claude/`.

## Design Principles

1. **Simplest design that meets the stated requirement.** No speculative generality; defer and record what was deferred.
2. **Reuse first; an abstraction needs a present reason**: 2+ real consumers or a real seam (external I/O, test boundary). Rule of three before extracting shared code.
3. **No hard-coded values in logic** (URLs, ids, thresholds, limits, timeouts, page sizes, tenant or environment values): typed validated Options, the database, or deployment configuration. Secrets never in source.
4. **Vertical slice by default**; add a layer or project only to remove duplication or coupling that exists now.
5. **Prefer built-in platform features** over custom code or a new dependency.
6. **Ease of change**: small cohesive units, one reason to change, intent-revealing names.
7. **Design output states** the simplest viable option, why each extra layer or config is needed (or "none"), and what is deferred.
8. **Principles never waive the Immutable Rules** or required concerns (auth, validation, migration review, secrets, observability).

## Immutable Rules

Non-negotiable. Change this list only when the team explicitly changes the rule.

1. **No secrets in source control.** Local: `dotnet user-secrets` or a gitignored `.env`. Deployed: the platform's secret store. Placeholders such as `${ENV_VAR}` in examples.
2. **Every EF Core migration is reviewed before it touches a shared environment.** No `EnsureCreated()` outside local dev and tests.
3. **Every infrastructure resource is defined as code**, never created by hand in a console.
4. **Nullable reference types are enabled project-wide**; no `!` suppression without a comment saying why the compiler is wrong.
5. **Angular components are standalone**; no new `NgModule`-based feature.
6. **No `any` in TypeScript** without a justifying comment; `strict: true`.
7. **Every externally reachable endpoint makes an explicit auth decision** (`RequireAuthorization()` or a documented reason it is anonymous).
8. **Every CI job runs on the pinned runner label** `{{RUNNER_LABEL}}` (repo variable `RUNNER_LABEL`, default `ubuntu-latest`); reviewers do not flag it as an unknown label.

## Multi-CLAUDE.md Map

The nearest `CLAUDE.md` to the file you edit wins; it adds to, never contradicts, this file. Add a sub-guide only for non-obvious conventions; keep this root bounded.

| File | Layer |
|------|-------|
| [`src/Api/CLAUDE.md`](src/Api/CLAUDE.md) | endpoints, options, auth, error shape |
| [`src/Infrastructure/CLAUDE.md`](src/Infrastructure/CLAUDE.md) | EF Core, naming, migration workflow |
| [`frontend/CLAUDE.md`](frontend/CLAUDE.md) | Angular conventions, tests |
| [`docs/CLAUDE.md`](docs/CLAUDE.md) | prose rules for docs |
| [`docs/slices/CLAUDE.md`](docs/slices/CLAUDE.md) | slice planning and status upkeep |
| [`tests/CLAUDE.md`](tests/CLAUDE.md) | test conventions |
| `kb/CLAUDE.md`, `questions/CLAUDE.md` | KB chunk and Q&A record authoring |

## Agent Workflow

```
requirements-analyst -> solution-architect -> [ux-usability-specialist] -> code-engineer
                                                   |
                                                   v
                                  quality-guardian || regression-detective   (parallel)
                                                   |
                                                   v
                                            test-automator
                                                   |
                                                   v
                                  documentation-curator -> documentation-reviewer
```

`security-engineer` and `infrastructure-engineer` run proactively on auth, data, API, secret or infra changes. `prompt-engineer` runs on request.

Before any coding or documentation task, state the pipeline in one line, with a few words of reason per skipped stage, for example: `Pipeline: full lane - requirements-analyst skip (small scope) - code-engineer -> QG||RD -> test-automator - docs: none - KB check: done (BC-001) - Alignment Gate: applies (src/)`.

Loop-back rule: findings return to the producing agent; at most 5 re-loops per gate chain (`_SHARED-PATTERNS.md`), then escalate to a human. Reviewers report evidence (file plus anchor, line optional and never in stored docs, plus a failing scenario), never a bare verdict. Lanes (Trivial, Iterate, Full, Spike) and the severity-to-blocking mapping: `.claude/agents/_SHARED-PATTERNS.md`.

## Delegation Is Required

Beyond a trivial one-line fix, delegate; the producer never reviews its own work.

| Target | Delegate to |
|--------|-------------|
| `src/`, `frontend/` | full pipeline above (`infrastructure-engineer` for infrastructure and deployment config) |
| `kb/**` chunks | `documentation-curator` then `documentation-reviewer` |
| `.claude/agents/**`, `.claude/skills/**`, this file's governed sections | `documentation-curator`, then `quality-guardian` || `regression-detective`, then `documentation-reviewer` |
| `docs/**`, `README.md` | `documentation-curator` then `documentation-reviewer`; generated files are regenerated, never hand-edited |
| `scripts/**` | `code-engineer` |

Before the first push (not Trivial) run the local AI review: `python3 scripts/ai_review_local.py --base origin/main --require` (exit 2 if no `claude` or no new commits; required with the in-session pair; no API key; `--model opus` for auth, data model, migrations, money, core logic). The GitHub review is an optional second gate that runs only when `ANTHROPIC_API_KEY` is set; without it the job is skipped and its green check is not a review. A human merges.

## Verification Commands

```bash
dotnet build Quorum.slnx && dotnet test --solution Quorum.slnx && dotnet format Quorum.slnx --verify-no-changes   # backend (tests run on Microsoft.Testing.Platform)
(cd frontend && npm ci && npm run build && npm test)              # frontend
python3 scripts/framework_lint.py                                 # agents and skills: frontmatter, names, sizes, shared rules
python3 scripts/kb/check_chunks.py                                # KB chunks and Q&A records
python3 -m unittest discover -s scripts/kb/tests                  # KB tooling tests
python3 -m unittest discover -s scripts/tests                     # framework lint and local review tests
python3 scripts/ai_review_local.py --dry-run                      # print the review prompt
```

## Commit Metadata

Exactly one line in the commit body, never the title: `AI:<TOOL> W<with> N<no> L<loc%>`, for example `AI:CC W15 N30 L70`. `TOOL`: `CC` Claude Code, `NA` no AI, other tools by your own code. `W` minutes with AI, `N` minutes purely without AI, `L` percent of changed lines the AI wrote. Estimates by whoever commits, minutes rounded to 5. A `Co-Authored-By` trailer goes after the AI line.
