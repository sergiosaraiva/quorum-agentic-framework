---
name: implementing-infrastructure-as-code
description: Declares every infrastructure resource (services, workers, databases, queues, buckets, caches, access roles, secrets, certificates, scheduled jobs, ingress) as reviewed code in the IaC tool the adopter chose and recorded, never created by hand in a console. Use when adding or changing a deployed service, worker or resource, when deciding how a resource is provisioned, or when designing exposure.
---

# Implementing Infrastructure as Code

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`. Every infrastructure resource is defined as code and reviewed; creating one by hand in a console is never acceptable, not even "just for now".

## Quick Reference

- The IaC tool and the deploy target (`{{DEPLOY_TARGET}}`) are the adopter's choice, recorded in a TQ or OD record. Search `qa-kb` first. Not recorded: return a TQ with a decider and a recommended option, then produce a tool-neutral design (resource, properties, access policy, dependencies). Never guess a tool
- Shared platform pieces (networks, clusters, accounts) may belong to a platform team's repo; if so, describe the change as a patch to that repo and mark it `unaudited` until the file is supplied
- Verify every configuration key against the tool's or module's schema at the pinned version, never its README or memory. Pin tool, provider and module versions; re-check on upgrade
- Local check: the tool's own validate, plan or lint command, read-only. Agents never apply to a shared environment; a human approves and applies
- Same definition, different inputs per environment: one input/configuration file per environment, no environment branching inside one file

## Decision Tree

```
New service or worker?      -> a declared workload in the chosen tool, image by digest
Needs a database/queue/bucket/cache? -> declared resource; managed service over self-hosted; cost noted
Needs a secret?             -> the secret's container declared as code; its value set out of band in the platform's secret store, surfaced as an env var
Recurring or one-shot work? -> a scheduled or one-shot task, declared; a one-shot task is not a schedule
Public exposure?            -> explicit auth at the app plus TLS; internal services stay private
No recorded tool?           -> TQ, tool-neutral design, continue
```

## Tool-neutral resource record

When no tool is recorded, describe each resource like this so any IaC tool can implement it:

| Field | Example |
|-------|---------|
| Resource | PostgreSQL database for `staging` |
| Properties | Version 16+, private network only, automated backups 7 days, encryption at rest |
| Access | API workload identity: connect only; migration task: schema change |
| Config surfaced | `ConnectionStrings__Default` env var from the platform's secret store |
| Depends on | Network, secret store entry |
| Cost note | Smallest size meeting the measured load; what was deferred |

## Design Principles Applied

Smallest viable infrastructure: reuse an existing resource before adding one; right-size from measurement, no speculative replicas or autoscaling; least-privilege access per workload; a cost note in every proposal (what it adds monthly and what was deferred).

## Quality Checklist

- [ ] Every new resource has a code definition (or a tool-neutral record plus a TQ when the tool is unrecorded)
- [ ] Keys verified against the schema at the pinned version; validate or lint clean
- [ ] One input file per environment
- [ ] No secret value in any file; least-privilege access, no wildcard without a comment
- [ ] Image by digest; a human approves and applies

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Following a README or memory for key names | Read the schema |
| Console-created resource "just for now" | Code, reviewed |
| Picking an IaC tool because it is popular | Use the recorded choice, or raise a TQ |
| Same file with environment branches | A file per environment |
| Wildcard permission | Scoped actions and resources |
| Agent applying to a shared environment | Human approval and apply |

## Related Skills

`deploying-the-application`, `managing-application-lifecycle`, `implementing-observability`, `creating-configuration-options`.
