# Q&A KB - record rules

| Rule | Detail |
|------|--------|
| Search first | `qa-kb search` before asking or assuming; an existing `answered`/`decided` record settles the point |
| Record, do not stall | When KB and Q&A are silent or conflict, create a record with a `decider` and continue with unblocked work |
| Right decider | Business behaviour goes to the product owner (`BQ`), technical choice to the tech lead (`TQ`). Never ask the wrong role |
| Ids | `BQ-NNN`, `TQ-NNN`, `OD-NNN`; next free number; filename `<ID>.md`; ids never reused or renumbered |
| One question per record | State the question, the options (recommended first), and what work continues meanwhile |
| Record every answer | When a human answers in a session, write it in the record the same session: status, `## Answer` or `## Decision`, date, who. Never leave an answer only in chat |
| History is append-only | Add dated lines under `## History`; do not rewrite earlier lines. Supersede a decision with a new `OD`: set the old record to `closed` and add a line "Superseded by <id>" under `## History`. Statuses are only `open`, `answered`, `decided`, `closed` |
| Link | `related` for records, `chunks` for the business KB; lint fails on unresolved ids |
| Contradiction | If a new answer contradicts a business KB chunk, open a `BQ`/edit task for the chunk via `documentation-curator` |
| Who writes | An agent that holds Write records the BQ/TQ itself; an agent without Write returns `questions_to_record` and the calling session (or `documentation-curator`) writes them |
| Fields | `answered:` (date) and `example: true` are optional; see `questions/README.md` |
| Cite | Code comments, docs and PR text cite the ids a decision rests on |

Lint with `python3 scripts/kb/check_chunks.py`. Reviewers check that every behaviour claim in a change traces to a chunk or a record.
