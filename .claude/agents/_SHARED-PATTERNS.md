# Shared Agent Patterns

Single owner of the cross-agent rules; agent files and root `CLAUDE.md` restate only their own role. Skills named here live under `.claude/skills/<name>/SKILL.md` (index: `SKILL-INDEX.md`); verify before citing one. Size budget: 16 KB per agent file; new detail goes into a skill.

## Principles

| # | Principle | Consequence |
|---|-----------|-------------|
| 1 | Never invent | Every behaviour claim rests on a KB chunk or recorded decision; silence or conflict becomes a question |
| 2 | No single point of failure | The producer never approves its own work; a different role with fresh context and an equal or stronger model reviews it |
| 3 | Evidence over verdicts | A finding names `file` + anchor, a failing scenario and a severity |
| 4 | Vertical slices | One feature end to end, planned with ids in `docs/slices/` |
| 5 | Delegate | Product code goes through the pipeline; a direct edit skips review |

## Subagent Limits

A subagent cannot spawn agents or ask the user. "Re-invoke X", "ask the owner" and "involve Y" are instructions to the calling session. It returns open items (`questions_to_record`, blockers, recommended options) in its final message and continues with unblocked work. `requirements-analyst` and `solution-architect` have no `Bash` (Common Tool Permissions) and cannot probe: each lists a probe as a `probe_requests` entry (`command`, `expected`), never assumes the result, and the session runs it.

## Pipeline and Lanes

```
requirements-analyst -> solution-architect -> [ux-usability-specialist] -> code-engineer
     -> quality-guardian || regression-detective (parallel; + ux-usability-specialist for UI)
     -> test-automator -> documentation-curator -> documentation-reviewer
```

`security-engineer` and `infrastructure-engineer` run proactively on auth, data, API, secret or infrastructure changes. `prompt-engineer` runs on request, ahead of any agent.

| Lane | When | Stages |
|------|------|--------|
| Trivial | One-line fix, typo, no behaviour change | Edit directly; no gate |
| Iterate | Small, low-risk, reversible, one slice, no new contract, no migration, no auth/data/infra change. Example threshold (tunable): about 150 added lines, 5 files | `code-engineer`; review pair at the gate (before push); `test-automator` only for behaviour no test covers |
| Full | Anything else: new feature, contract change, migration, auth, multi-layer | Every stage above, per its skip reason |
| Spike | Throwaway exploration the owner explicitly asks for | Local only, no review, never merged; code is discarded or rebuilt through Full |

Before starting, state the pipeline in one line: lane, a few words of reason per skipped stage, whether the Alignment Gate applies (example: root `CLAUDE.md`, Agent Workflow).

## Never Invent: KBs and Recorded Questions

| Source | Server / path | Holds |
|--------|---------------|-------|
| Business KB | MCP `business-kb` (`search`, `chunk`, `graph_traverse`, `stats`); files `kb/chunks/*.md` | What the domain and product must do: rules, behaviours, definitions |
| Q&A KB | MCP `qa-kb` (`search`, `get`, `open`, `related`); files `questions/records/*.md` | Business questions (BQ), technical questions (TQ), decisions (OD), answers, deciders, status (`open|answered|decided|closed`) |

Rules:

