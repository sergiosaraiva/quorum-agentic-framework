# Q&A KB - record rules

| Rule | Detail |
|------|--------|
| Search first | `qa-kb search` before asking or assuming; an existing `answered`/`decided` record settles the point |
| Record, do not stall | When KB and Q&A are silent or conflict, create a record with a `decider` and continue with unblocked work |
| Right decider | Business behaviour goes to the product owner (`BQ`), technical choice to the tech lead (`TQ`). Data-classification and privacy questions go to the privacy role when the root `CLAUDE.md` Team table has one, else to the product owner. Never ask the wrong role |
| Ids | `BQ-NNN`, `TQ-NNN`, `OD-NNN`; next free number; filename `<ID>.md`; ids never reused or renumbered |
| One question per record | State the question, the options (recommended first), and what work continues meanwhile. Confirmed in OD-022: options are alternative answers to the same question and stay in one record; split into several records (linked by `related`) when answering one part does not settle the others, or the parts have different deciders or different blocked work |
| Record every answer | When a human answers in a session, write it in the record the same session: status, `## Answer` or `## Decision`, date, who. Never leave an answer only in chat |
| History is append-only | Add dated lines under `## History`; do not rewrite earlier lines. Supersede a decision with a new `OD`: set the old record to `closed` and add a line "Superseded by <id>" under `## History`. Statuses are only `open`, `answered`, `decided`, `closed` |
| Link | `related` for records, `chunks` for the business KB; lint fails on unresolved ids and warns when a link is one-way, so add the id to both records |
| Accepted risk | A finding that is known and not fixed before merge (for example a Medium security finding) stays an open `BQ`/`TQ`. Only after the owner accepts the risk does the session write an `OD` with `accepted_risk: true`, `expires: <date>` and `related` pointing at that question; `## Decision` states the risk, the owner, the mitigation and what happens at expiry. The `decider` is the role that owns the risk. An agent never writes it before the owner has accepted. Lint errors on a missing `expires`, an `expires` not after `answered` (or `asked`), a missing `related` BQ/TQ or an empty `## Decision` (only that it is not empty; risk, owner, mitigation and expiry action are required by convention), treats `expires` without `accepted_risk: true` as an error, and prints a `WARN` line once `expires` has passed (re-decide or close it); a `closed` OD never warns |
| Contradiction | If a new answer contradicts a business KB chunk, open a `BQ`/edit task for the chunk via `documentation-curator` |
| Who writes | `requirements-analyst`, `solution-architect` and `documentation-curator` record the BQ/TQ themselves; every other agent returns `questions_to_record` and the calling session (or `documentation-curator`) writes them (owner: `_SHARED-PATTERNS.md`, Never Invent rule 5) |
| Fields | `answered:` (date) and `example: true` are optional; see `questions/README.md` |
| Cite | Code comments, docs and PR text cite the ids a decision rests on |

Lint with `python3 scripts/kb/check_chunks.py`. Reviewers check that every behaviour claim in a change traces to a chunk or a record.
