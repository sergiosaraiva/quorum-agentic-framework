# docs guide

This file exists because it is loaded when you work under `docs/`; the nearest CLAUDE.md wins and sets the prose contract for every document here.

## Folders

| Folder | Holds | Style |
|--------|-------|-------|
| `slices/` | slice index, implementation guide, templates | see `slices/CLAUDE.md` |
| `concepts/` | numbered explanations of how the framework works | readable prose, one concept per file |
| `reference/` | cost, model selection, lookups | tables |
| `presentation/` | slide-style overview | short sections |

## Prose contract

| Rule | Detail |
|------|--------|
| Grounded | every claim about code points to a path (and a symbol, not a line number); every claim about behaviour cites a KB chunk id or record id |
| No line-number citations | lines drift; cite `path` plus symbol or heading |
| Plain | short sentences, active voice, one idea per paragraph, define a term on first use |
| No filler, no emojis | no "it is worth noting", no marketing words |
| Tables over prose | for lists of facts, options, rules |
| Examples marked | any invented example says "example" next to it |
| Generated files | never hand-edit; regenerate with the owning script |
| Dates | absolute (`2026-03-14`), never "last week" |

## Workflow

Docs are written by `documentation-curator` and verified by `documentation-reviewer` (no Write or Edit tools; grounding check). A doc without a grounded source for a claim gets the claim removed or a TQ recorded, not a guess.