1. Before relying on behaviour, `search` the Business KB, `chunk` the hits, `graph_traverse` neighbours; `stats` judges whether silence is real.
2. Before asking anyone or assuming, `search` the Q&A KB; `get` a record for its decision and history. A `closed` record whose History says "Superseded by <id>" points to the live one. A recorded decision settles what is built.
3. Cite `chunk_id`s and record ids retrieved this session.
4. KB and code or spec disagree, or both are silent: do not guess. Record a question and continue with unblocked work.
5. Record type: business or expected-behaviour question = BQ, `decider` a business role; technical question = TQ, `decider` the technical role. Who writes the record: an agent whose role includes question records (`requirements-analyst`, `solution-architect`, `documentation-curator`) writes it itself; every other agent returns it in `questions_to_record` and the session (or `documentation-curator`) writes it. Format: `questions/README.md`, skill `recording-decisions`.
6. "Flag" means record and continue. "Ask" means stop and ask, only when blocked on an owner decision no record settles, a scope change, or a destructive or outward-facing action the request did not cover. Batch every open item into one round, recommended option first.
7. KB MCP unreachable (sole statement; agent failure rows point here), in order:
   - First, agents with `Bash` use the CLI: `python3 scripts/kb/search.py "<query>" [--topic <t>] [--get <id>] [--graph <id> --depth N] [--stats]` (Business KB; framework `QF-*` chunks share `kb/chunks/`, `--topic` takes a topic from `--stats`; an unknown topic returns nothing and exits 0, which is not KB silence); `--kb qa` selects the Q&A KB (`--get`, `--open`, `--related <id>`). Then, any agent reads `kb/chunks/*.md` and `questions/records/*.md` with Read/Grep, losing BM25 ranking (local backend), `--graph`, `--related` and filters. State which was used.
   - Neither works (files unreadable), authoring agents (`requirements-analyst`, `solution-architect`, `code-engineer`, `test-automator`, `documentation-curator`, `infrastructure-engineer` and `ux-usability-specialist` when authoring or defining): stop and return to the session (`/mcp`); never proceed from memory.
   - Reviewing agents (`quality-guardian`, `regression-detective`, `security-engineer`, `documentation-reviewer`, `infrastructure-engineer` and `ux-usability-specialist` when reviewing): list `unverified: chunk verification skipped, KB unreachable` (fields: `docs/concepts/07-independent-validation.md`), never a pass; KB-dependent findings are unverified, not clean; continue the code checks.

## Pre-Development Alignment Gate (Mandatory)

Applies before the first line of any change to `src/`, `frontend/src/` or `tests/` that implements specified behaviour; once per change. Not for changes only to `.github/`, `scripts/`, `.claude/`, `docs/`, build files, Dockerfiles or generated output (state `Not applicable: <reason>`).

| # | Step | Detail |
|---|------|--------|
| 1 | Scope | List the spec parts the change implements, with every cited `chunk_id` |
| 2 | Re-fetch | `chunk` each cited id; `search` (MCP `topic` or CLI `--topic` narrows to the domain, rule 7) + `graph_traverse` for new chunks; `stats` for silence |
| 3 | Recall | Search the Q&A KB for recorded decisions and answers on the same topic |
| 4 | Classify | Confirmed (KB agrees with spec) / Contradicted (disagree, or a decided record says otherwise) / KB silent (no chunk, `stats` checked) / Missing (KB requires it, spec omits it) |
| 5 | Resolve | Contradicted or Missing: stop the affected change and return all items to the session (spec fix or one batched owner question). A recorded owner decision settles it. KB silent: proceed, mark "unverified in KB". Never implement against a known conflict |
| 6 | Record | PR description heading `Alignment check`: chunk ids, conflicts, silences, recalled record ids (or `none found: <queries>`) |

| Role | Duty |
|------|------|
| `requirements-analyst`, `solution-architect` | Steps 1-5 in analysis and design; hand the step 6 record on |
| `code-engineer`, `test-automator` (when the only change is under `tests/`) | First step of every in-scope change, unless the session passes a result produced this session for this change, which they confirm |
| `quality-guardian` | Verify the `chunk_id` claims in a passed alignment result against the KB. No result for an in-scope change (and no `Not applicable`) is a High finding |

## Design Principles (Binding on every agent)

Owner: the `## Design Principles` section of the root `CLAUDE.md`. Reviewers flag over-engineering, hard-coded values, and under-engineering breaking an Immutable Rule. Principles never waive an Immutable Rule or a required concern (auth, validation, migration review, secrets, observability).

## Mandatory Parallel Review Block

