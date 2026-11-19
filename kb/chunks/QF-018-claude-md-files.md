---
chunk_id: QF-018
title: CLAUDE.md files and the nearest-wins rule
topics: [claude-md, configuration]
links: [QF-019, QF-007, QF-032]
sources: ["docs/concepts/05-claude-md-files.md", "CLAUDE.md", "scripts/framework_lint.py"]
---
`CLAUDE.md` is the file Claude Code loads into every session automatically, so it carries the project's standing instructions. Quorum uses a root file plus small sub-files next to the code they govern.

Claude Code loads the root file at session start. When it works on files in a subdirectory it also loads that directory's `CLAUDE.md`, so guidance nearest the edited file is in context. The convention is that the nearest `CLAUDE.md` wins on its own layer, adds to the root and never contradicts it. A sub-file is a specialisation, not a fork.

| Belongs in the root | Belongs in a sub-file |
|---------------------|-----------------------|
| What the product is and the current phase | Conventions that matter in one layer only |
| Working style, the grounding rule, Immutable Rules | Endpoint shape and error format in `src/Api/CLAUDE.md` |
| Roles and who answers what | EF Core naming and migration workflow in `src/Infrastructure/CLAUDE.md` |
| Tech stack, one line per layer | Angular conventions in `frontend/CLAUDE.md` |
| The map of sub-files and the delegation table | Slice upkeep in `docs/slices/CLAUDE.md`, authoring rules in `kb/CLAUDE.md` |

A long procedure used only in some tasks is neither: it is a skill. Design Principles are judgement guides a justified exception can bend, whereas Immutable Rules can be changed only when the team explicitly changes the rule.

Because every byte is paid on every session, keep files small. Suggested budgets: root under about 12 KB and a sub-file under about 6 to 10 KB, which Claude Code does not enforce. `scripts/framework_lint.py` warns when an agent file exceeds 16 KB or a skill file exceeds 7 KB. Write tables and imperative sentences, point instead of copy, and keep one owner per rule. Edits to governed sections and to agent or skill files are framework changes and go through documentation-curator and the review pair.
