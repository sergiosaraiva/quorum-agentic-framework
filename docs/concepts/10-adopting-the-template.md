# 10. Adopting the template

This is the step-by-step path from the template repository to a project that uses it. Follow it in order; each step has a check so you know it worked. Commands are examples; verify them against the files they name, because the scripts are the source of truth.

## Prerequisites

| Need | Notes |
|------|-------|
| Claude Code installed and signed in | Agents, skills and MCP servers run in it |
| .NET 10 SDK, Node (current LTS) and npm | Backend and Angular frontend |
| PostgreSQL 16+ with the `pgvector` extension | A local Docker container is enough to start |
| Python 3.11+ (`python3`) | KB scripts, framework lint and the local AI review |
| A GitHub repository and an Anthropic API key available as a secret | For the GitHub AI CI; never committed |
| An embedding provider or local model | Only for pgvector search that is semantic; the default hash stub is not (see `scripts/kb/README.md`) |

## Steps

### 1. Fork or copy the template

Create your repository from the template (fork, or "use this template"). Keep the folder layout: the agents, skills and docs refer to each other by path.

### 2. Activate the framework files

The agents, skills, hooks and settings already live in `.claude/`, and the MCP registration in `.mcp.json`. Install the pre-commit lint hook with `bash .claude/hooks/install-framework-check-hook.sh` and check the result with `python3 scripts/framework_lint.py`.

### 3. Replace the placeholders

Search for `{{` across the repo and replace each one.

| Placeholder | Meaning |
|-------------|---------|
| `{{PRODUCT_NAME}}` | Your product's name; used in `CLAUDE.md`, `kb/README.md` and the page `<title>` in `frontend/src/index.html` |
| `{{OBJECTIVE}}` | One paragraph: what, for whom, which phase, what gate ends it |
| `{{TECH_LEAD}}`, `{{PRODUCT_OWNER}}` | The people who answer technical and business questions |
| `{{RUNNER_LABEL}}` | CI runner label; set the `RUNNER_LABEL` repository variable too |
| `{{REALM}}` | Identity-provider realm in the example issuer URL in the doc comment of `src/Api/Options/AuthOptions.cs` |
| `{{PLACEHOLDER}}` | Generic wording in `CLAUDE.md`, `README.md`, the slides and two QF chunks; not a real token to replace |

Check: `grep -rn '{{[A-Z_]*}}' . --exclude-dir=.git --exclude-dir=node_modules` lists only the generic `{{PLACEHOLDER}}` wording and these docs.

### 4. Remove the example domain

The business KB ships with a few example chunks about "Acme Orders" and `questions/records/` may contain example records, all marked as examples. Keep them until the pipeline works end to end, then delete them and the example sample code you do not need.

### 5. Seed the business KB

Write your first 10 to 30 chunks in `kb/chunks/`, following `kb/CLAUDE.md` and [02](02-business-knowledge-base.md): one topic each, self-contained, with `sources`. Start with the rules most likely to be misunderstood. Run the chunk checker (`python3 scripts/kb/check_chunks.py`) to validate format and links. Delegate the writing to documentation-curator and the review to documentation-reviewer so the process is exercised from day one.

### 6. Seed the Q&A KB

Record what you already know is open (`BQ-`, `TQ-`) and decisions already made (`OD-`), each with a decider, following [03](03-questions-and-decisions-kb.md). An empty Q&A KB is fine; agents will fill it.

### 7. Bootstrap PostgreSQL (optional)

Local search needs no database. For pgvector, run `cp .env.example .env`, set your own password, export it with `set -a; source .env; set +a`, and start the container with `docker compose up -d`. Keep the connection string in an environment variable or user secrets, never in a committed file. You do not apply `kb/schema.sql` or `questions/schema.sql` by hand: `scripts/kb/ingest.py` applies them, with the vector dimension taken from `EMBED_DIM`.

### 8. Ingest (pgvector only)

Run `python3 scripts/kb/ingest.py` for both KBs; each run re-embeds everything. Then check with a search (`scripts/kb/search.py`) that a plain-language query returns the chunk you expect. With the default hash stub a query on something you did not write still returns the nearest chunks, so silence is only detectable by reading the results (and on the local BM25 backend, which returns nothing without a keyword match). Use a real embedding model before relying on semantic search. Re-run ingest whenever chunks or records change.

### 9. Register the MCP servers

