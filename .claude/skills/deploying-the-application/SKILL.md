---
name: deploying-the-application
description: "Designs how an ASP.NET Core + Angular build reaches an environment on the adopter's chosen platform ({{DEPLOY_TARGET}}): a GitHub Actions pipeline that builds a container image, publishes it by immutable digest, runs migrations as a deploy step, deploys with short-lived credentials, and supports rollback, plus container base-image selection. Use when editing .github/workflows/**, a Dockerfile or compose image, or deciding how a build reaches an environment."
---

# Deploying the Application

## Quick Reference

- Target: `{{DEPLOY_TARGET}}`, the adopter's choice recorded in a TQ or OD record. Not recorded: flag a TQ, design the pipeline stages tool-neutrally, never guess a platform
- Pipeline: build image -> push to the adopter's container registry tagged and referenced by digest, never `latest` -> migrate -> deploy that digest -> verify health. A human approval gates production
- CI credentials: short-lived or federated credentials (for example, a GitHub Actions identity-token exchange) where the platform supports them, scoped to repo, branch or environment and workflow. Never long-lived keys committed or stored in the repo
- Database: PostgreSQL per environment, not publicly reachable. The connection string comes from the platform's secret store as an environment variable; how the database is provisioned is the adopter's IaC choice (`implementing-infrastructure-as-code`)
- Every environment (dev, staging, prod) has its own configuration set; no branching on environment name inside one file
- Registry, target names and regions come from a reviewed workflow-level `env:` block or a reusable `workflow_call` workflow's inputs; avoid repo variables for values that must change only through a PR
- Runner label placeholder: `runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}` on every job, so adopters pin their own pool without editing workflows. Reviewers must not flag the expression alone

## Decision Tree

```
New environment?        -> new configuration set + deploy job/environment, defined as code
Zero-downtime deploy?   -> rolling or blue-green per the platform, readiness check tuned to warm-up, never a hard cutover
Database migration?     -> separate pipeline step BEFORE the new image serves traffic; never app startup against a shared database
Frontend static assets? -> static hosting behind a CDN is a common shape; which host and which job publishes and invalidates is the adopter's decision: flag
Secrets at runtime?     -> platform's secret store surfaced as env vars; never in workflow files or images
Bad release?            -> redeploy the previous digest; migrations stay additive so the old image still runs
```

## Pipeline

```yaml
# .github/workflows/deploy.yml (sketch; deploy step is platform-specific)
name: deploy
on: { push: { branches: [main] } }
permissions: { id-token: write, contents: read, packages: write }
env:
  REGISTRY: ${{ vars.REGISTRY }}               # placeholders: set per adopter
  IMAGE_NAME: ${{ vars.IMAGE_NAME }}
jobs:
  build:
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    outputs: { digest: "${{ steps.push.outputs.digest }}" }
    steps:
      - uses: actions/checkout@<pinned-sha>
      - uses: docker/login-action@<pinned-sha>  # short-lived token, never a stored long-lived key
        with: { registry: "${{ env.REGISTRY }}", username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - id: push
        uses: docker/build-push-action@<pinned-sha>
        with:
          context: .
          file: src/Api/Dockerfile
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
  migrate:                                     # before the new version serves traffic
    needs: build
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    environment: staging
    steps:
      - run: ./scripts/migrate.sh              # applies the efbundle; fails the run on first error
  deploy:
    needs: [build, migrate]
    runs-on: ${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}
    environment: staging                       # production uses a protected environment with required reviewers
    steps:
      - run: ./scripts/deploy.sh "${{ needs.build.outputs.digest }}"   # {{DEPLOY_TARGET}}-specific
```

Pin third-party actions to a full commit SHA (verify the current release). The run summary names the commit, image digest and migration result; the protected-environment approval is the production gate.

## Base image selection

Choose the smallest viable variant from registry-verified tags and measured size, never from memory. For the shipped runtime stage, viable means no shell, no package manager, non-root.

| Role | Image | Notes |
|------|-------|-------|
| .NET runtime (default) | `mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled` | Shell-less, non-root; verify the tag and size |
| .NET runtime needing ICU/time zones | `...:10.0-noble-chiseled-extra` | Adds ICU and tzdata, still shell-less |
| Build stage | `mcr.microsoft.com/dotnet/sdk:10.0` | Never shipped |

A deviation needs an adjacent comment with a reason and a source. Image scanning and registry policy are a separate decision; flag if none exists. Publish multi-arch only if the target mixes architectures; build on the architecture you run.

## Quality Checklist

- [ ] Short-lived or federated CI credentials; no long-lived keys in the repo; scope limited to repo and ref
- [ ] Image deployed by digest; never `latest`
- [ ] Migrate step precedes the deploy and is not tied to app startup
- [ ] One configuration set per environment; production gated by human approval
- [ ] Rollback path: previous digest redeployable
- [ ] Every job uses the `RUNNER_LABEL` expression; actions pinned by SHA; minimal `permissions`
- [ ] Runtime image shell-less and non-root; no secret baked into an image or workflow

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Push `:latest` and restart | Deploy a specific digest |
| Long-lived deploy keys stored as secrets | Short-lived or federated credentials |
| Migration in the container entrypoint | Pipeline migrate step |
| One config file with `if env == prod` | A configuration set per environment |
| `ubuntu-latest` hard-coded in every job | `${{ vars.RUNNER_LABEL || 'ubuntu-latest' }}` |
| Guessing the platform or how the database is provisioned | Flag a TQ for the adopter |

## Related Skills

`implementing-infrastructure-as-code`, `writing-postgresql-migrations`, `managing-application-lifecycle`, `creating-configuration-options`, `implementing-observability`.
