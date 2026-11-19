---
name: implementing-infrastructure-as-code
description: Authors Helm values files and Argo CD Application manifests for services in a separate GitOps environment repo (services, workers, queues, buckets, roles, secrets, certificates, jobs), and owns the coverage table of which AWS resources the chart provisions versus which need the adopter's own tool. Use when adding or changing a deployed service, worker, queue, bucket, role, secret, certificate, scheduled job, or ingress, or when deciding how an AWS resource is provisioned.
---

# Implementing Infrastructure as Code

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`. Every AWS resource is defined as code; console clicks are never acceptable.

## Quick Reference

- Application repo holds code and a Dockerfile; deployment configuration lives in a separate environment repo reconciled by Argo CD. Each app and cluster needs two artifacts there: a Helm values file and an Argo CD `Application` (multi-source: chart from an OCI/Helm registry, values from Git)
- Cluster-level infrastructure (clusters, networks, node groups) belongs to the platform team's tooling, not this repo
- This skill is the single owner of chart coverage facts; other skills point here
- Verify every values key against the chart's `values.schema.json` and `values.yaml`, never its README (READMEs drift). Pin the chart version and re-check on upgrade
- `helm lint` and `helm template` against the pinned chart are the local check. The chart registry may need a login; do it with a short-lived credential. A human approves and merges the GitOps PR; agents never run `argocd app sync` or `kubectl apply`

## Coverage table (fill in for your chart; verify, do not assume)

| Resource | Typical path | Status to confirm |
|----------|--------------|-------------------|
| Deployment, Service, Ingress, HPA, probes, env | chart values | first-class |
| Object store, queue, topic, event bus, IAM role, DNS record | chart values backed by AWS Controllers for Kubernetes (ACK), if installed | confirm each key exists and is first-class |
| Secret consumption | external-secrets operator reading an existing secret | consumption only; who creates the secret is open |
| TLS certificate | cert-manager `Certificate` in-cluster; an ACM certificate (CloudFront needs it in us-east-1) is separate | confirm which |
| Log groups, alarms | usually not covered by app charts | flag |
| RDS/Aurora, ElastiCache, CloudFront, KMS keys, anything with no controller | not in the chart | adopter's provisioning tool (Terraform, CDK, Crossplane, other): decide with the platform team, record it as a TQ question, never guess |

Rule: an AWS resource type with an unqualified first-class chart key goes in Helm values. Any other type has an unresolved provisioning path: flag it, resolve the tool with the platform owner before touching a shared environment. Pod identity or IRSA wiring and the role trust policy source should be verified, as chart support differs.

## Decision Tree

```
New service or worker?         -> entry in the values `services` map (verify key name in the schema)
Needs a queue/bucket/role?     -> chart key if first-class; else the adopter's tool, flagged
Needs a secret?                -> secrets manager entry (provisioned as code) + external-secrets reference
Recurring or one-shot work?    -> scheduled job / job hook per the chart; a job hook is one-shot, not a schedule
Public exposure?               -> ingress with explicit auth at the app; internal services stay ClusterIP
Per-environment difference?    -> separate values file per environment, same chart version pinned deliberately
```

## Example (illustrative; verify keys against your chart)

```yaml
# environments/staging/api/values.yaml
services:
  api:
    image:
      repository: ${ECR_REGISTRY}/app-api
      digest: sha256:<digest>          # set by the deploy pipeline PR
    replicas: 2
    env:
      ASPNETCORE_ENVIRONMENT: Staging
      OTEL_SERVICE_NAME: app-api
    externalSecrets:
      db:
        secretName: app/staging/database      # created by your provisioning tool
        envFrom: true
    probes:
      liveness:  { httpGet: { path: /health/live,  port: 8080 } }
      readiness: { httpGet: { path: /health/ready, port: 8080 } }
    resources:
      requests: { cpu: 250m, memory: 512Mi }
      limits:   { memory: 512Mi }
```

```yaml
# argocd/staging-api.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata: { name: api-staging, namespace: argocd }
spec:
  project: default
  sources:
    - repoURL: ${CHART_REGISTRY}
      chart: app-chart
      targetRevision: <pinned-version>
      helm: { valueFiles: [$values/environments/staging/api/values.yaml] }
    - repoURL: ${ENV_REPO_URL}
      targetRevision: main
      ref: values
  destination: { server: https://kubernetes.default.svc, namespace: app }
  syncPolicy: { automated: { prune: true, selfHeal: true } }
```

## Design Principles Applied

Smallest viable infrastructure: reuse chart features before a new AWS resource; right-size requests, no speculative replicas or autoscaling without a measured need; least-privilege IAM per workload; a cost note in every proposal (what it adds monthly and what was deferred).

## Quality Checklist

- [ ] Keys verified against the chart schema at the pinned version; `helm lint` and `helm template` clean
- [ ] One values file and one Application per environment
- [ ] Every new AWS resource has a code definition path; uncovered types flagged with a TQ question, not guessed
- [ ] No secret value in any values file; IAM least privilege, no wildcard actions without a comment
- [ ] Image by digest; human approval of the GitOps PR

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Following the chart README for key names | Read the schema |
| Console-created queue or database "just for now" | Code, via the covered path or the adopter's tool |
| Assuming the external-secrets block creates the secret | It consumes an existing one |
| Same values file with environment branches | A file per environment |
| Wildcard IAM policy | Scoped actions and resources |
| Agent merging or syncing the GitOps PR | Human merge |

## Related Skills

`deploying-to-aws`, `managing-application-lifecycle`, `implementing-observability`, `creating-configuration-options`.
