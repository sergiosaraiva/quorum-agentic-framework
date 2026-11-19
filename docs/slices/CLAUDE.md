# docs/slices guide

This file exists because it is loaded when you work under `docs/slices/`; the nearest CLAUDE.md wins and defines how slice planning stays consistent. Process detail: [`IMPLEMENTATION-GUIDE.md`](IMPLEMENTATION-GUIDE.md).

## Files

| File | Role |
|------|------|
| `INDEX.md` | the single status table plus the dependency graph; the first thing read before slice work |
| `IMPLEMENTATION-GUIDE.md` | branching model, rungs, readiness steps S1..S5, scoring, definition of done |
| `templates/slice.md` | one slice spec per `VS-nnn` (copy to `docs/slices/VS-nnn-<name>.md`) |
| `templates/readiness-analysis.md` | the S1..S5 analysis record (append to the slice spec) |

## Rules

| Rule | Detail |
|------|--------|
| Ids | `VS-nnn`, never reused or renumbered; check open PRs and sibling branches before taking the next id |
| One source of status | status lives only in `INDEX.md`; slice specs link to it, they do not copy it |
| Every code PR updates `INDEX.md` | status, rung reached, PR link (add the link in a follow-up commit once the PR number exists; never predict it) |
| Dependencies | a slice cannot start while a hard dependency is below `Done`; update the Mermaid graph when a dependency changes |
| Readiness before build | status moves `Proposed -> Analysed -> Ready -> In progress -> Done`; `Ready` requires a completed readiness analysis with zero open BQ/TQ blockers |
| Baseline stamp | each readiness analysis records the commit it was written against; the pickup delta check compares it with `HEAD` |
| Grounding | behaviour in a slice spec cites `business-kb` chunk ids or `qa-kb` record ids; a gap becomes a BQ/TQ, not a guess |
| Revision log | append a row per change to the slice; never edit earlier rows |
