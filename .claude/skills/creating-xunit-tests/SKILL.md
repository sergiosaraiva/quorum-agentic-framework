---
name: creating-xunit-tests
description: Use when writing unit tests for C# services and business logic in isolation from the database and network. xUnit v3 with built-in Assert only, AAA structure, Theory data, NSubstitute at I/O seams. The default for a service method unless a database or HTTP dependency is explicitly in scope.
---

# Creating xUnit Tests

## Quick Reference

| Topic | Rule |
|-------|------|
| Structure | Arrange / Act / Assert, visibly separated |
| Name | `Method_Scenario_ExpectedResult`, for example `CalculateDuration_EndBeforeStart_Throws` |
| Assertions | xUnit v3 built-in `Assert` only; no third-party assertion library. Expected first: `Assert.Equal(expected, actual)`. Exceptions: `Assert.Throws<T>` / `await Assert.ThrowsAsync<T>`. Explain with `Assert.True(cond, message)` / `Assert.Fail(message)` |
| Cancellation | Pass `TestContext.Current.CancellationToken` to async calls (xUnit v3) |
| Data | `[Theory]` with `[InlineData]` / `[MemberData]` for one rule over many inputs, not copied `[Fact]`s |
| Doubles | NSubstitute only at I/O seams (HTTP client, clock, message bus). Pure classes and cheap in-memory collaborators are constructed for real |
| Time | Inject `TimeProvider`; use `FakeTimeProvider` in tests, never `DateTime.UtcNow` in logic |
| Scope | Behaviour and branches that can break. Not getters, DI wiring, framework code or private methods |
| Helpers | No custom assertion or test-base frameworks without 2+ current users |

## Decision Tree

```
Pure logic or calculation?                 -> [Fact]/[Theory], no mocks
Service with an external HTTP/bus seam?    -> NSubstitute the seam, assert on outcome and the call made
Depends on EF Core query behaviour, SQL, constraints, migrations? -> writing-integration-tests (Testcontainers); do not fake the DbContext
Endpoint pipeline, auth, validation?       -> writing-integration-tests
Asserting an exception?                    -> Assert.Throws and check the message or parameter name
```

Do not use the EF Core in-memory provider as a stand-in for PostgreSQL: it has no constraints, transactions or SQL translation, so it gives false confidence.

## Example: pure logic with Theory

```csharp
public sealed class DiscountCalculatorTests
{
    [Theory]
    [InlineData(99.99, 0)]      // below threshold
    [InlineData(100.00, 10)]    // exactly at threshold
    [InlineData(250.00, 25)]
    public void Calculate_OrderTotal_AppliesTenPercentFromThreshold(decimal total, decimal expected)
    {
        // Arrange
        var sut = new DiscountCalculator(threshold: 100m, rate: 0.10m);

        // Act
        var discount = sut.Calculate(total);

        // Assert
        Assert.Equal(expected, discount);
    }

    [Fact]
    public void Calculate_NegativeTotal_Throws()
    {
        var sut = new DiscountCalculator(100m, 0.10m);
        var ex = Assert.Throws<ArgumentOutOfRangeException>(() => sut.Calculate(-1m));
        Assert.Equal("total", ex.ParamName);
    }
}
```

The boundary row (exactly at threshold) is what mutation testing later demands (`running-mutation-tests`).

## Example: seam and clock

```csharp
[Fact]
public async Task SendReminder_InvoiceOverdue_CallsNotifierOnce()
{
    // Arrange
    var clock = new FakeTimeProvider(new DateTimeOffset(2026, 3, 1, 0, 0, 0, TimeSpan.Zero));
    var notifier = Substitute.For<INotifier>();
    var sut = new InvoiceReminderService(notifier, clock);
    var invoice = new Invoice(Guid.NewGuid(), dueDate: new DateOnly(2026, 2, 1));

    // Act
    await sut.SendReminderAsync(invoice, TestContext.Current.CancellationToken);

    // Assert
    await notifier.Received(1).NotifyAsync(invoice.Id, Arg.Any<string>(), Arg.Any<CancellationToken>());
}
```

## Quality Checklist

- [ ] AAA, descriptive name, one behaviour per test
- [ ] Built-in `Assert` only, expected value first
- [ ] Boundaries, null/empty and error paths covered, not just the happy path
- [ ] Mocks only at I/O seams; no real database or network
- [ ] No `DateTime.UtcNow`, `Random` or `Thread.Sleep` in tests; tests are deterministic and order-independent
- [ ] Each test would fail if the logic were wrong (not an always-true assertion)

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `Assert.Equal(actual, expected)` | expected first |
| Mocking a DbContext or using the in-memory provider | Testcontainers integration test |
| Asserting only `NotNull` | Assert the value or the observable effect |
| Copy-pasted `[Fact]`s per input | `[Theory]` |
| Testing private members | Test through the public behaviour |

## Related Skills

- `writing-integration-tests`: real HTTP and PostgreSQL
- `running-mutation-tests`: measures whether these tests catch bugs
- `detecting-regressions`: `test_would_catch` findings become tests here
