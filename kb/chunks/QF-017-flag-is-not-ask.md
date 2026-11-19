---
chunk_id: QF-017
title: Flag is not ask, and how questions are batched
topics: [process, autonomy]
links: [QF-014, QF-015, QF-013]
sources: ["CLAUDE.md", ".claude/agents/_SHARED-PATTERNS.md", "docs/concepts/04-never-invent.md"]
---
In Quorum, "flag it" and "do not guess" mean one thing: record the item (a BQ or TQ record, the pull request description, a deferred list) and carry on with whatever is unblocked. They never mean stop and wait for a human. The default is to act.

| Situation | Action |
|-----------|--------|
| A record settles it | Use it and cite it |
| A record is open | Link to it, proceed on its default, do not ask again |
| Nothing is recorded and the choice is conventional and reversible | Choose the conventional option, state the choice in one line, continue |
| Nothing is recorded and the answer changes product behaviour | Record the question with a decider and continue with unblocked work |
| Blocked on a decision that is the user's | Finish all unblocked work, then ask |

Stopping to ask is reserved for ambiguous product behaviour where the knowledge base and spec conflict or are silent, a scope change, and a destructive or outward-facing action the request did not cover.

Questions are batched. When a stop is justified, the agent finishes everything unblocked, collects every open item and asks once as a numbered list with the recommended option first. It never asks one question per turn, and it does not ask "should I proceed?" after a plan the user already requested.

Questions go to the role that can answer them: technical ones to the technical lead, business ones to the product owner. A question that is not the current user's to answer is recorded with the right decider. A subagent never asks the user; it returns `questions_to_record` to the calling session. A task that produces a change also ends without asking: branch, commit, push, pull request and the AI review loop are standing authorizations, and merging happens only when asked.
