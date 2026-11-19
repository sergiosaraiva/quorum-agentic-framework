---
chunk_id: QF-019
title: Agents, skills, hooks, MCP servers and settings compared
topics: [claude-code, configuration]
links: [QF-018, QF-007, QF-012, QF-034, QF-033]
sources: ["docs/concepts/09-agents-and-skills.md", ".mcp.json", ".claude/skills/SKILL-INDEX.md"]
---
Claude Code offers several ways to shape model behaviour, and Quorum uses each for a different need.

| Block | What it is | Loaded | Lives in |
|-------|-----------|--------|----------|
| `CLAUDE.md` | Standing project instructions | Every session; sub-files when working in their folder | `CLAUDE.md`, `<dir>/CLAUDE.md` |
| Agent | A specialised worker with its own context window, tool allow-list and model | When the session delegates to it, by call or by matching its `description` | `.claude/agents/<name>.md` |
| Skill | A packaged procedure with instructions and optional reference files | Name and description always visible; body loaded when the task matches | `.claude/skills/<name>/SKILL.md` |
| Hook | A command run on an event | By the harness or git, not the model, so the model cannot forget it | `.claude/settings.json`, `.claude/hooks/` |
| MCP server | An external tool provider the model can call | Registered once | `.mcp.json` |

Rules of thumb: facts every task needs go in `CLAUDE.md`; a role with its own job, tools and model is an agent; a procedure only some tasks need is a skill; something that must happen every time is a hook; access to a system outside the repository is an MCP server.

In Quorum the agent allow-list is the technical form of "reviewers have no Write or Edit tools" (ux-usability-specialist has scratch Write only). A reviewer's Bash is limited to reading, building and testing by its agent body; the tool list cannot enforce that. No agent lists `Agent` or `AskUserQuestion`.

The skill index `.claude/skills/SKILL-INDEX.md` lists every skill with its users. The settings file and the pre-commit hook are described in QF-034.
