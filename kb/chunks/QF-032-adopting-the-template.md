---
chunk_id: QF-032
title: Adopting the Quorum template step by step
topics: [adoption, process]
links: [QF-010, QF-011, QF-028]
sources: ["docs/concepts/10-adopting-the-template.md", "README.md", "scripts/kb/README.md"]
---
Adopting Quorum follows twelve steps, each with a check.

1. Create your repository from the template, keeping the folder layout because agents and docs refer to each other by path.
2. Activate the framework files already in `.claude/` and `.mcp.json`: install the pre-commit hook and run `python3 scripts/framework_lint.py`.
3. Replace every placeholder: product name, objective, technical lead, product owner, the optional privacy owner (or delete its row), `RUNNER_LABEL`, `REALM` and, once the platform is recorded as a TQ or OD, `DEPLOY_TARGET`. Find them with `grep -rnE '\{\{[A-Z_]+\}\}' --exclude-dir=node_modules --exclude-dir=.git .`; only the generic `{{PLACEHOLDER}}` wording, reference notes, example records and a kept `DEPLOY_TARGET` should remain.
4. Remove the Acme Orders example domain once the pipeline works end to end: run `python3 scripts/kb/remove_examples.py` (dry run), then `--apply`, rewrite the passages it still lists, delete the example slices and replace the Orders sample code with your first real feature.
5. Seed the business knowledge base with 10 to 30 chunks and run `scripts/kb/check_chunks.py`.
6. Seed the questions knowledge base with open BQ, TQ and past OD records.
7. Optionally bootstrap PostgreSQL with `pgvector`. Install `psycopg` in a virtual environment and start Claude Code with it activated.
8. Run `scripts/kb/ingest.py` for pgvector and check that a plain-language query finds the expected chunk.
9. Register `business-kb` and `qa-kb` in `.mcp.json`, restart Claude Code and confirm their tools respond.
10. Set up CI: the required review is local (the in-session pair plus `python3 scripts/ai_review_local.py --base origin/main --require`, no API key). Optionally enable the GitHub second gate: set the repository variable `AI_REVIEW_ENABLED` to `true`, create the environment `ai-review` (required reviewers, prevent self-review) and add the environment secret `ANTHROPIC_API_KEY`; otherwise it is skipped and green is not a review.
11. Run a first slice, under the next free VS id, through the full lane.
12. Tune models and effort after a few pull requests, never lowering a reviewer below its author's tier.

Prerequisites: Claude Code, the .NET 10 SDK, Node, Docker (integration tests), Python 3.11 or later, a GitHub repository and, only for the optional pgvector backend, PostgreSQL 16 or later with `pgvector` and `psycopg`.