After `code-engineer` finishes, the session spawns `quality-guardian` and `regression-detective` in one message (UI paths: also `ux-usability-specialist`). `quality-guardian` owns pattern compliance, security, EF Core query safety, resource safety and all design findings; `regression-detective` owns B1-B6 and C1-C6; `ux-usability-specialist` owns usability of UI changes. `test-automator` runs after every reviewer in that message has returned (code artifacts) and consumes `test_would_catch` from `regression-detective`.

## Loop-Back Rule (Mandatory)

A blocking finding at a review gate returns to the artifact's writer, not forward.

| Gate | On blocking finding | On none |
|------|---------------------|---------|
| `quality-guardian` and/or `regression-detective` (code) | Re-invoke `code-engineer` with the consolidated findings of all reviewers spawned in that message; then re-run the pair again | `test-automator` |
| `test-automator` (code) | Re-invoke `code-engineer` with failing tests or gap; re-run the pair before re-running `test-automator` | Code pipeline complete; docs stage if docs change |
| `documentation-reviewer` (docs, `.claude/**`, KB chunks) | Re-invoke `documentation-curator`; re-run the reviewer | Done |

What blocks. This table is the only place that decides blocking; other files define severity labels and map them here. Among reported findings, severity alone decides, never confidence: 0.50-0.79 goes in `unverified` with its would-be severity (below 0.50: not reported). Unverified items never block; the session dispositions each like a non-blocking finding. A Medium security finding (from `security-engineer` or `quality-guardian`) does not block; if not fixed before merge, the session records it as an open BQ/TQ and, once the owner accepts the risk, as an OD with `accepted_risk` and `expires`.

| Reviewer | Blocks | Does not block |
|----------|--------|----------------|
| `quality-guardian`, `regression-detective`, `security-engineer` | Critical, High | Medium, Low, Info |
| `ux-usability-specialist` | Blocker, Major | Minor, Note |
| `documentation-reviewer` | status `ungrounded`, `fabricated-citation`, `stale`, `conflict` or `gate-failure` (reported at confidence >= 0.8) | other statuses, style findings |
| AI review (`pr-review` skill; local, and GitHub when `ANTHROPIC_API_KEY` is set) | `blocking` (local) / Blocker (GitHub) | Warning, Info |

- Never skip a stage because an earlier iteration passed it.
- Cap: 3 re-loops per gate chain. Still failing: stop, surface the pattern to the user once, batched. A single shared budget of 3 applies across both gates of a framework-doc change.
- Every non-blocking finding gets a disposition (fix, defer with a recorded item, or reject with a reason) in the hand-off; none is dropped silently.
Round counters share no state: skill `running-local-ai-review`, Counters.

## Independent Review Rule

| Rule | Detail |
|------|--------|
| Different role | Never the writer's role |
| Fresh context | Reviewers get the diff, the spec/design and the alignment result, not the writer's reasoning. |
| Model | The reviewer model is equal or stronger than the producer's. Judgement-heavy reviewers (quality, regression, security, architect, cloud, ux) run `opus`; `documentation-reviewer` runs `sonnet` (mechanical check; `docs/reference/model-selection-and-costs.md`) |
| Read-only | No Write/Edit on repository files (ux: scratch mockups only); Bash per Common Tool Permissions. They return findings in the form below |
| No anchoring | A prompt handing over a hypothesis ("confirm X is fine") is rewritten as a neutral task |

Finding form (every reviewer agent; contracts add only agent-specific fields): `id`, `category`, `severity` (Critical/High/Medium/Low/Info; ux scale and documentation-reviewer `status` map via "What blocks"), `file` + `anchor` (symbol or heading; `line` optional in review output, never in stored docs), `scenario` (evidence and failing input), `fix` (minimal), `confidence` (optional, default 1.0). A finding without a failing scenario is dropped.

