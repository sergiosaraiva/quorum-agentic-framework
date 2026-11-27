---
chunk_id: QF-001
title: What Quorum is and why it exists
topics: [overview]
links: [QF-002, QF-015, QF-024]
sources: ["README.md", "docs/concepts/01-overview-and-pipeline.md", "docs/presentation/quorum-framework.md"]
---
Quorum is a template for building software with a team of Claude Code agents instead of a team of people, without giving up the controls a human team provides. It is made of twelve role-specific agents, about forty skills, `CLAUDE.md` guide files, two searchable knowledge bases, a vertical-slice planning method and two AI review loops, one local and one on GitHub. It ships with a reference stack of .NET 10, Angular and PostgreSQL, which an adopting team replaces or adjusts.

Quorum exists because a single AI coding assistant working alone has three failure modes:

| Failure | What it looks like |
|---------|--------------------|
| It invents | Plausible business rules, field names and behaviours nobody specified |
| It forgets | Yesterday's decision is argued again today or silently reversed |
| It self-approves | The author reviews its own diff and finds it fine |

Quorum answers each one. Agents consult a business knowledge base and a questions-and-decisions knowledge base, cite record ids, and record a question when both are silent. Every question, answer and decision is a searchable record, so nothing is lost in a chat. Independent reviewer agents with fresh context, no Write or Edit tools and an equal or stronger model validate every change, and after five failed review rounds (OD-031) a human decides.

The repository is a template: an adopting team replaces the `{{PLACEHOLDER}}` values in the root `CLAUDE.md`, deletes the invented Acme Orders example content and writes its own knowledge.
