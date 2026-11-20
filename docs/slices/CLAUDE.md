# docs/slices guide

This file exists because it is loaded when you work under `docs/slices/`; the nearest CLAUDE.md wins and defines how slice planning stays consistent. Process detail: [`IMPLEMENTATION-GUIDE.md`](IMPLEMENTATION-GUIDE.md).

## Files

| File | Role |
|------|------|
| `INDEX.md` | the single status table plus the dependency graph; the first thing read before slice work |
| `IMPLEMENTATION-GUIDE.md` | branching model, rungs, readiness steps S1..S5, scoring, definition of done |
| `templates/slice.md` | one slice spec per `VS-nnn` (copy to `docs/slices/VS-nnn-<name>.md`) |
| `templates/readiness-analysis.md` | the S1..S5 analysis record (appended to the slice spec, never a separate file) |

## Rules

| Rule | Detail |
|------|--------|
| Ids | `VS-nnn`, never reused or renumbered; check open PRs and sibling branches before taking the next id |
| One source of status | status lives only in `INDEX.md`; slice specs link to it, they do not copy it |
| Every code PR updates `INDEX.md` | status, the Rung column (last rung merged, `-` until one merges; the rung a PR builds is in its title) and the PR link (add the link in a follow-up commit once the PR number exists; never predict it) |
| Dependencies | a slice cannot start while a hard dependency is below `Done`; update the Mermaid graph when a dependency changes. The only exception is an `OD` that names the slice (and the rung it covers); cite it in the spec's pickup condition and the INDEX row. Without an `OD` there is no waiver |
| Readiness before build | status moves `Proposed -> Analysed -> Ready -> In progress -> Done` (triggers: guide, section 4b); `Ready` requires a completed readiness analysis with zero open blockers. Confirmed in OD-022: a blocker is an open BQ/TQ with no recorded working assumption that the slice's criteria or design cannot proceed without; every other open record is non-blocking and is listed as such in the INDEX Open blockers table. Readiness may be per rung (`Ready for R1`, same status): a blocker names the rung it blocks in the analysis S5 table |
| Baseline stamp | each readiness analysis records the commit it was written against; the pickup delta check compares it with `HEAD` |
| Grounding | behaviour in a slice spec cites `business-kb` chunk ids or `qa-kb` record ids; a gap becomes a BQ/TQ, not a guess |
| Revision log | append a row per change to the slice; never edit earlier rows |
