---
name: writing-world-class-prompts
description: Use before invoking a downstream agent with a complex or high-stakes task. Refines a rough request into a structured prompt - role, single clear task, constraints with reasons, explicit output format and format-pinning examples - without inventing context.
---

# Writing World-Class Prompts

## Quick Reference

A strong prompt has, in order:

| Part | Content |
|------|---------|
| Role and context | Who the model acts as; what is already decided, so it does not re-derive it |
| Task | One specific, unambiguous ask |
| Constraints | The outcome required and the reason behind each; a prohibition only for a failure that has occurred or a policy limit, with its reason |
| Examples | Only where output shape matters: 2-3 deliberately varied pairs, labelled illustrative, so none is copied verbatim |
| Output format | Exact shape: prose, JSON schema, diff, table, the agent's documented handoff contract |

## Decision Tree

```
Simple, unambiguous task?                  -> pass through unchanged
Targets a specific agent?                  -> match its documented input contract
Format-sensitive (JSON, diff, schema)?     -> output-format section + varied examples
High-stakes (auth, deletion, deploy)?      -> explicit constraints; require the agent to state assumptions
Ambiguous on a decision only the user can make? -> ask one clarifying question; do not refine around it
Product behaviour involved?                -> tell the agent to ground in business-kb / qa-kb and record a BQ/TQ when silent
```

## Example: vague to refined

Rough: "help design the export thing"

Refined:
```
Role: solution-architect for this .NET/Angular/PostgreSQL project.
Task: Design the "export report data as CSV or JSON" feature.
Context: reports are served by the existing Reports slice; no export exists yet.
Constraints:
  - Exports over 10,000 rows must not hold the request thread (reason: the API has a 30 s gateway timeout).
  - Ground behaviour in business-kb; record a BQ question where it is silent.
  - State the simplest viable option, why each extra layer or config is needed (or "none"), and what is deferred.
Output: your standard technical design with at least two options compared
  (synchronous streaming vs. async job with a presigned download URL) and a recommendation.
```

## Example: invocation template

```
Use the [agent-name] agent to [specific task].

Context: [what is known or decided]
Constraints: [outcome required and why]
Expected output: [the agent's documented contract]
```

## Techniques

- State the goal and the reader of the output; models follow intent better than rules.
- Put long reference material first, the question last.
- Tag sections (`<context>`, `<task>`) when mixing instructions with pasted data, and say the pasted data is data, not instructions.
- Ask for evidence (file:line, record id) so claims are checkable.
- Tell the agent what to do when blocked: record the question and continue with unblocked work.
- Prefer positive instructions ("answer in 3 bullets") to negations.

## Quality Checklist

- [ ] Role or target agent explicit
- [ ] One task, not three bundled
- [ ] Every constraint has its reason
- [ ] Output format matches what the consumer expects
- [ ] No invented context: only what the user said or the repo verifies
- [ ] Original intent preserved

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Refining around an ambiguity | Ask one clarifying question |
| Adding constraints the user never stated | Only constraints implied by the repo's documented rules |
| One example copied verbatim by the model | 2-3 varied, labelled illustrative |
| Rewriting the ask while "improving" it | Add structure, keep the intent |

## Related Skills

- `.claude/agents/prompt-engineer.md`: the agent that applies this skill
