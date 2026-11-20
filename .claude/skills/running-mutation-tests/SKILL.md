---
name: running-mutation-tests
description: Use when proving that tests on hot-path business logic (pricing, calculations, permission checks) actually catch bugs. Runs Stryker.NET scoped to those files with a kill-rate threshold and a survivor triage loop.
---

# Running Mutation Tests

## Quick Reference

| Topic | Rule |
|-------|------|
| Idea | Coverage shows a line ran; mutation testing breaks the line and checks a test fails |
| Tool | `dotnet-stryker` as a pinned local tool. The manifest `.config/dotnet-tools.json` and `stryker-config.json` are not shipped: the adopter creates them (`dotnet new tool-manifest`, `dotnet tool install dotnet-stryker`) when the first hot path is gated; installing a tool needs human approval |
| Scope | Hot-path files only (money math, rules engines, authorization checks, anything the team flags). Not CRUD glue, not the whole solution |
| Threshold | Set `thresholds.break` per maturity (start near 70, ratchet up). Below `break` the run fails |
| Survivors | A survivor is a test gap until reasoned otherwise. Add one targeted test for the missed behaviour; do not expand the suite for its own sake |
| Equivalent mutants | Dismiss only with written reasoning that no test can observe the difference (rare) |
| Cadence | Separate, explicit job (nightly or on changes to flagged files), not the per-commit suite: it is slow |

## Decision Tree

```
Change touches a flagged hot-path file?  -> run the gate; block merge below break threshold
Ordinary CRUD or glue code?              -> skip; unit and integration tests are the bar
Mutant survived?                         -> missing assertion? add a test. Truly equivalent? document why
Run too slow?                            -> narrow `mutate`, use --since:<branch> for changed files only
```

## Example: config

```json
{
  "stryker-config": {
    "project": "src/Api/Api.csproj",
    "test-projects": [
      "tests/Api.UnitTests/Api.UnitTests.csproj",
      "tests/Api.IntegrationTests/Api.IntegrationTests.csproj"
    ],
    "mutate": [
      "src/Api/Features/Billing/Pricing/**/*.cs",
      "src/Api/Common/PermissionEvaluator.cs"
    ],
    "thresholds": { "high": 90, "low": 70, "break": 70 },
    "reporters": ["html", "progress", "json"]
  }
}
```

Match project paths to your solution (the `mutate` paths above are an example, not files in the template). Verify option names against the installed Stryker version.

Which test projects to list: behaviour that a unit test can observe alone (calculations, pure filters) needs only `Api.UnitTests`. Behaviour that shows only through the database or the HTTP pipeline (query ordering and tiebreaks, SQL translation, status codes) is killed only by `Api.IntegrationTests`; a config that omits that project reports those mutants as survivors. Listing it makes each run start containers and need Docker, so keep `mutate` narrow and run it in the separate job, not the per-commit suite.

## Example: run and triage

```bash
dotnet tool restore
dotnet stryker --config-file stryker-config.json
dotnet stryker --config-file stryker-config.json --since:origin/main   # changed files only
```

```
Survivor: PricingCalculator.cs  discountRate >= threshold  mutated to  discountRate > threshold
Cause:    tests only used values clearly above and clearly below the threshold
Fix:      add [InlineData] at exactly the threshold asserting the discount applies; rerun; mutant killed
```

Typical survivors: boundary operators, removed statements, flipped conditions, swapped arithmetic, string literal changes. Each points to a missing assertion or an untested branch.

## CI

Run as its own workflow or scheduled job, upload the HTML/JSON report as an artifact, fail on `break`. Do not put it in the fast PR gate unless scoped by `--since`.

## Quality Checklist

- [ ] `mutate` limited to genuinely high-consequence logic
- [ ] `break` threshold set for the file's maturity, ratcheted over time
- [ ] Every survivor inspected, not auto-dismissed
- [ ] Equivalent mutants documented with specific reasoning
- [ ] Killing tests assert behaviour, not implementation details

## Common Mistakes

- Reading a high mutation score as proof the logic is correct: it proves tests would notice a change, not that the original rule is right.
- Running solution-wide on every PR and then disabling the gate because it is slow.
- Writing tests that just echo the implementation to kill a mutant.

## Related Skills

- `creating-xunit-tests`: the tests being measured
- `detecting-regressions`: `test_would_catch` findings often name a mutation gap
