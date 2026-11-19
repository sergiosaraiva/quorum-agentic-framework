---
chunk_id: QF-010
title: Anatomy of a business knowledge-base chunk
topics: [business-kb, authoring]
links: [QF-011, QF-012, QF-007, QF-015]
sources: ["kb/CLAUDE.md", "kb/README.md", "scripts/kb/check_chunks.py", "scripts/kb/lib.py", ".claude/skills/writing-kb-chunks/SKILL.md"]
---
The Quorum business knowledge base is a folder of Markdown files in `kb/chunks/`, one chunk per file, named `<chunk_id>-<slug>.md`. Each chunk covers one topic and makes sense alone, because search returns chunks out of context.

Frontmatter fields:

| Field | Rule |
|-------|------|
| `chunk_id` | Unique, matching the pattern of two to four capital letters, a dash and at least three digits, for example `BC-001`; the filename must start with it |
| `title` | A noun phrase naming the one topic |
| `topics` | At least one topic; the table of contents groups chunks by topic |
| `links` | Ids of related chunks that exist; a link to itself or to a missing chunk fails the lint |
| `sources` | At least one entry saying where the claim comes from; a claim without a source is recorded as a question instead |
| `example` | Optional `true` marking demonstration content to delete once real chunks exist |

Length: the lint enforces a body of 40 to 350 words, and the authoring rules aim for 80 to 300. Style rules: the first sentence names the concept and already reads as an answer; state each fact once and link rather than repeat; use the same term for the same concept; no hedging, marketing words or meta-commentary.

The linter `scripts/kb/check_chunks.py` reports every violation, and `--write-toc` regenerates `kb/TOC.md`. Authoring goes through documentation-curator using the `writing-kb-chunks` skill, and review through documentation-reviewer using `reviewing-kb-chunks`; the author never approves its own chunk. If a chunk disagrees with code or another chunk, no winner is picked: a business question is recorded.
