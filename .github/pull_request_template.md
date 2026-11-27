## Summary

What changed and why, in two or three sentences.

## Alignment check

| Item | Value |
|------|-------|
| Slice id and rung | `VS-nnn Rn` or "none" |
| Business KB chunk ids cited | `BC-nnn, ...` or "KB silent: BQ-nnn recorded" |
| Q&A records cited | `BQ-nnn, TQ-nnn, OD-nnn` or "none" |
| Open questions recorded | BQ/TQ ids with decider, or "none" |
| Behaviour in KB, spec and code agree | yes / no (explain) |

## Review loop

| Item | Status |
|------|--------|
| Local AI review (`scripts/ai_review_local.py`), required | round `n` of `--max-rounds` (default 5), findings dispositioned |
| GitHub AI review round (optional; only if `ANTHROPIC_API_KEY` is set, else skipped and not a review) | `n` of `MAX_ROUNDS` (default 5); label `needs-human-review` if capped |
| Review findings | fixed / rejected with reason / deferred (record id) |

## Checklist

- [ ] `docs/slices/INDEX.md` updated (status, rung, PR link)
- [ ] Tests added or changed for every behaviour change
- [ ] Migration reviewed (if any)
- [ ] No secrets, no hard-coded environment values
- [ ] Every new endpoint has an explicit auth decision
- [ ] Docs and CLAUDE.md files updated where conventions changed
- [ ] Commit body has the `AI:<TOOL> W<n> N<n> L<n>` line
