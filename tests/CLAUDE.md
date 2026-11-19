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
| Mutation testing | Stryker.NET | hot-path business logic only |
| Load | k6 | before a release, thresholds on p95 and error rate |
| End to end | Playwright | critical user journeys |

## Running

```bash
dotnet test --project tests/Api.UnitTests/Api.UnitTests.csproj
dotnet test --project tests/Api.IntegrationTests/Api.IntegrationTests.csproj   # requires Docker
```
