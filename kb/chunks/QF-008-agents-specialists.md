---
chunk_id: QF-008
title: Specialist agents in Quorum
topics: [agents, security, infrastructure]
links: [QF-029, QF-009]
sources: [".claude/agents/security-engineer.md", ".claude/agents/infrastructure-engineer.md", ".claude/agents/prompt-engineer.md", ".claude/settings.json", ".claude/agents/_SHARED-PATTERNS.md"]
---
Three Quorum agents sit outside the linear pipeline.

security-engineer (Opus, high effort, maximum 40 turns) is a principal security engineer for web software. It reviews authentication flows, data access, API security, infrastructure and compliance, and it runs proactively when a request involves authentication, authorization, encryption, secrets, rate limiting, multi-tenancy or personal data. It is a reviewer without Write or Edit tools: it reports evidence-based findings, returns open policy questions as `questions_to_record`, and never edits. Its Critical and High findings block.

infrastructure-engineer (Opus, high effort, maximum 20 turns) designs and reviews infrastructure as code for whatever platform the adopter chose, plans CI/CD and deployment, and evaluates cost and scaling trade-offs. If no platform is recorded it records a technical question instead of guessing. It runs proactively on requests about deploy, infrastructure resources, queues, storage, secrets, certificates or infrastructure cost. It is a writer, so its output is reviewed by security-engineer and quality-guardian, never by itself.

prompt-engineer (Haiku, no effort level set) refines a prompt before another agent is invoked, applying prompt-engineering practice: context, one clear task, reasons behind constraints and an explicit output format. It has only the tools Read, Grep, Glob and Skill, returns the refined prompt in a code block with its open ambiguities, and never executes the prompt. It runs on request, ahead of any agent, typically before a complex multi-agent hand-off.

The framework permission file `.claude/settings.json` allows the session to call all twelve agents by name. The two proactive specialists run whenever a change touches authentication, data access, secrets, infrastructure or deployment configuration.
