# Pipeline trial findings: VS-004 R1

Record of a trial of the Quorum pipeline on the example slice VS-004 R1 (order search and filters), run on 2026-11-19 on branch `feat/pipeline-trial-slice`. The slice spec and design are in `docs/slices/VS-004-order-search-and-filters.md`; the questions and decisions it raised are in `questions/records/` (BQ-003 to BQ-008, TQ-003 to TQ-009, OD-002 to OD-006). All data is the invented "Acme Orders" domain.

How to read the evidence. A claim marked "repo" was checked against the files cited on 2026-11-19. A claim marked "trial log" comes from the agents' friction logs and reports in the trial session; the repository does not contain it, so it is stated as reported, not as verified.

Priority: High = blocks following the framework as written (two rules give opposite instructions, so an agent cannot comply with both). Medium = ambiguity or a misleading example that costs time. Low = polish.

## 1. What was run

One person played every role (technical lead and product owner). The agents ran as general-purpose subagents that read the agent files; they were not registered agent types (see G2).

| Stage | Agent (model it was launched with; effort not set per agent) | Result in one line |
|---|---|---|
| Readiness analysis | requirements-analyst (sonnet) | VS-004 analysed; found that the landed code contradicts `BC-001` (status values) and that `BC-005` has no counterpart in the Order entity; raised BQ-003, BQ-004, BQ-005 (sort order), BQ-006 (result visibility), TQ-003, TQ-004 |
| Owner decisions | owner | OD-002 to OD-006 recorded; VS-005 created for status alignment; R2 (status filter) deferred behind it |
| Design (R1) | solution-architect (opus) | Chose string binding plus a strict parser, `ILike` with LIKE-escaping, no new index; design stored in the slice spec |
| Implementation | code-engineer (sonnet) | Date-range and customer-name filters on `GET /api/orders`; INDEX moved to `In progress` |
| Review round 1 | quality-guardian and regression-detective (opus) in parallel | NUL-character 500 and a self-comparing test (quality-guardian); error-key casing drift and INDEX/spec drift (regression-detective) |
| Security review | security-engineer (opus) | Search cost, customer name in URLs, result visibility; recorded as TQ-007, BQ-008, BQ-006 raised to P1 |
| Tests and mutation | test-automator (sonnet) | Backend integration tests ran against PostgreSQL through Docker on WSL; 11 hand mutations, 2 survived the original suite (removing the `Id` tiebreak), now killed |
| Fix commit | code-engineer | NUL rejected with a 400; tests and records updated (`fix(orders): reject NUL in the name filter ...`) |

Repo evidence: the two commits `feat(orders): filter and search the order list (VS-004 R1, example slice)` and `fix(orders): reject NUL in the name filter ...`; the revision log in `docs/slices/INDEX.md`; the records listed above. Trial log only: the agent-by-agent model and effort used, the 11 mutations and their results, and the Docker/WSL test run.

## 2. What the pipeline caught that would have shipped