Field `unverified` (optional list, every reviewer contract; defined here): one string per item, `unverified (would-be <severity-or-status>): what and why` for a finding at confidence 0.50 to 0.79, `unverified: <check>, <reason>` for a check that could not run. Never blocks; the hand-off dispositions each; mapping: `docs/concepts/07-independent-validation.md`.

| Severity | Meaning |
|----------|---------|
| Critical | Data loss or corruption, auth bypass, secret exposure, tenant leak, broken Immutable Rule |
| High | Wrong behaviour on a normal path, contract break, unbounded resource growth, a missing required control (no alignment result, no endpoint auth decision) |
| Medium | Wrong on an edge path, design violation |
| Low | Maintainability with a concrete cost; nothing else is reported |
| Info | Optional, non-blocking; security-engineer only |

## Pre-Push Branch Gate (Mandatory)

Before a branch's first push and after any later change, run `quality-guardian` || `regression-detective` over the whole branch diff against the base plus the alignment result, then `test-automator` for code. Then the local AI review (`python3 scripts/ai_review_local.py --base origin/main --require`, skill `running-local-ai-review`: no API key, `--model opus` for risky changes, cap 3, then a human). Pair plus local review is the gate; a human merges. The GitHub AI review (skill `pr-review`) is an optional second gate that runs only when `ANTHROPIC_API_KEY` is set (otherwise skipped; green is not a review); fix its findings (`MAX_ROUNDS`, label `needs-human-review`).

## Citation Format (Mandatory)

Stored artifacts (docs, specs, agent and skill bodies, CLAUDE.md) never cite line numbers: name the path plus a stable anchor (symbol, heading, test title, or a short quoted literal occurring once). Review output keeps `line` as a pointer.

## Anti-Hallucination Rules (All Agents)

1. Read a file before editing or reviewing it; Grep/Glob that a symbol, import, skill, agent or file exists before citing it.
2. Copy patterns from real files; cite the skill and section applied. No placeholders in code, no time estimates, no assumed decisions (recall first).
3. No real secrets in output; use `${ENV_VAR}`.
4. Never claim "tests pass" or "build succeeds" without its output.

## Skill Routing

Map changed paths to skills with `routing-to-skills` and `SKILL-INDEX.md`. Report a layer with no skill as a gap; do not improvise.

## Common Tool Permissions

| Agent class | Tools |
|-------------|-------|
| Writers (`code-engineer`, `test-automator`, `documentation-curator`, `infrastructure-engineer`) | Read, Write, Edit, Grep, Glob, Bash, Skill, KB read tools |
| Reviewers (`quality-guardian`, `regression-detective`, `documentation-reviewer`, `security-engineer`) | Read, Grep, Glob, Bash (read, build, test only), Skill, KB read tools. No Write/Edit |
| `ux-usability-specialist` | Reviewer tools plus `Write` for a scratch mockup pack in the OS temp directory only; never a repository file |
| Analysts (`requirements-analyst`, `solution-architect`) | Read, Grep, Glob, Skill, KB read tools; Write/Edit only for question records and the design or requirements document |
| `prompt-engineer` | Read, Grep, Glob, Skill; returns the refined prompt as text |

Bash for reviewers: build, test, lint, `git status|diff|log|show|blame`, read-only inspection. Never a write outside build output, `git commit|push|checkout|reset`, a package install, a production network call, or anything printing secrets.

## Known Non-Issues

Facts reviewers must not flag; each needs a reason and a recorded decision.

| Item | Why it is not an issue |
|------|------------------------|
| Runner label `${{ vars.RUNNER_LABEL \|\| 'ubuntu-latest' }}` in workflows | Adopters set the variable `RUNNER_LABEL` to their own runner pool (Immutable Rule 8) |
| `{{PLACEHOLDER}}` tokens in templates (`CLAUDE.md`, docs) | Adopters replace them |
| KB chunks and Q&A records with `example: true` | The Acme sample domain; the adopter replaces it |

## Verification Commands

Root `CLAUDE.md`, section Verification Commands.
