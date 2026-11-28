# 05. CLAUDE.md files

`CLAUDE.md` is the one file Claude Code loads into every session automatically. It is the project's standing instructions: what the product is, the rules that never bend, and where to find everything else. Used well it keeps agents consistent without repeating the same paragraph in every prompt. Used badly it becomes a dumping ground that every session pays for.

## How Claude Code reads them

Claude Code loads the root `CLAUDE.md` at session start. When it works on files in a subdirectory it also loads that directory's `CLAUDE.md` (and those of its parents), so the guidance nearest the file being edited is in context. The convention in this template: the nearest `CLAUDE.md` wins on its own layer, adds to the root and never contradicts it. A sub-file is a specialisation, not a fork.

## Root versus sub-files

| Belongs in the root `CLAUDE.md` | Belongs in a sub-`CLAUDE.md` |
|--------------------------------|------------------------------|
| What the product is and the current phase | Conventions that only matter in one layer |
| Working style: when to act, when to ask | Endpoint shape, options, error format (`src/Api`) |
| The grounding rule ([04](04-never-invent.md)) | Entity naming, migration workflow (`src/Infrastructure`) |
| Immutable Rules and Design Principles | Angular component and test conventions (`frontend`) |
| Team roles and who answers what | Prose rules for docs (`docs`) |
| Tech stack, one line per layer | Slice upkeep rules (`docs/slices`) |
| Agent workflow summary and delegation table | Chunk and record authoring rules (`kb`, `questions`) |
| The map of sub-files | Test layout and tooling (`tests`) |

If a rule applies to every layer it is root; if it matters only when touching a folder it is a sub-file; if it is a long procedure used in some tasks it is neither, it is a skill ([09](09-agents-and-skills.md)).

## The map table

The root file ends with a map of every sub-file, with the layer each file covers. It serves two readers. Agents learn which file to read before working on a layer; maintainers learn when a new sub-file is justified. Only add a sub-file when a layer has conventions that are non-obvious and would otherwise be rediscovered each session.

| File | Layer |
|------|-------|
| `src/Api/CLAUDE.md` | endpoints, options, auth, error shape |
| `src/Infrastructure/CLAUDE.md` | EF Core, naming, migration workflow |
| `frontend/CLAUDE.md` | Angular conventions, tests |
| `docs/CLAUDE.md` | prose rules for docs |
| `docs/slices/CLAUDE.md` | slice planning and status upkeep |
| `tests/CLAUDE.md` | test conventions |
| `kb/CLAUDE.md`, `questions/CLAUDE.md` | chunk and record authoring |

## What a good root file contains

The template root has these sections; keep them, replace the placeholders.

| Section | Purpose |
|---------|---------|
| Objective | One paragraph: what, for whom, which phase, what gate decides the next phase |
| Working Style | The autonomy rules: act by default, "flag" is not "ask", batch questions, standing authorizations (branch, commit, push, PR, AI review loop: local rounds, plus GitHub rounds when `AI_REVIEW_ENABLED` is `true` and the `ai-review` environment holds the key) |
| Never Invent | The grounding rule |
| Team and Communication | Roles and who decides what; how to address technical versus business readers |
| Tech Stack | A table, one line per layer; sub-guides are listed once, in the Multi-CLAUDE.md Map |
| Architecture Style | Vertical slices and a one-line layout |
| Design Principles | Simplest design, reuse first, no hard-coded values, built-ins first |
| Immutable Rules | Numbered, non-negotiable: secrets, migrations reviewed, infrastructure as code, nullable enabled, standalone Angular, explicit auth on every endpoint, pinned CI runner |
| Multi-CLAUDE.md Map | The table above |
| Agent Workflow and Delegation | The pipeline and who edits what |
| Verification Commands | Build, test, format; how to prove a change is sound |
| Commit Metadata | Optional: a one-line AI-usage footer on commits |

Design Principles and Immutable Rules differ on purpose. Principles are judgement guides that a justified exception can bend. Immutable Rules cannot be waived by a principle, only changed by the team explicitly, and the file says so.

## Style and size budgets

`CLAUDE.md` files are read by models on every session, so every byte costs context and attention on every task. Write them for a model:

| Practice | Why |
|----------|-----|
| Tables over prose, imperative sentences | Dense, scannable, unambiguous |
| State the rule and its reason in one line | A reason lets an agent handle the case you did not list |
| Point instead of copy | One owner per rule; others link to it |
| No history, no changelog, no narrative | History belongs in git and records |
| No secrets, no personal data | The file is committed |

Suggested budgets for the files you write by hand: root under about 12 KB, a sub-file under about 6 to 10 KB. `python3 scripts/framework_lint.py` checks the agent and skill limits (agent at most 16 KB, skill at most 7 KB; it warns above). When a file nears its budget, move a procedure into a skill's `reference/` file or a doc and leave a one-line pointer. Growth by accretion is the failure mode: each addition is reasonable, the sum is not.

## Keeping them current

| Trigger | Action |
|---------|--------|
| A fact changes (a path, a version, a count) | documentation-curator updates the one owner file |
| A review finds an agent followed a wrong or stale instruction | Fix the instruction, not only the output |
| A rule is stated in two files | Keep one, replace the other with a pointer |
| A layer grows non-obvious conventions | Add a sub-file and a row in the map |
| A section nears its budget | Move detail into a skill reference or doc |

Edits to governed sections (Immutable Rules, Design Principles, Agent Workflow, Working Style, Team) and to agent and skill files are framework changes. They are delegated to documentation-curator and then reviewed by quality-guardian and regression-detective in parallel and by documentation-reviewer, because a wrong sentence here steers every future session. `python3 scripts/framework_lint.py` (frontmatter, names, index, sizes) runs in CI and catches drift in agents and skills; a scheduled review of the prose is yours to add.

## Example: where does this rule go?

"All list endpoints return `{ items, total }` and cap page size at a configured maximum." It is specific to the API layer, so it goes in `src/Api/CLAUDE.md`. The page-size maximum is a value, so the rule also says it lives in typed options, which restates a root Design Principle by pointer, not by copy. "No endpoint without an auth decision" applies everywhere, so it is an Immutable Rule in the root. "How to write a Testcontainers fixture" is a procedure used only when writing integration tests, so it is a skill, not a `CLAUDE.md` section.