`.mcp.json` at the repo root (from step 2) registers `business-kb` and `qa-kb`, each launching `python3 scripts/kb/mcp_server.py` with the right arguments; add `--backend pg` (or `KB_BACKEND=pg`) and the database environment variables if you use pgvector. Restart Claude Code, then in a session list the tools and confirm `mcp__business-kb__search` and `mcp__qa-kb__search` respond. If they do not, agents fall back to reading files and lose ranked search; fix this before relying on the gate in [04](04-never-invent.md).

### 10. Set up CI

Add the repository secret `ANTHROPIC_API_KEY` (and any AWS role identifiers for OIDC) and the variables you need: `RUNNER_LABEL` (default `ubuntu-latest`) and optionally `AI_REVIEW_MODEL` (default `opus`). The round cap is `MAX_ROUNDS` in the workflow `env` (default 3); edit it there. The workflow pins each action to a commit SHA with the tag in a comment; re-resolve the SHA when you bump an action. Enable `.github/workflows/ai-pr-review.yml` and make its check required on the integration branch. The frontend CI job runs only once `frontend/package-lock.json` exists (see `frontend/CLAUDE.md`). Try the local script first: `python3 scripts/ai_review_local.py --dry-run`. See [08](08-ai-ci-local-and-github.md).

### 11. Run your first slice

Pick a small capability. Add it to `docs/slices/INDEX.md` as `VS-001`, run the readiness analysis (S1 to S5) with the template in `docs/slices/templates/`, record any gaps as questions, and build rung R1 to R4 through the full lane. Use the one-line pipeline statement at the start, let the review pair run in parallel, and open the PR. Watch the local and GitHub reviews work through at least one finding loop. [06](06-vertical-slices-and-planning.md) explains the flow.

### 12. Tune models and effort

Start with the defaults in `docs/reference/model-selection-and-costs.md` (Opus at high effort for the judgement-heavy reviewers, architect, UX and security; Sonnet for producers and for documentation-reviewer; Haiku for prompt sharpening). After a few PRs, look at cost per review round and at findings that reached the PR review but should have been caught earlier. Move one agent at a time and compare. Do not lower a reviewer below its author's tier.

## Checklist

| Done | Item |
|------|------|
| [ ] | Repository created from the template; placeholders replaced |
| [ ] | `python3 scripts/framework_lint.py` and `python3 scripts/kb/check_chunks.py` pass |
| [ ] | Root `CLAUDE.md`: objective, roles, immutable rules reviewed by the team |
| [ ] | Sub-`CLAUDE.md` files read and adjusted to your stack choices |
| [ ] | First business chunks written, reviewed, checked |
| [ ] | (Optional) PostgreSQL with `pgvector` running; ingest applied both schemas |
| [ ] | Search finds a known chunk; you know what an unknown topic returns on your backend |
| [ ] | `.mcp.json` registers both servers; tools respond in a session |
| [ ] | Secrets and variables set in the repository; none in the code |
| [ ] | AI review workflow enabled and required; local script runs |
| [ ] | First slice analysed, built, reviewed and merged |
| [ ] | Models and effort reviewed after the first few PRs |

## Pitfalls

| Pitfall | Consequence | Avoid by |
|---------|-------------|----------|
| Skipping the KB seed | Agents have nothing to ground in and every gap becomes a question | Write the first chunks before the first slice |
| Embedding model or dimension changed after ingest | Search returns garbage or errors | Fix the model and the vector column size together; re-ingest everything after a change |
| Copying the example domain's rules as if they were yours | Invented behaviour in your product | Delete example chunks once real ones exist |
| Reviewers given write tools | Independence lost ([07](07-independent-validation.md)) | Keep allow-lists as shipped |
| Large PRs | Review tools truncate or skip; findings are shallow | Cut rungs small |
| Secrets in `.mcp.json` or `.env` committed | Leak | Use environment variables; keep `.env` gitignored |
| Trusting a green AI review as approval | Reviewers miss things | Keep the human merge decision |
| Letting `CLAUDE.md` grow without limit | Context cost on every session | Move procedures to skills ([05](05-claude-md-files.md)) |
| Editing agent and skill files directly | Unreviewed changes to the rules that govern everything | Delegate to documentation-curator and the review pair |

## When something is wrong

Agents give stale or wrong guidance: fix the instruction file, not just the output. A claim has no source: record a question. The loop hits its three-round cap: stop and re-examine the requirement or design, as [01](01-overview-and-pipeline.md) describes.
