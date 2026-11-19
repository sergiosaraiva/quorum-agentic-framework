# Slice Implementation Guide

How a vertical slice goes from idea to merged code. Generic; adapt the numbers to your team.

## 1. What a slice is

A slice is one user-visible capability built end to end: entity, migration, service, endpoint, Angular client, component and tests. It is small enough to merge in a few days and has an id `VS-nnn`. Status lives only in [`INDEX.md`](INDEX.md).

## 2. Rungs

Each slice is built as a ladder of small PRs. A rung is independently mergeable and leaves the product working.

| Rung | Content | Gate |
|------|---------|------|
| R0 | spec and readiness analysis merged (docs only) | slice `Ready` |
| R1 | entity, configuration, migration | migration reviewed |
| R2 | service and endpoints with unit and integration tests | tests green |
| R3 | Angular client and component with loading, error, empty, data states | frontend tests green |
| R4 | end-to-end journey, observability, docs | slice `Done` |

Fewer rungs are fine for a small slice; never skip the order of dependencies.

## 3. Branching model

| Branch | Purpose |
|--------|---------|
| `main` | releases only; protected |
| `integration` (optional) | where slice PRs land; promoted to `main` by a release PR |
| `feature/VS-nnn-<name>` | one rung per branch; the base is the integration branch |
| stacked rung | a rung that depends on an unmerged rung targets the parent branch; after the parent squash-merges, rebase and retarget |

Rules: one rung per PR; the PR title starts with the slice id and rung (`VS-001 R2: orders service and endpoints`); merge only when the AI review loop is clean and threads are resolved.

## 4. Readiness analysis (steps S1..S5)

Done by `requirements-analyst` then `solution-architect`, recorded with [`templates/readiness-analysis.md`](templates/readiness-analysis.md).

| Step | Question | Output |
|------|----------|--------|
| S1 Ground | what does the business KB say; what do prior decisions say | cited chunk and record ids, gaps listed |
| S2 Scope | what is in, what is out, what is deferred | acceptance criteria, one per behaviour |
| S2b UX (UI slices) | does a design exist | flows and states, or a `ux-usability-specialist` define pass |
| S3 Design | simplest design, data model delta, API contract, risks | rungs and files per rung |
| S4 Dependencies | hard and soft dependencies, conflicts with open PRs | `Depends on` column, graph updated |
| S5 Decide | open BQ/TQ blockers | each recorded with a decider; slice is `Ready` only at zero blockers |

## 5. Priority scoring

```
priority = (2*Value + 2*Urgency + Unblocks) / Effort
```

All inputs are integers 1-5 (Unblocks 0-5). Value: business benefit. Urgency: cost of delay. Unblocks: how many other slices wait on it. Effort: relative size. The slice with the highest priority among `Ready` slices whose hard dependencies are `Done` is picked first; ties go to the one that unblocks more.

## 6. Pickup delta check

Before starting a slice (or a rung) that was analysed earlier, compare the analysis baseline commit with `HEAD`:

1. `git log <baseline>..HEAD --oneline -- <paths the slice touches>`.
2. Check open and merged PRs for the same slice id or files (sibling sessions may have built it).
3. Re-read the KB chunks and records it cites; a changed chunk reopens the affected criteria.
4. Record the result in the readiness analysis revision log: `unchanged` or a list of deltas. A material delta moves the slice back to `Analysed`.

## 7. Definition of done

| Item | Check |
|------|-------|
| Behaviour | every acceptance criterion has a test that fails without the change |
| Grounding | behaviour cites KB chunk or record ids; no open blockers |
| Review | quality-guardian and regression-detective clean; findings dispositioned |
| Tests | unit and integration green; Angular tests green for UI |
| Migration | reviewed, additive or with an approved rollout |
| Docs | docs and CLAUDE.md updated; `INDEX.md` row updated |
| Auth | every endpoint has an explicit auth decision |
| Observability | structured logs and a metric or alarm where the slice adds a failure mode |
| CI | build, tests, format and AI review green |

## 8. PR checklist

- [ ] PR title starts with `VS-nnn Rn:`
- [ ] Alignment check filled in (KB chunk ids, record ids, slice id)
- [ ] `INDEX.md` status and rung updated
- [ ] Commit body has the `AI:` metadata line
- [ ] Local AI review run (`scripts/ai_review_local.py`), findings addressed
- [ ] No secrets, no hard-coded environment values
- [ ] Migration reviewed (if any)
- [ ] Tests added for every behaviour change
