# Model selection and costs

This page tells you which Claude model to give each agent, why, and what it costs. Prices and model IDs change often. Treat every number here as a snapshot and check the [official pricing page](https://platform.claude.com/docs/en/about-claude/pricing) before you budget.

Page written 2026-11-18. Prices were re-verified on 2026-11-19 against the [Anthropic pricing page](https://platform.claude.com/docs/en/about-claude/pricing) (fetched 2026-11-19). Model ids, effort defaults and advisor rules come from the Anthropic API reference model table (a copy cached 2026-11-03). Prices still change often; re-check before you budget.

## 1. The Claude 5 family at a glance

All prices are US dollars per million tokens (MTok) on the first-party Claude API. Cloud platforms that resell the models bill at their own rates.

| Model | Model ID | Context | Input | Output | Cache read | Best for |
|---|---|---|---|---|---|---|
| Claude Fable 5.2 | `claude-fable-5-2` | 1M | $8.00 | $40.00 | $0.20 | The hardest reasoning and longest agent runs. Use it where an error is very expensive. |
| Claude Opus 5.5 | `claude-opus-5-5` | 1M | $4.00 | $20.00 | $0.20 | Review, architecture, security, and any judgment call. The default for "do not get this wrong". |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | 1M | $2.00 | $10.00 | $0.10 | Everyday coding, tests, documentation, requirements analysis. The default worker. |
| Claude Haiku 5.5 | `claude-haiku-5-5` | 1M | $0.10 | $0.50 | $0.01 | High-volume, simple work: classification, prompt sharpening, bulk triage. These prices apply to prompts up to 100K tokens; longer prompts are billed at $0.50 input, $2.50 output and $0.05 cache read. |

Cache-write prices, per MTok (a write costs more than plain input; reads are the cheap side):

| Model | 5-minute cache write | 1-hour cache write |
|---|---|---|
| Claude Fable 5.2 | $10.00 | $16.00 |
| Claude Opus 5.5 | $5.00 | $8.00 |
| Claude Sonnet 5.5 | $2.50 | $4.00 |
| Claude Haiku 5.5 (prompts up to 100K tokens) | $0.125 | $0.20 |
| Claude Haiku 5.5 (prompts over 100K tokens) | $0.625 | $1.00 |

Notes:
- All four models list a 1M-token context window in the API model table. The pricing page says the standard-pricing 1M window applies to models 4.6 and later, except Haiku 5.5, which is billed at the higher tier above 100K tokens.
- The Batch API gives a 50% discount for work that can wait (results arrive asynchronously, in any order).
- Prompt caching cuts the price of repeated prefixes (system prompts, CLAUDE.md, agent bodies, the KB context you resend). The cache-read column above is the discounted price, and its ratio to input differs by model (pricing page: 0.025x on Fable 5.2, 0.05x on Opus 5.5 and Sonnet 5.5, 0.1x on Haiku 5.5); the cache-write table gives the cost of writing the prefix, which is charged again whenever the cache has expired (5 minutes or 1 hour after the last use) and the prefix is written anew. Minimum cacheable sizes vary by model and are not listed here: check the pricing page.
- Fast mode runs the same model at up to 2.5x output speed for a premium: Opus 5.5 at $8 / $40 and Fable 5.2 at $16 / $80 per MTok. The premium stacks with the caching multipliers, and fast mode is not available with the Batch API. Use it for interactive sessions where waiting costs more than tokens, never for unattended CI.
- On Fable 5.2 and Opus 5.5, thinking cannot be switched off. Effort is the control. On Sonnet 5.5, `thinking: disabled` returns a 400 error; to turn thinking off, send type `between_tools` (only at effort `high` or below).
- Older models (Opus 4.x, Sonnet 4.6, Haiku 4.5) are listed on the pricing page at higher per-token prices than their 5.x successors (input and output both: for example Opus 4.5 at $5 / $25 against Opus 5.5 at $4 / $20, Sonnet 4.6 at $3 / $15 against $2 / $10, Haiku 4.5 at $1 / $5 against $0.10 / $0.50); Opus 4 and 4.1 are retired on some platforms. Move to the current generation unless you have a reason not to.
- In agent frontmatter, use the aliases `opus`, `sonnet`, `haiku`. They resolve to the current model of that tier, so you pick up new releases without editing every agent. Pin a full ID (for example `claude-opus-5-5`) only when you need reproducible evaluation runs.

## 2. When to use which model

| Situation | Use | Why |
|---|---|---|
| Independent review of someone else's work (quality, regression, security) | Opus | A reviewer must be at least as capable as the author. A weaker reviewer rubber-stamps. |
| Architecture and dependency-ordered planning | Opus | A wrong plan multiplies cost downstream. One expensive call saves many cheap rewrites. |
| Implementation from an approved design | Sonnet | The design carries the hard thinking. Sonnet is fast and cheap enough to iterate. |
| Writing tests, docs, KB chunks | Sonnet | Well-specified, verifiable by the reviewer that follows. |
| Requirements analysis and gap finding | Sonnet at high effort | Mostly structured reading of the KBs. Escalate to Opus for ambiguous multi-system specs. |
| Prompt sharpening, classification, routing, log triage, bulk summaries | Haiku | Cheap and quick. Output is checked or low-stakes. |
| A task that failed twice on Sonnet | Opus once, then return to Sonnet | Pay for judgment only where it is needed. |
| Hardest long-horizon work (large refactor plan, migration strategy, incident root cause) | Fable 5.2 | Highest capability. At $8 / $40 per MTok it is twice Opus input price, so reserve it. |
| Local AI CI before you push | Sonnet (the script default) | The required review with the in-session pair; no API key, capped at 5 rounds. Use `opus` for auth, data model, migrations, money or core logic. |
| GitHub AI CI on every PR (optional, needs `ANTHROPIC_API_KEY`) | Opus (the workflow default, overridable with the repository variable `AI_REVIEW_MODEL`) | An optional second gate. Do not economize on the reviewer. |

Rule of thumb: spend on the checker, save on the maker. Reviewer errors cost an escaped defect. Implementer errors cost a review round.

## 3. Default model per agent in this framework

| Agent | Model | Effort | Reason |
|---|---|---|---|
| requirements-analyst | sonnet | high | Structured gap analysis grounded in the KBs. |
| solution-architect | opus | high | Design errors are the most expensive errors. |
| ux-usability-specialist | opus | high | Judgment-heavy review. |
| code-engineer | sonnet | high | Implements a design that is already approved. |
| quality-guardian | opus | high | Independent reviewer. |
| regression-detective | opus | high | Independent reviewer. |
| test-automator | sonnet | high | Writes and runs tests. Verified by running them. |
| documentation-curator | sonnet | medium | Low-risk writing, then reviewed. |
| documentation-reviewer | sonnet | high | Checks grounding mechanically against sources, so Sonnet suffices. |
| security-engineer | opus | high | Security misses are the costliest. |
| infrastructure-engineer | opus | high | Infrastructure mistakes have a large blast radius. |
| prompt-engineer | haiku | n/a | Short, cheap, easy to inspect. |

The rule behind the table: the reviewer model is equal to or stronger than the producer's. Judgement-heavy reviewers (quality, regression, security, architect, infrastructure, ux) run Opus; documentation-reviewer runs Sonnet because the check is mechanical lookup. Change these by editing the `model:` and `effort:` lines in `.claude/agents/<name>.md`, then run `python3 scripts/framework_lint.py`.

## 4. Effort levels

Effort sets how much the model thinks and how many tokens it spends. It is the main quality-versus-cost dial inside one model. Levels `low`, `medium`, `high`, `xhigh` and `max` exist on all four models (source: Anthropic API reference, cached 2026-11-03). The per-model defaults named below come from the same source.

| Level | Typical use |
|---|---|
| `low` | Subagents with simple tasks, chat, classification, routing. |
| `medium` | Documentation, straightforward edits. The cost-saving step down where quality still holds. Opus 5.5 and Haiku 5.5 default to this level. |
| `high` | Coding, review, requirements analysis. The sweet spot for most agent work. Sonnet 5.5 and Fable 5.2 default to this level; start Fable 5.2 at `high`. |
| `xhigh` | Hard coding and agentic tasks where measured results improve; use it only where you have measured the gain. |
| `max` | Measuring a model's ceiling, or work where correctness matters more than cost. |

Guidance:
- Measure on real tasks before you raise a default. Tune per agent, not globally.
- Judge cost per finished task, not per request. A cheap call that needs three retries is not cheap.
- Lower effort on a newer model often matches the previous generation at high effort. Try that before building a model cascade, because caches are model-scoped and a cascade throws away cache reuse.
- Effort changes the cost of thinking tokens more than the length of the reply. Control reply length in the prompt.

## 5. The advisor pattern

An executor model does the work. A stronger advisor model is consulted at key points: before committing to an approach, when stuck, and before declaring done. You pay for the stronger model only on those few short calls.

- The advisor must be at least as capable as the executor. An invalid pair returns HTTP 400. A Sonnet 5.5 executor with an Opus 5.5 advisor is valid. A Fable 5.2 executor accepts only `claude-fable-5-2` or `claude-mythos-5-2` as advisor (Mythos 5.2 is limited availability: the pricing page says only organizations verified through Anthropic's verification programs can use it) (source: Anthropic API reference, cached 2026-11-03).
- This is the same idea as the framework's independent review, applied inside one task. Use the advisor for cheap early correction. Use the reviewer agents for the independent final check. Do not let an advisor replace the reviewers.

## 6. Cost levers, in the order to try them

1. Cache what repeats: system prompts, agent bodies, CLAUDE.md, KB context. Keep stable content first and volatile content last. Check `cache_read_input_tokens` to confirm hits.
2. Trim input: send diffs not whole files, KB chunks not whole documents, targeted `Grep` before `Read`. This is why the KBs return small, self-contained chunks.
3. Right-size the model per agent (section 3).
4. Right-size effort per agent (section 4).
5. Batch work that can wait (50% discount): nightly KB re-embedding, bulk chunk review, overnight regression sweeps.
6. Cap loops: the 3-round review cap bounds the worst case at a known number of calls.
7. Cap output: set `max_tokens` and ask for structured findings, not essays.
8. Use task budgets on long agent runs so the model paces itself instead of being cut off.
9. Run the local AI CI first so the optional GitHub review, if enabled, starts from clean diffs and ends in fewer rounds.

## 7. Worked example: cost of one review round

Illustrative only. Assume a PR diff plus context of 30,000 input tokens and 5,000 output tokens per reviewer call, no caching.

| Reviewer model | Input cost | Output cost | Per call |
|---|---|---|---|
| Opus 5.5 | 30,000 x $4 / 1M = $0.12 | 5,000 x $20 / 1M = $0.10 | $0.22 |
| Sonnet 5.5 | 30,000 x $2 / 1M = $0.06 | 5,000 x $10 / 1M = $0.05 | $0.11 |
| Haiku 5.5 | 30,000 x $0.10 / 1M = $0.003 | 5,000 x $0.50 / 1M = $0.0025 | $0.0055 |

The default pipeline runs two Opus reviewers in parallel (quality-guardian and regression-detective), so one round is 2 x $0.22 = $0.44 before thinking tokens, and a five-round cap bounds it at 5 x $0.44 = $2.20 for that stage. Haiku 5.5 is used here at prompts under 100K tokens; above that, the higher tier applies. Real runs add thinking tokens and tool calls, so measure your own. The point: a review round costs cents, an escaped defect costs hours.

## 8. Subscription plans versus API billing

Claude Code can run on a subscription plan or on API billing. A plan limits usage by allowance rather than by dollars per token, and the allowance differs by plan and changes over time. For CI you normally use an API key stored as a repository secret (`ANTHROPIC_API_KEY`) so that cost is metered per run. Check your plan's current terms before you rely on it for automation.

## 9. Keep this page current

- Re-check prices and model IDs each quarter, and whenever a new model ships.
- Record a change of default model or effort as an owner decision in the Q&A KB (see `docs/concepts/` on decisions), with the evidence that justified it.
- When a model is retired, update the agents that name it by full ID.
