---
chunk_id: QF-032
title: Adopting the Quorum template step by step
topics: [adoption, process]
links: [QF-010, QF-011, QF-028]
sources: ["docs/concepts/10-adopting-the-template.md", "README.md", "scripts/kb/README.md"]
---
Adopting Quorum follows twelve steps, each with a check.

1. Create your repository from the template, keeping the folder layout because agents, skills and docs refer to each other by path.
2. Activate the framework files: agents, skills, hooks and settings already live in `.claude/`, and the MCP registration in `.mcp.json`. Install the pre-commit hook and run `python3 scripts/framework_lint.py`.
3. Replace every `{{PLACEHOLDER}}`: product name, objective, technical lead, product owner and `RUNNER_LABEL`. Check that `grep -rn "{{" .` returns nothing unintended.
4. Remove the Acme Orders example domain once the pipeline works end to end.
5. Seed the business knowledge base with your first 10 to 30 chunks, starting with the rules most likely to be misunderstood, and run `scripts/kb/check_chunks.py`.
6. Seed the questions knowledge base with open BQ and TQ records and past OD decisions; an empty one is fine.
7. Optionally bootstrap PostgreSQL with `pgvector`. Keep the connection string in an environment variable, never in a committed file. Ingest applies the schemas itself.
8. Run `scripts/kb/ingest.py` for pgvector, then check that a plain-language query finds the expected chunk. Local BM25 search returns nothing for an unwritten topic, but the default hash stub in pgvector mode still returns its nearest chunks, so use a real embedding model before relying on it.
9. Register `business-kb` and `qa-kb` in `.mcp.json`, restart Claude Code and confirm their tools respond.
10. Set up CI: add the repository secret `ANTHROPIC_API_KEY` and the variables `RUNNER_LABEL` and optionally `AI_REVIEW_MODEL`, set `MAX_ROUNDS` in the workflow if needed, enable the AI review workflow and make it a required check. Try `python3 scripts/ai_review_local.py --dry-run` first.
11. Run a first slice through the full lane, watching at least one review finding loop.
12. Tune models and effort after a few pull requests, one agent at a time, never lowering a reviewer below its author's tier.

Prerequisites: Claude Code, the .NET 10 SDK, Node, Python 3.11 or later, a GitHub repository and, for pgvector, PostgreSQL 16 or later with `pgvector`.
