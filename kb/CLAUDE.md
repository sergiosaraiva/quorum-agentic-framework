# Business KB - authoring rules

Chunks in `kb/chunks/` are embedded and retrieved one at a time. Write each so it makes sense alone.

| Rule | Detail |
|------|--------|
| One topic per chunk | If the title needs "and", split it |
| Self-contained | Name the subject in full; no "as above", no pronoun without a noun; define terms on first use |
| Length | 40 to 350 words (lint enforces); aim for 80 to 300 |
| Frontmatter | `chunk_id` (`BC-NNN`, unique, filename starts with it), `title`, `topics`, `links`, `sources` (never empty); optional `example: true` |
| Links | Only to chunks that exist; link related rules, not everything. Lint fails on a dangling link |
| Sources | Where the claim comes from (spec, interview, regulation, code path). A claim with no source is a question: record a BQ in `questions/` instead |
| Facts only | State behaviour, rules, numbers. No history, no opinions, no filler, no marketing words |
| No duplication | Say a rule once; link to it. Two chunks stating the same rule drift apart |
| Examples | Chunks with `example: true` are demo content; remove them when real chunks exist |
| Conflicts | If a chunk disagrees with code, a spec or another chunk, do not pick a winner: record a BQ with the right `decider` |

After any change run `python3 scripts/kb/check_chunks.py --write-toc` and re-ingest if you use the pgvector backend. Edits go through `documentation-curator` then `documentation-reviewer`; the author never approves its own chunk.