| Stage | Catch | Evidence |
|---|---|---|
| requirements-analyst | The landed `OrderConfiguration` allows `open`, `paid`, `cancelled`; `BC-001` defines `draft`, `placed`, `paid`, `shipped`, `closed`. A status filter would have been built on the wrong values. Resolved as TQ-003, OD-004 and slice VS-005 | repo: `src/Infrastructure/Persistence/Configurations/OrderConfiguration.cs` (`ck_order_status`), chunk `BC-001` (`kb/chunks/BC-001-order-lifecycle.md`), `questions/records/TQ-003.md` |
| requirements-analyst | `BC-005` requires exactly one currency per order; the Order entity has no currency column, so an amount filter has no unit (TQ-004, open) | repo: chunk `BC-005`, `src/Infrastructure/Persistence/Entities/Order.cs` (no currency member), `questions/records/TQ-004.md` |
| solution-architect | Typed query-parameter binding on .NET 10: a malformed value gives a 400 with no body in Production and a 500 in Development, and `11/19/2026` is silently accepted. String binding plus a strict parser was chosen | repo: slice spec, design table row "Binding of the new parameters" |
| solution-architect | `ILike` needs LIKE-escaping (`\`, `%`, `_`); chosen over `ToLower().Contains` because the latter folds case in two places that can disagree on non-ASCII letters | repo: slice spec, design table; `src/Api/Features/Orders/OrdersService.cs` (`EscapeLikePattern`, `ILike`) |
| quality-guardian | `customerName=%00` returned a 500 because PostgreSQL rejects 0x00 in text; fixed with a 400 | repo: `src/Api/Features/Orders/Dtos.cs` (NUL check), `tests/Api.IntegrationTests/OrdersSearchTests.cs` (`%00` cases) |
| quality-guardian | A test compared the new code with itself, so it could not fail | trial log (the corrected test is in `OrdersSearchTests.cs`; the original is not in the repo) |
| regression-detective | `ValidationProblem` error keys: camelCase on GET (proven by the exact-key test) and, by code reading, C# member names on POST, hidden by a case-insensitive test. TQ-008 says the POST response body was not confirmed (TQ-009 likewise: the 500 for NUL in create was not run) | repo: `questions/records/TQ-008.md`, `questions/records/TQ-009.md` |
| regression-detective | INDEX and spec drift: the Mermaid class of VS-004 was still `proposed` after the status change | repo: `docs/slices/INDEX.md`, revision log row "Mermaid class corrected" |
| security-engineer | The `%term%` search costs two sequential scans per request, measured about 0.4 to 1.6 s at 1M rows (TQ-007) | repo: `questions/records/TQ-007.md` |
| security-engineer | Customer name travels in query strings and so in logs (BQ-008); any authenticated caller sees every order, a P1 question before non-staff identities can get a token (BQ-006) | repo: `questions/records/BQ-008.md`, `questions/records/BQ-006.md` |
| test-automator | 2 of 11 hand mutations survived the original suite: removing the `Id` tiebreak in the ordering | trial log; the tiebreak is asserted in `tests/Api.IntegrationTests/OrdersSearchTests.cs` |

## 3. Findings in the framework

### A. Knowledge-base access

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| A1 | The KB MCP tools were not available in the session. The shared rules say stop; the quality-guardian says skip chunk verification and continue | `.claude/agents/_SHARED-PATTERNS.md`, section "Never Invent: KBs and Recorded Questions", rule 7 ("KB MCP unreachable: stop"); `.claude/agents/quality-guardian.md`, row "KB unreachable" | Two agents follow opposite rules in the same session; the pipeline either halts or proceeds ungrounded | One rule in `_SHARED-PATTERNS.md`; agent files point to it | High |
| A2 | No sanctioned fallback to the command-line KB tools, although they work (`search.py` with `--kb qa`, `--get`, `--open`, `--graph`, `--related`, `--stats`, `--topic`) | `scripts/kb/search.py`; `.claude/skills/recording-decisions/SKILL.md` ("Without MCP: Grep `questions/records/`") names grep only | Agents either stopped or grepped; the CLIs give the same answers as the MCP tools | State in the shared rule that `scripts/kb/search.py` is the approved fallback when MCP is down, with the equivalent flag for each tool | Medium |
| A3 | `.mcp.json` launches `scripts/kb/mcp_server.py` by a relative path, so the servers load only when the client starts in the repo root | `.mcp.json` | A session started from a parent folder has no KB tools (trial log: this was the trial's case) | Document the repo-root requirement in `docs/concepts/10-adopting-the-template.md` step on MCP, or use a path the client resolves from the project | Medium |
| A4 | KB search is noisy: framework chunks (`QF-*`) rank with the example domain chunks (`BC-*`), and no agent is told about `--topic` | `kb/chunks/`; `scripts/kb/search.py` (`--topic`); no agent body or skill mentions `--topic` | Domain queries return framework chunks first (trial log); the filter exists but is not discoverable | Mention `--topic` in the `recording-decisions` and alignment-gate guidance; consider separate folders or a default topic filter for adopters | Medium |

### B. Skills versus the landed sample code

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| B1 | `writing-integration-tests` shows `TestJwt`, `TestDatabase.Image` and `Assert.Contains(..., StringComparer.OrdinalIgnoreCase)` on error keys; the landed code uses `tests/Api.IntegrationTests/ApiFactory.cs` and has neither helper. The skill's case-insensitive assertion on error keys is the same pattern the reviewers named in TQ-008, where the VS-001 POST test also matches keys case-insensitively | `.claude/skills/writing-integration-tests/SKILL.md`; `tests/Api.IntegrationTests/ApiFactory.cs` | The skill example and the VS-001 test share the pattern that hid a real defect (inference: nothing shows the test was derived from the skill) | Show a case-sensitive key assertion and the real `ApiFactory`; or label the sample as illustrative | Medium |
| B2 | `creating-xunit-tests` says NSubstitute at I/O seams; `tests/CLAUDE.md` says no third-party mocking library unless a decision records one | `.claude/skills/creating-xunit-tests/SKILL.md` ("Doubles"); `tests/CLAUDE.md` ("Framework") | A conflict between a skill and the nearest CLAUDE.md; the CLAUDE.md wins, but the skill reads as permission | Align the skill with `tests/CLAUDE.md` | Medium |
| B3 | `running-mutation-tests` sample config lists only `tests/Api.UnitTests` as the test project, while the behaviour under test here shows only in integration tests | `.claude/skills/running-mutation-tests/SKILL.md`, section "Example: config" | Prediction, not observed: a run from the sample would report survivors that the integration suite kills. The sample `mutate` paths target example Billing code (`src/Api/Features/Billing/Pricing`), not the trial code | Include the integration test project, or say when each applies | Medium |
| B4 | `backend` skill prescribes `/api/v1/<feature>`, `PageRequest` and named policies; the landed code uses `/api/orders`, `PagedResponse` and `OrdersOptions` | `.claude/skills/backend/SKILL.md` (route group, pagination); `src/Api/Features/Orders/OrdersEndpoints.cs`, `Dtos.cs` | Code and skill disagree on route prefix and paging types; reviewers cannot tell which is the standard | Pick one and change the other; record it as an owner decision | Medium |
| B5 | `creating-dtos-and-validation` allows DataAnnotations or FluentValidation (FluentValidation recommended for cross-field rules); `backend` mentions FluentValidation only in a checklist caveat. The landed code uses `Validator.TryValidateObject` (DataAnnotations), which the skill permits, so only the skill's sample and the code's helper differ | `.claude/skills/creating-dtos-and-validation/SKILL.md`; `.claude/skills/backend/SKILL.md` (checklist); `src/Api/Features/Orders/OrdersEndpoints.cs` | Low: the code is within the skill; a reader may still expect FluentValidation | State that `TryValidateObject` with DataAnnotations is the default for simple rules | Low |
| B6 | `implementing-vertical-slice-features` lists "Backend-only or frontend-only change" under "Do not use", yet the agents route a whole feature to it and the slice was backend-only. It names test files `<Feature>EndpointTests.cs`; the trial files are `OrdersEndpointsTests.cs` and `OrdersSearchTests.cs` | `.claude/skills/implementing-vertical-slice-features/SKILL.md`, "When to Use / Not Use" and "The Sequence"; `.claude/agents/code-engineer.md` | An agent cannot tell whether to follow the skill for a backend-only slice | Add a backend-only variant of the sequence; relax the file naming to a pattern | Medium |
| B7 | The `.claude/skills` were not listed by the Skill tool in a session started outside the repo; agents read the `SKILL.md` files directly | trial log | Skill routing silently degrades; the lint cannot see it | Same fix as A3 and G2; document the fallback "read the file named in `SKILL-INDEX.md`" | Medium |

### C. Slice process

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| C1 | No exception mechanism for the hard-dependency pickup rule; the trial used an owner decision (OD-006) | `docs/slices/CLAUDE.md`, rule "Dependencies"; `docs/slices/VS-004-order-search-and-filters.md`, "Pickup condition" | A rule with no recorded way to waive it invites unrecorded waivers | State that an `OD` is the exception mechanism and where it is cited (spec and INDEX) | Medium |
| C2 | `Ready` requires zero open BQ/TQ blockers, yet VS-004 was `Ready for R1` with nine open non-blocking records (BQ-005, BQ-006, TQ-004, TQ-005, TQ-006, TQ-007, BQ-008, TQ-008, TQ-009; see the S5 table in the slice spec), and the rule does not say rung-level blockers (R2 behind VS-005) | `docs/slices/CLAUDE.md`, rule "Readiness before build"; `docs/slices/INDEX.md`, VS-004 row, section "Open blockers" | The slice's own INDEX had to explain why the rule did not apply | Define blocker versus non-blocking, and allow readiness per rung | Medium |
| C3 | No guidance for splitting a slice (VS-004 R1 and R2 plus new VS-005) | `docs/slices/IMPLEMENTATION-GUIDE.md` | Splitting was ad hoc | Add a short "splitting a slice" section: new id, dependency edge, what stays | Medium |
| C4 | Rung numbering clash: the guide's R0 to R4 mean spec, entity, service, client, journey; VS-004's R1 and R2 are filter increments | `docs/slices/IMPLEMENTATION-GUIDE.md`, section 2 "Rungs"; `docs/slices/INDEX.md` (VS-004 row) | "R1" means different things in the guide and the index | Say that a slice may define its own rung ladder, or rename the guide's rungs | Medium |
| C5 | No stated trigger for `Ready -> In progress`; the INDEX log says the guide moves it with the first code PR, but the guide does not say so | `docs/slices/CLAUDE.md` (status sequence); `docs/slices/IMPLEMENTATION-GUIDE.md` | Status changed by judgement | Add the trigger to the guide | Medium |
| C6 | The INDEX `Rung` column means "last rung merged", while the folder rule says each code PR records "status, rung reached" | `docs/slices/INDEX.md` (notes under the table); `docs/slices/CLAUDE.md`, rule "Every code PR updates `INDEX.md`" | VS-004 sat at `In progress` with `-` | Use one definition | Low |
| C7 | The example row VS-001 says PR `#1 (example)`, but `#1` is a real merged pull request in this repository | `docs/slices/INDEX.md` (VS-001 row); git history ("Merge pull request #1") | An invented number collides with a real one | Use a clearly fake reference such as `#0 (example)` or `n/a` | Low |
| C8 | The INDEX Mermaid `class` lines are edited by hand and not checked | `docs/slices/INDEX.md`, section 2; `scripts/framework_lint.py` checks agent and skill frontmatter and the skill index, and does not read `docs/slices` | Caught only by a reviewer (section 2 above) | Add a lint rule or generate the lines from the status column | Medium |
| C9 | The design lives in two places: the `Design` section of the slice template and `S3 Design` in the readiness analysis | `docs/slices/templates/slice.md`; `docs/slices/templates/readiness-analysis.md` | Drift risk; unclear which one is current | Keep one and link from the other | Low |
| C10 | Where the readiness analysis lives is ambiguous: `docs/slices/CLAUDE.md` says "append to the slice spec", the guide says "recorded with the template" | `docs/slices/CLAUDE.md`, "Files"; `docs/slices/IMPLEMENTATION-GUIDE.md`, section 4 | Minor | Say "appended to the slice spec" in both | Low |
| C11 | `requirements-analyst` has Write and Edit, but its body does not say it may create the slice spec or edit INDEX | `.claude/agents/requirements-analyst.md` (tools, Responsibilities) | Permission is implicit | Name the two files in its Does table | Low |

### D. Questions and decisions

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| D1 | The rule is one question per record, but reviews raise multi-part questions (BQ-006 has three options that are really three decisions) | `questions/CLAUDE.md`, rule "One question per record" | Agents split or bundle by guess | Say how to bundle options versus how to split questions | Medium |
| D2 | No rule says when an `OD` is mandatory, or who decides when one person holds both the technical and product roles | `.claude/skills/recording-decisions/SKILL.md`, "Record types"; `CLAUDE.md`, "Team and Communication" | OD-006 was decided by the product owner for a technical-looking exception | State the trigger and the single-owner rule | Medium |
| D3 | `related` ids are checked to resolve, but not for symmetry or relevance | `scripts/kb/check_chunks.py` (record rules); `questions/CLAUDE.md`, rule "Link" | Links are kept by hand and drift | Optionally warn on one-way links | Low |
| D4 | Concurrent agents and branches can take the same next id; the skill only says to check branches and PRs | `.claude/skills/recording-decisions/SKILL.md`, "Record every answer" | A merge collision renumbers ids that other records cite | Reserve ids per branch, or add a lint check for ids on sibling branches | Medium |
| D5 | Review ids (`SEC-001`, `RD-1`) are cited in records and the slice spec but do not exist anywhere stable | `questions/records/TQ-007.md`, `TQ-008.md` (History); `docs/slices/VS-004-order-search-and-filters.md` | A cited id cannot be looked up | Cite the record id only, or store review reports under a stable path | Medium |
| D6 | No place for a risk acceptance, which is not a question to anyone. The security-engineer says "record an accepted-risk decision" for Medium findings; the trial used open TQ/BQ records marked "accepted until answered" | `.claude/agents/security-engineer.md`, "Severity"; `docs/slices/VS-004-order-search-and-filters.md` (accepted items) | An open question and an accepted risk look the same in the KB | Define an accepted-risk use of `OD` with an expiry | Medium |
| D7 | `priority` P1 means "blocks work", but BQ-006 was raised to P1 while non-blocking; and History is append-only, so a priority change leaves the frontmatter and the History in two places | `.claude/skills/recording-decisions/SKILL.md` (field table); `questions/records/BQ-006.md` | The field has two meanings | Define P1 as "answer before a stated milestone" or add a blocks field | Low |

### E. Reviewer instructions

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| E1 | Severity tables conflict: security-engineer says Medium means "fix or record an accepted-risk decision"; the shared mapping says Medium does not block. The `detecting-regressions` rubric says confidence 0.50 to 0.79 is "still blocking", while the shared rule blocks only Critical and High | `.claude/agents/security-engineer.md`, "Severity"; `.claude/agents/_SHARED-PATTERNS.md`, "What blocks"; `.claude/skills/detecting-regressions/SKILL.md`, confidence rubric | Loop-back decisions differ by which file the orchestrator reads | Make `_SHARED-PATTERNS.md` the only source; map confidence to severity explicitly | High |
| E2 | Two finding schemas: the security-engineer JSON contract (`id`, `area`, `location` with a line, `confidence`) and the shared "Finding form" (`category`, `file` plus anchor, `scenario`, `fix`) | `.claude/agents/security-engineer.md`, "Context Contract"; `.claude/agents/_SHARED-PATTERNS.md`, "Finding form" | Consolidation across reviewers needs a mapping | One schema, extra fields optional | Medium |
| E3 | A missing alignment result for an in-scope change is a High finding for quality-guardian, but no storage location is stated before a PR exists. The Pre-Push Branch Gate appends the result to the reviewers' input and `code-engineer` returns the step 6 record, but the only named home is the PR description heading `Alignment check` | `.claude/agents/_SHARED-PATTERNS.md`, "Pre-Development Alignment Gate" (step 6) and "Pre-Push Branch Gate"; `.github/pull_request_template.md` | A missing result is a High finding, so the gap can block an otherwise clean diff | Say the result is passed in the review prompt and stored in the slice spec or a branch file until the PR exists | Medium |
| E4 | Reviewers may build and test per the agent files; the trial session used a shared build directory where a reviewer build would collide with the author's, and nothing says how to cite the author's run instead | `.claude/agents/quality-guardian.md`, "Bash"; `.claude/agents/_SHARED-PATTERNS.md`, "Bash for reviewers". The shared build directory itself is trial log only | Reviewers either skipped evidence or risked the build | State that a reviewer may cite the author's command output when a build would collide, and name the form | Medium |
| E5 | Commit scope versus whole-branch diff is unclear: the Pre-Push Branch Gate says whole branch, the quality-guardian input row repeats it, and reviews of a single commit are not addressed | `.claude/agents/_SHARED-PATTERNS.md`, "Pre-Push Branch Gate"; `.claude/agents/quality-guardian.md`, "Context Contract" | Reviewers review different ranges | One sentence on which range a mid-branch review uses | Medium |
| E6 | No guidance for a dirty working tree (uncommitted changes while reviewing a branch) | `.claude/agents/_SHARED-PATTERNS.md`; no agent file mentions it | Reviewers may read code that is not in the diff | State that reviewers review the committed diff and report a dirty tree | Medium |
| E7 | `regression-detective` has no code for docs and index drift (INDEX versus spec), which it found anyway | `.claude/agents/regression-detective.md` (taxonomy B1 to B6, C-series) | The category is found ad hoc | Add a docs-drift code, or assign it to documentation-reviewer | Medium |
| E8 | `security-engineer` prescribes no skills, unlike the other reviewers | `.claude/agents/security-engineer.md` (Skill tool is granted; no skill is named) | Inconsistent guidance | Name the relevant skills in its routing table | Low |
| E9 | The Team table has only a technical lead and a product owner, so data-classification and privacy questions (BQ-008) go to the product owner | `CLAUDE.md`, "Team and Communication" | A privacy question has no matching role | Add an optional privacy or compliance role the adopter may leave empty | Medium |
| E10 | `dotnet list package --vulnerable` queries a package source over the network; the rules say "no network calls with credentials" (security-engineer) and "a network call to production" (shared). Not a literal conflict, but unclear. Whether a reviewer may start a throwaway container is not addressed | `.claude/agents/security-engineer.md`, "Bash"; `.claude/agents/_SHARED-PATTERNS.md`, "Bash for reviewers" | Reviewers guess | State that public package-source queries are allowed, and say yes or no to throwaway containers | Medium |

### F. Tooling

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| F1 | No `dotnet-tools.json` manifest, so `dotnet ef`, which the design's migration check needs, is not guaranteed | repo root and `.config/` (no manifest); `.claude/settings.json` allows only `dotnet ef migrations list`, `migrations script`, `database update` and `database drop`; `dotnet ef migrations has-pending-model-changes`, the check named in the VS-004 design, is not in the allow list; `.claude/skills/writing-postgresql-migrations/SKILL.md` | A fresh checkout cannot run the check | Ship a tool manifest pinning `dotnet-ef` | Medium |
| F2 | Stryker.NET is not shipped (no config, no script), so mutation testing was done by hand. It worked, but neither an approved script nor a statement that hand mutation counts as evidence exists | `.claude/skills/running-mutation-tests/SKILL.md`; `tests/CLAUDE.md` ("Mutation testing"); `.claude/agents/test-automator.md` | The evidence format is undefined | Ship the Stryker config, or define "hand mutation log" as accepted evidence with a template | Medium |
| F3 | The test-automator output contract has a `coverage` object, but no coverage tool is shipped | `.claude/agents/test-automator.md` (output contract, "Coverage"); `src/`/`tests/` project files | The field cannot be filled from the repo | Ship coverlet configuration, or make the field optional | Medium |
| F4 | `solution-architect` has no Bash tool, but the binding and `ILike` decisions needed probes (the design records `ToQueryString()` checks) | `.claude/agents/solution-architect.md` (tools line); slice spec design table | The agent had to delegate or be given a tool ad hoc | Either grant a restricted Bash, or document the "ask the session to probe" step | Medium |
| F5 | Agent frontmatter `model` and `effort` do not apply to general-purpose subagents started from a session outside the repo | trial log | The model and effort tables in `docs/reference/model-selection-and-costs.md` are not enforced in that mode | Note the limit in `docs/concepts/09-agents-and-skills.md` | Medium |

### G. Environment

| Id | What happened | Where | Why it matters | Suggested fix | Priority |
|---|---|---|---|---|---|
| G1 | The session header reported "not a git repository" although git worked | trial log | Agents may skip git steps | Note in the agent files to test `git rev-parse` instead of trusting the header | Low |
| G2 | Skill and agent registration depends on starting the session in the repo root; the trial agents were not registered agent types | trial log; `.claude/` | Same cause as A3 and B7 | Start-up check in the adoption guide | Low |

## 4. Prioritised fix list

Selection rule: the two High findings come first (A1, E1). The rest are ordered by how directly a trial agent was blocked or misled, then by how many findings one change closes. Findings not listed here (A4, B7 beyond rank 6, C6 to C11, D1 to D3, D7, E5 to E10, F4, F5, G1) scored lower on both measures.

| Rank | Fix | Findings | Why first |
|---|---|---|---|
| 1 | One rule for "KB unreachable", with `scripts/kb/search.py` as the approved fallback | A1, A2 | Two rules disagree; the fallback already works |
| 2 | Single severity and blocking source in `_SHARED-PATTERNS.md`; map confidence and security Medium into it | E1, E2 | Loop-back decisions depend on it |
| 3 | Say where the alignment result travels before a PR exists | E3 | A missing result is a High finding for the reviewer, so the gap can block a clean diff |
| 4 | Fix the test skills: case-sensitive error-key assertion, real `ApiFactory`, one mocking rule, mutation config that includes integration tests | B1, B2, B3 | The skill example and the VS-001 POST test share the case-insensitive key matching that hid TQ-008 (inference; no evidence the test was derived from the skill) |
| 5 | Reviewer build and test: allow citing the author's run when a build would collide | E4 | Reviewers lose their main evidence source |
| 6 | Document the repo-root requirement for `.mcp.json`, skills and agents | A3, B7, G2 | One cause, three symptoms |
| 7 | Slice process: exception via `OD`, blocker definition, splitting, rung naming, status triggers | C1 to C5 | The trial had to improvise each one |
| 8 | Align `backend` and `creating-dtos-and-validation` with the landed sample code, and fix the "backend-only" wording | B4, B5, B6 | Reviewers cannot tell which is the standard |
| 9 | Accepted-risk decisions, id collisions and stable review ids | D4, D5, D6 | The KB records outlive the review sessions |
| 10 | Ship the tool manifest and decide on mutation and coverage evidence | F1, F2, F3 | Evidence the contracts ask for cannot be produced from a fresh checkout |

## 5. Limits of the trial

| Not tested | Detail |
|---|---|
| Frontend and UX | Backend only; no frontend slice rungs, no `ux-usability-specialist` stage, no Angular tests |
| More than one slice | One slice (VS-004 R1); the Docker/WSL integration test run worked once, on one slice (trial log) |
| Registered agents | Agents ran as general-purpose subagents reading the agent files; registered agent types, their tool allowlists and their frontmatter model and effort were not exercised |
| KB MCP servers | Never exercised; the command-line tools were used (see A1 to A3) |
| GitHub AI review | Not run: no `ANTHROPIC_API_KEY` in the trial (trial log); only the local review path applies (`docs/concepts/08-ai-ci-local-and-github.md`) |
| Multiple people | One owner played every role, so decider routing, hand-offs and approval separation were not tested |
| Real domain | The Acme Orders domain and its KB are invented, so KB noise and gaps on a real domain were not measured |
