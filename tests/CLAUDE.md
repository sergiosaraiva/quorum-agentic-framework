# tests guide

This file exists because it is loaded when you work under `tests/`; the nearest CLAUDE.md wins and sets test conventions for the root guide.

## Projects

| Project | Scope | Needs |
|---------|-------|-------|
| `Api.UnitTests` | services and pure logic in isolation | nothing external |
| `Api.IntegrationTests` | real HTTP pipeline (`WebApplicationFactory`) against real PostgreSQL (Testcontainers) | Docker |

## Conventions

| Topic | Rule |
|-------|------|
| Framework | xUnit v3 with its built-in `Assert`; no third-party assertion or mocking library unless a decision records one |
| Naming | `Method_Scenario_Expected`; one behaviour per test; Arrange-Act-Assert with blank-line separation |
| Isolation | a test owns its data; never rely on test order; one container per test class via `IClassFixture`, unique ids per test |
| No mocked persistence | integration tests hit real PostgreSQL; unit tests use in-memory fakes of the real seam (a hand-written class, not a mock framework) |
| Auth in tests | replace JWT bearer with a test authentication scheme in the factory; also assert that an unauthenticated call returns 401 |
| Time and ids | inject `TimeProvider`; never read the wall clock in a test |
| Determinism | no sleeps; no network except the container |
| Regression tests | each reviewer finding with a `test_would_catch` scenario becomes a test that fails before the fix |

## Gates

| Gate | Tool | When |
|------|------|------|
| Mutation testing | Stryker.NET (`stryker-config.json`, run by `scripts/run-mutation-tests.sh`) | hot-path business logic only |
| Load | k6 against the deployed target; locally the explicit `LoadMeasurementTests` (below) | before a release, thresholds on p95 and error rate |
| End to end | Playwright | critical user journeys |

## Running

```bash
dotnet test --project tests/Api.UnitTests/Api.UnitTests.csproj
dotnet test --project tests/Api.IntegrationTests/Api.IntegrationTests.csproj   # requires Docker
```

Coverage (Microsoft code coverage extension, referenced by both test projects) and the figure for the test-automator `coverage` object:

```bash
dotnet test --solution Quorum.slnx --coverage --coverage-output-format cobertura --results-directory TestResults   # integration tests need Docker
python3 scripts/coverage_changed.py --base origin/main TestResults/*.cobertura.xml   # JSON: changed_files_pct, per file, not_measured
```

Mutation: `scripts/run-mutation-tests.sh` (needs Docker, takes minutes; Stryker runs on the Microsoft.Testing.Platform runner, which it marks as preview, so confirm a surprising result by hand). Edit `mutate` in `stryker-config.json` to the flagged hot-path files; it ships pointing at `OrdersService.cs` as the sample.

Load measurement (TQ-016, OD-030): `Api.IntegrationTests/LoadMeasurementTests` is `[Fact(Explicit = true)]`, so a normal `dotnet test` skips it (it shows as one skipped test). It starts its own PostgreSQL container, seeds 1M orders with `generate_series`, runs `ANALYZE`, then drives the real API in process and prints latency tables and a pool and concurrency table. It took 8 to 20 minutes at the defaults on the measured machine (fewer pools, users or rows shorten it). Docker only through the WSL engine.

```bash
QUORUM_LOAD_OUT=measurement.md dotnet test --project tests/Api.IntegrationTests/Api.IntegrationTests.csproj --explicit only --filter-class "*LoadMeasurementTests"
```

The runner hides the output of a passing test, so read the table from `QUORUM_LOAD_OUT` (default `TestResults/load-measurement.md` under the test output folder). Optional environment variables: `QUORUM_LOAD_ROWS` (1000000), `QUORUM_LOAD_REPS` (30), `QUORUM_LOAD_ROUNDS` (5), `QUORUM_LOAD_POOL_SIZES` (`100,50,20,10`), `QUORUM_LOAD_USERS` (`1,5,25,50`), `QUORUM_LOAD_MAX_PAGE_NUMBER` (default from Options). The figures are one single-machine data point, never a production figure: re-run on the deployment target before release.
