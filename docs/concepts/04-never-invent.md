# 04. Never invent

The most expensive failure of an AI team is not a syntax error; it is a confident, plausible, wrong behaviour that nobody asked for. "Never invent" is the rule that prevents it. It is stated once in the root `CLAUDE.md` and repeated, in role-specific form, in every agent.

## The rule

Every product, business or behaviour claim must rest on a record. The record is a chunk in the business KB (`business-kb`) or a question or decision in the Q&A KB (`qa-kb`). An agent follows four steps:

1. Consult both KBs before relying on recall.
2. Cite the chunk ids and record ids the decision rests on, in the code comment, the design, the doc or the PR.
3. If the KBs are silent or disagree with each other or with the code, say so and record a question (`BQ-nnn` for a business owner, `TQ-nnn` for a technical owner) with a `decider`. Do not fill the gap with a guess.
4. Carry on with whatever is not blocked by the gap.

The rule covers behaviour (what the product does), not craftsmanship. Choosing a conventional variable name or the standard ASP.NET Core way to validate a DTO needs no record.

## Silence is a finding

If `search` returns nothing relevant, the agent runs `stats` to see whether the topic is covered at all, then treats the result as information: the KB does not say. It does not conclude that anything is allowed. Conflict is treated the same way. If a chunk says 30 days and the code says 45, neither is assumed right; both are cited in a new question.

## "Flag" is not "ask"

Many rules say "flag it" or "do not guess". They mean one thing: record the item (a question record, the PR description, a deferred list) and continue with what is unblocked. They do not mean stop and wait for a human. Stopping is reserved for a small set of cases.

| Situation | Action |
|-----------|--------|
| A record settles it | Use it, cite it |
| A record is open | Link to it, proceed on its stated default, do not ask again |
| Nothing recorded, the choice is conventional and reversible | Choose the conventional option, state the choice in one line, continue |
| Nothing recorded, the answer changes product behaviour | Record the question with a decider, proceed with unblocked work |
| Blocked on a decision that is the user's: ambiguous product behaviour, a scope change, a destructive or outward-facing action the request did not cover | Finish all unblocked work, then ask once with every open item in a numbered list, recommended option first |

Never one question per turn. A session that asks "should I proceed?" after a plan the user already requested has failed the rule in the opposite direction.

## The Pre-Development Alignment Gate

Before the first line of a pull request that changes source, frontend or tests, the specification is checked against the KB as it is now, because the KB changes while work is queued. The steps:

| # | Step | Detail |
|---|------|--------|
| 1 | Scope | List the spec parts the change implements, with every cited `chunk_id` |
| 2 | Re-fetch | `chunk` each cited id; `search` (with `topic`, or `--topic` on the CLI, to stay in the domain; see rule 7 in `_SHARED-PATTERNS.md`) and `graph_traverse` for new chunks; `stats` for silence |
| 3 | Recall | Search the Q&A KB for recorded decisions and answers on the same topic |
| 4 | Classify | Confirmed (KB agrees with the spec), Contradicted (they disagree, or a decided record says otherwise), KB silent (no chunk, `stats` checked) or Missing (the KB requires it, the spec omits it) |
| 5 | Resolve | Contradicted or Missing: stop the affected change and return all items to the session (a spec fix or one batched owner question); a recorded owner decision settles it. KB silent: proceed and mark "unverified in KB". Never implement against a known conflict |
| 6 | Record | The alignment result: chunk ids, conflicts, silences, recalled record ids (or `none found: <queries>`). Before a PR exists it travels in each review prompt and is kept in the slice spec or the session hand-off; the PR description then carries it in an `Alignment check` section |

The gate does not apply to a PR that only changes docs, scripts, CI or agent files; such a PR states `Not applicable: <reason>` instead of an alignment result. A code PR that implements no specified behaviour writes `Alignment check: not applicable: <reason>`. If the KB tools are down, agents use the fallback in `_SHARED-PATTERNS.md` (Never Invent rule 7): the command line `scripts/kb/search.py` where they have Bash, direct reading of `kb/chunks/` and `questions/records/` where they do not. If neither is possible, authoring agents stop at this step and read-only reviewers list the check as unverified: analysing from memory is exactly what the rule forbids. An agent that does not write records itself (every agent except requirements-analyst, solution-architect and documentation-curator) returns the open items as `questions_to_record` to the calling session instead of recording or asking itself.

## Examples

Acme Orders has chunk `BC-003` (refund within 30 days after delivery of a line). The task: "allow refunds after delivery problems".

| Behaviour | Verdict | Why |
|-----------|---------|-----|
| Searches the KB, finds BC-003, notes it does not mention delivery problems, records a business question (for example `BQ-010`: "Do delivery problems extend the 30-day window?") with the product owner as decider, implements the standard path and a configuration value for the window, comments `// BC-003, BQ-010 default 30 days` | Right | Grounded, gap recorded, unblocked work done, no hard-coded guess |
| Decides that delivery problems extend the window to 60 days because "that is typical" | Wrong | An invented business rule presented as fact |
| Stops and asks the owner a question in chat before searching either KB | Wrong | Asking before recalling; the answer may already exist |
| Finds `BQ-010` open from last week, proceeds on its default and cites it | Right | Recall before ask |
| Writes a doc stating "refunds are processed within 2 days" with no source | Wrong | Unsupported claim; the doc reviewer would block it |
| Finds BC-003 says 30 days and a spec page says 45; implements 30 silently | Wrong | A conflict must be recorded and flagged, not resolved by pick |
| Asks the owner five related questions in one numbered message after finishing the unblocked work | Right | Batch, recommended option first |

## How the framework enforces it

| Mechanism | Where |
|-----------|-------|
| Rule stated in the root file | `CLAUDE.md` section "Never Invent (Grounding Rule)" |
| KB tools in the agents' tool allow-lists | Agent frontmatter (`mcp__business-kb__*`, `mcp__qa-kb__*`) |
| Anti-hallucination block shared by all agents | `.claude/agents/_SHARED-PATTERNS.md` |
| Alignment check section in each code PR | PR description, checked by the local AI review (and the GitHub review when enabled) |
| Reviewers verify cited ids exist and say what the code claims | quality-guardian, documentation-reviewer |
| Citation format (file path plus anchor, never a bare line number that drifts) | Shared patterns |

The practical test for any claim an agent makes: can a reviewer follow the citation and find the same statement there? If not, the claim is an invention.

Related: [02](02-business-knowledge-base.md), [03](03-questions-and-decisions-kb.md), [07](07-independent-validation.md).
