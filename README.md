# Quorum: an agentic software engineering framework

Quorum is a template for building software with a team of [Claude Code](https://code.claude.com) agents that ground their work in a knowledge base, never invent, and never approve their own output.

It ships a working reference stack (.NET 10, Angular, PostgreSQL, AWS), twelve agents, 39 skills in seven groups, two searchable knowledge bases (BM25 and link graph locally, pgvector optional), a vertical-slice planning method, and two AI review loops (local and on GitHub).

Start with the slides: [docs/presentation/quorum-framework.md](docs/presentation/quorum-framework.md).

## Why

An AI assistant working alone tends to fail in three ways: it invents plausible rules nobody specified, it forgets earlier decisions, and it reviews its own work and finds it fine. Quorum answers each one:

| Failure | Quorum's answer |
|---|---|
| Invents | Agents consult two knowledge bases and cite ids. If both are silent, they record a question and continue with unblocked work. |
| Forgets | Every question, answer and decision is a record in a searchable Q&A knowledge base. Agents search it before asking. |
| Self-approves | Independent reviewer agents with fresh context, no Write or Edit tools (ux-usability-specialist: scratch Write only) and an equal or stronger model validate every change. Findings loop back, at most three rounds, then a human decides. |

## The ideas

1. **Business knowledge base** (`kb/`): small self-contained chunks describing what the product must do. Plain Markdown files searched locally (BM25 plus the link graph), or PostgreSQL with pgvector (vector distance only; with the default hash embedding stub it is not semantic). Served to agents through an MCP server (`business-kb`).
2. **Questions and decisions knowledge base** (`questions/`): business questions (BQ), technical questions (TQ) and owner decisions (OD), with deciders and history. Same dual backend, served as `qa-kb`.
3. **Never invent**: agents ground claims in those two sources, cite ids, and record a question rather than guess.
4. **Agents and skills** (`.claude/agents/`, `.claude/skills/`): twelve role-specific agents run in a pipeline. Skills hold the reusable how-to, loaded on demand.
5. **CLAUDE.md files**: a root guide plus small guides next to the code they govern. The nearest one wins.
6. **Vertical slices** (`docs/slices/`): plan features end to end with ids, dependencies, readiness analysis and priorities.
7. **Independent validation**: no single point of failure. The producer never approves its own work.
8. **Two AI CIs**: a local review script before you push, and a GitHub workflow on every pull request.
9. **Model and cost guidance**: which Claude model and effort level for each agent, with prices and levers. See [docs/reference/model-selection-and-costs.md](docs/reference/model-selection-and-costs.md).

## The pipeline

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

`security-engineer` and `cloud-infrastructure-engineer` run proactively on auth, data, API or AWS changes. `prompt-engineer` sharpens a prompt on request.

| Agent | Model | Role |
|---|---|---|
| requirements-analyst | sonnet | Find gaps, ground in the KBs, record questions |
| solution-architect | opus | Simplest viable design, ordered plan, slices |
| ux-usability-specialist | opus | Define or review flows and states |
| code-engineer | sonnet | Implement the approved design |
| quality-guardian | opus | Correctness, security, data-access safety (no Write or Edit tools) |
| regression-detective | opus | Contract drift, parity, duplicated logic (no Write or Edit tools) |
| test-automator | sonnet | Write and run tests |
| documentation-curator | sonnet | Write docs and KB chunks |
| documentation-reviewer | sonnet | Check docs are grounded (no Write or Edit tools) |
| security-engineer | opus | Auth, data, API and infrastructure security |
| cloud-infrastructure-engineer | opus | AWS, Helm, Argo CD, cost |
| prompt-engineer | haiku | Sharpen prompts |

## Repository map

```
CLAUDE.md                 root guide (rules, stack, pipeline, delegation)
.claude/agents/           the twelve agents + _SHARED-PATTERNS.md
.claude/skills/           39 skills, with SKILL-INDEX.md
.claude/settings.json     permissions
.claude/hooks/            pre-commit framework lint
.mcp.json                 registers the two knowledge-base servers
kb/                       business knowledge base (chunks, schema)
questions/                Q&A knowledge base (records, schema)
scripts/kb/               ingest, search, MCP server, chunk lint
scripts/framework_lint.py agent and skill lint
scripts/ai_review_local.py  local AI CI
.github/workflows/        ci.yml, ai-pr-review.yml
docs/                     presentation, concepts, reference, slices
src/ tests/ frontend/     sample vertical slice (Orders)
docker-compose.yml        PostgreSQL with pgvector
```

## Quick start

Prerequisites: [Claude Code](https://code.claude.com), .NET 10 SDK, Node.js, Python 3.11+, Docker (optional).

```bash
# 1. Try the knowledge bases with no database
python3 scripts/kb/check_chunks.py
python3 scripts/kb/search.py "refund after delivery"
python3 -m unittest discover -s scripts/kb/tests
python3 scripts/framework_lint.py

# 2. Optional: PostgreSQL with pgvector
cp .env.example .env            # then set your own password
set -a; source .env; set +a     # export the variables for the commands below
docker compose up -d
python3 scripts/kb/ingest.py    # applies the schemas itself; see scripts/kb/README.md for embedding options

# 3. Build and test the sample backend
dotnet build Quorum.slnx && dotnet test --solution Quorum.slnx && dotnet format Quorum.slnx --verify-no-changes

# 4. Open Claude Code in this folder; it reads CLAUDE.md and registers the MCP servers
claude
```

Install the pre-commit lint hook with `bash .claude/hooks/install-framework-check-hook.sh`.

The example knowledge-base content describes an invented "Acme Orders" domain. Replace it with your own.

## The two AI CIs

| | Local | GitHub |
|---|---|---|
| Entry | `python3 scripts/ai_review_local.py --base origin/main` | `.github/workflows/ai-pr-review.yml` |
| When | Before the first push | Every pull request |
| Reviewers | quality-guardian and regression-detective prompts | the same two reviewer agents, instructions read from the base branch |
| Model | default `sonnet`: a cheap rehearsal that does not replace the GitHub gate | default `opus`; repository variable `AI_REVIEW_MODEL` overrides |
| Cap | `--max-rounds`, default 3 | `MAX_ROUNDS` in the workflow, default 3, then label `needs-human-review` |
| Needs | the `claude` CLI | repository secret `ANTHROPIC_API_KEY` |

Local flags: `--base --model --max-chunk-bytes --max-rounds --out-dir --claude-bin --timeout --reset --dry-run`. Run `python3 scripts/ai_review_local.py --dry-run` to see the prompt without calling a model. The GitHub review posts one summary and up to 20 inline comments per round, with the reviewer instructions read from the base branch. It does not resolve threads, tier models by path or chunk large diffs; those are optional extensions, not implemented in the template.

## Documentation

| Read | For |
|---|---|
| [Presentation](docs/presentation/quorum-framework.md) | the whole framework in slides (Marp) |
| [01 Overview and pipeline](docs/concepts/01-overview-and-pipeline.md) | agents, lanes, parallel review |
| [02 Business knowledge base](docs/concepts/02-business-knowledge-base.md) | chunks, local and pgvector search |
| [03 Questions and decisions](docs/concepts/03-questions-and-decisions-kb.md) | BQ, TQ, OD records |
| [04 Never invent](docs/concepts/04-never-invent.md) | the grounding rule |
| [05 CLAUDE.md files](docs/concepts/05-claude-md-files.md) | root and sub-guides |
| [06 Vertical slices](docs/concepts/06-vertical-slices-and-planning.md) | planning, readiness, priorities |
| [07 Independent validation](docs/concepts/07-independent-validation.md) | no single point of failure |
| [08 Local and GitHub AI CI](docs/concepts/08-ai-ci-local-and-github.md) | the two review loops |
| [09 Agents and skills](docs/concepts/09-agents-and-skills.md) | what each is and how to write them |
| [10 Adopting the template](docs/concepts/10-adopting-the-template.md) | step-by-step setup |
| [Model selection and costs](docs/reference/model-selection-and-costs.md) | which model, what it costs |

## What is tested vs not

| Area | State |
|---|---|
| KB tooling (`scripts/kb`) | unit tests, run with `python3 -m unittest discover -s scripts/kb/tests`; chunk lint with `check_chunks.py` |
| Framework lint, local review script | unit tests under `scripts/tests/` (`python3 -m unittest discover -s scripts/tests`) |
| Sample backend (Orders) | xUnit unit and integration tests (Testcontainers needs Docker) |
| Frontend skeleton | has specs but needs `npm ci` first; the template does not ship a lockfile (see `frontend/CLAUDE.md`), so the CI frontend job is skipped until you add one |
| GitHub workflow `ai-pr-review.yml` | not run end to end in this template: it needs your repository, secret and a real PR; actions are pinned to commit SHAs (tag in a comment), re-resolve the SHA when you bump one |
| Agents, skills, hooks | linted for structure only; behaviour was not evaluated on real tasks |
| pgvector search quality | not measured; the default embedding is a hash stub |
| Prices and model ids in the cost doc | a snapshot, partly unsourced (marked "verify") |

## Status and caveats

- This is a starting point, not a product. Replace every `{{PLACEHOLDER}}` and the example domain.
- The default embedding provider is a deterministic hash stub for offline demos. It is not semantic. Configure a real embedding model before relying on vector search (see `scripts/kb/README.md`).
- Model prices, model ids and GitHub Action versions change. Items marked "verify" need a check against current official documentation.
- The Angular skeleton under `frontend/` was not built when the template was written. Create a lockfile with `npm install`, then `npm run build`.
- Workloads use default Helm values plus Argo CD. Other AWS resources (databases, caches, CDN) are the adopter's choice of tool; agents record a TQ instead of guessing.

## License

MIT. See [LICENSE](LICENSE).
