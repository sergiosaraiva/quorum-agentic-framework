---
name: deploying-to-aws
description: "Designs deployment topology and CI/CD for an ASP.NET Core + Angular app on AWS EKS: a GitHub Actions pipeline using OIDC, ECR image publish by digest, a per-environment migrate step, and a GitOps pull request into a separate environment repo that Argo CD reconciles, plus container base-image selection. Use when editing .github/workflows/**, a Dockerfile or compose image, or deciding how a build reaches an environment."
---

# Deploying to AWS

## Quick Reference

- Compute: EKS. Services deploy through a Helm chart with values kept in a separate environment (GitOps) repo that Argo CD reconciles. Chart coverage and non-Helm resources: `implementing-infrastructure-as-code`
- Pipeline: build image -> push to ECR pinned by digest, never `latest` -> open a PR in the environment repo updating the values file -> a human merges -> Argo CD reconciles. No direct `kubectl apply`, no `argocd app sync` from an agent
- AWS access: GitHub Actions assumes an IAM role through OIDC (`aws-actions/configure-aws-credentials`, `id-token: write`). No long-lived AWS keys in secrets. Scope the role trust to the repo, branch/environment and workflow
- Database: RDS or Aurora PostgreSQL in private subnets. The control-plane or main connection string is injected from the secrets manager; provisioning of the database is the adopter's infrastructure-as-code choice (flag it, do not guess a tool)
- Every environment (dev, staging, prod) is its own values file and Argo CD `Application` targeting its own cluster; no branching inside one values file
- Account id, region, role ARN and values path come from a reviewed workflow-level `env:` block or a reusable `workflow_call` workflow's inputs; avoid repo variables for values that must change only through a PR
- Runner label placeholder: `runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}` on every job, so adopters pin their own pool without editing workflows. Reviewers must not flag the expression alone

## Decision Tree

```
New environment?        -> new values file + Argo CD Application in the environment repo
Zero-downtime deploy?   -> default rolling update, readiness probe tuned to warm-up, never a hard cutover
Database migration?     -> separate pipeline step BEFORE the new image/values are promoted; never app startup against a shared database
Frontend static assets? -> S3 + CDN is a common shape; who provisions the CDN and which job publishes and invalidates is the adopter's decision: flag
Secrets at runtime?     -> secrets manager synced by an external-secrets operator into env; never in values files
```

## Pipeline

```yaml
# .github/workflows/deploy.yml (sketch)
name: deploy
on: { push: { branches: [main] } }
permissions: { id-token: write, contents: read }
env:
  AWS_REGION: ${{ vars.AWS_REGION }}          # placeholders: set per adopter
  ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY }}
jobs:
  build:
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    outputs: { digest: "${{ steps.push.outputs.digest }}" }
    steps:
      - uses: actions/checkout@<pinned-sha>
      - uses: aws-actions/configure-aws-credentials@<pinned-sha>
        with: { role-to-assume: "${{ vars.AWS_ROLE_ARN }}", aws-region: "${{ env.AWS_REGION }}" }
      - uses: aws-actions/amazon-ecr-login@<pinned-sha>
      - id: push
        uses: docker/build-push-action@<pinned-sha>
        with:
          context: .
          file: src/Api/Dockerfile
          push: true
          tags: ${{ vars.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
  migrate:                                     # before promotion; loops tenant databases if per-tenant
    needs: build
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    steps:
      - run: ./scripts/migrate.sh              # applies the efbundle; fails the wave on first error
  open-gitops-pr:
    needs: [build, migrate]
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    steps:
      - run: |
          # clone the environment repo with a short-lived app token, set image digest in values, open a PR
          ./scripts/open-gitops-pr.sh "${{ needs.build.outputs.digest }}"
```

Pin third-party actions to a full commit SHA (verify the current release). The PR body names the commit, image digest and migration result; the human merge is the production gate.

## Base image selection

Choose the smallest viable variant from registry-verified tags and measured size, never from memory. For the shipped runtime stage, viable means no shell, no package manager, non-root.

| Role | Image | Notes |
|------|-------|-------|
| .NET runtime (default) | `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled` | Shell-less, non-root; verify the tag and size |
| .NET runtime needing ICU/time zones | `...:10.0-noble-chiseled-extra` | Adds ICU and tzdata, still shell-less |
| Build stage | `mcr.microsoft.com/dotnet/sdk:10.0` | Never shipped |

A deviation needs an adjacent comment with a reason and a source. Image scanning and registry policy are a separate decision; flag if none exists. Publish multi-arch only if the cluster mixes architectures; build on the architecture you run.

## Quality Checklist

- [ ] OIDC role assumption; no static AWS keys; trust policy scoped to repo and ref
- [ ] Image referenced by digest in values; never `latest`
- [ ] Migrate step precedes promotion and is not tied to app startup
- [ ] One values file and Application per environment; human merges the GitOps PR
- [ ] Every job uses the `RUNNER_LABEL` expression; actions pinned by SHA; minimal `permissions`
- [ ] Runtime image shell-less and non-root; no secret baked into an image or workflow

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `docker push :latest` and `kubectl rollout restart` | Digest in a GitOps PR |
| Long-lived `AWS_ACCESS_KEY_ID` secrets | OIDC role |
| Migration in the container entrypoint | Pipeline migrate step |
| One values file with `if env == prod` | A file per environment |
| `ubuntu-latest` hard-coded in every job | `${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}` |
| Guessing how the CDN or database is provisioned | Flag it for the adopter |

## Related Skills

`implementing-infrastructure-as-code`, `writing-postgresql-migrations`, `managing-application-lifecycle`, `creating-configuration-options`, `implementing-observability`.
