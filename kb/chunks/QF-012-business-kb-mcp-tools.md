---
chunk_id: QF-012
title: Business knowledge-base MCP tools and how agents cite them
topics: [business-kb, mcp, citation]
links: [QF-010, QF-011, QF-015, QF-016]
sources: ["scripts/kb/mcp_server.py", "scripts/kb/search.py", "docs/concepts/02-business-knowledge-base.md", ".claude/agents/_SHARED-PATTERNS.md"]
---
The server `business-kb` is `scripts/kb/mcp_server.py --kb business`, registered in `.mcp.json` and read-only. It exposes four tools, which appear in agent frontmatter as `mcp__business-kb__<tool>`:

| Tool | Use |
|------|-----|
| `search` | Find chunks by query, with an optional topic filter and result count `k` (at most 50); returns ids, titles, scores and snippets. Ranking is BM25 locally and vector distance on pgvector |
| `chunk` | Fetch one chunk in full by id |
| `graph_traverse` | Walk the `links` of a chunk to a given depth (at most 10); links are treated as undirected |
| `stats` | Counts of chunks, words, edges and per-topic totals, used to judge whether silence means the topic is not covered |

The command-line equivalent is `scripts/kb/search.py` with `--get`, `--graph` and `--stats`.

Agents follow a fixed sequence: `search`, then `chunk` on the hits, then `graph_traverse` for neighbours, and `stats` when a search returns nothing. They cite only ids retrieved in the current session, never ids recalled from memory. Citations appear in code comments, designs, docs and the `Alignment check` section of the pull request description. Reviewers re-fetch cited ids, and a citation that does not exist is a finding.

If the MCP tools are unreachable, an agent reads the same files with `python3 scripts/kb/search.py` (`--kb qa` for the Q&A KB, `--topic` to narrow the search) and says so. If the command line fails too, an authoring agent stops and returns to the session; a read-only reviewer lists the chunk verification as skipped and unverified, never as a pass. No agent proceeds from memory. Links are authored deliberately, so a missing link between related chunks is a documentation defect that makes graph traversal miss neighbours.
