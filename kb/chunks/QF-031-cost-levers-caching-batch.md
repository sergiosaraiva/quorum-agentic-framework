---
chunk_id: QF-031
title: Cost levers, prompt caching and batch savings
topics: [cost, models]
links: [QF-030, QF-009, QF-027]
sources: ["docs/reference/model-selection-and-costs.md"]
---
The Quorum cost guide lists levers in the order to try them:

1. Cache what repeats, such as system prompts, agent bodies, `CLAUDE.md` and knowledge-base context. Keep stable content first and volatile content last, and confirm hits through `cache_read_input_tokens`.
2. Trim input: send diffs not whole files, chunks not whole documents, and targeted searches before reads. This is why the knowledge bases return small self-contained chunks.
3. Right-size the model per agent.
4. Right-size effort per agent.
5. Batch work that can wait.
6. Cap loops: the three-round review cap bounds the worst case.
7. Cap output with `max_tokens` and structured findings.
8. Use task budgets on long runs.
9. Run the local AI CI first so the paid GitHub review starts from clean diffs.

Prompt caching: the cache-read price is a fraction of the input price. In the prices verified on 2026-11-19 against the Anthropic pricing page, cache reads cost $0.20 per million tokens on Opus 5.5 and Fable 5.2 and $0.10 on Sonnet 5.5, against input prices of $4.00, $8.00 and $2.00. Cache writes cost more than input: on Opus 5.5, $5.00 for a 5-minute write and $8.00 for a 1-hour write. Minimum cacheable sizes vary by model and must be checked.

Batch: the Batch API gives a 50 percent discount for work that can wait, with results arriving asynchronously in any order. Suitable jobs are nightly knowledge-base re-embedding, bulk chunk review and overnight regression sweeps.

Worked example: with a 30,000-token input and 5,000-token output per call, an Opus 5.5 review costs about $0.22 and a Sonnet 5.5 review about $0.11, before thinking tokens. Two parallel Opus reviewers make about $0.44 per round, so a three-round cap bounds that stage at $1.32. Fast mode, a premium for output speed, suits interactive sessions and never unattended CI.
