---
name: creating-dtos-and-validation
description: Creates request/response DTOs as C# records with server-side validation via DataAnnotations or FluentValidation, and hand-written entity-to-DTO mapping. Use when adding or changing an API request or response shape, a validator, or a column-length limit shared by DTO, validator and database.
---

# Creating DTOs and Validation

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- DTOs are `record` types: immutable, value equality, concise. Defined in the feature's `Dtos.cs`
- One request type and one response type per use case. Never reuse one DTO for both directions (a request must not accept a response-only field)
- Never return an EF Core entity from an endpoint; map to a response DTO by hand. For queries prefer a mapping expression inside the EF `Select` projection (EF selects only the needed columns; landed: private `OrdersService.ToResponse`); a static `FromEntity(...)` next to the DTO is the option for in-memory mapping. No AutoMapper unless the team explicitly chooses it
- No parallel domain/application/API DTO copies, no generic `Result<T>` envelope hierarchy, no validator for a type with no rules
- Server-side validation is mandatory regardless of client-side checks. DataAnnotations is the default for simple rules: call `Validator.TryValidateObject` in the endpoint, as the landed Orders code does (`OrdersEndpoints.cs`; `CreateOrderRequest` in `Dtos.cs` is the model). `AddValidation()` is not registered in `Program.cs`; an adopter who registers it gets automatic checking; add FluentValidation only for cross-field or conditional rules
- A limit that mirrors a column length is one named `const` on the entity in `src/Infrastructure` (which does not reference `src/Api`), referenced by the DTO, the validator and the EF configuration (landed: `Order.CustomerNameMaxLength`, used by `OrderConfiguration`, `CreateOrderRequest`, `OrderListFilter`). The Angular form mirrors it as one named constant. Tunable business limits come from Options (`creating-configuration-options`)
- Expose enums as strings (`JsonStringEnumConverter` or map to string), never raw ordinals
- Response DTOs omit internal-only fields (soft-delete flags, audit principals the client should not see)

## Decision Tree

```
Simple required/range/length checks only?   -> DataAnnotations on the record (use [property: ...] on positional records)
Cross-field or conditional validation?      -> FluentValidation
Response differs from the entity?           -> dedicated response DTO + `Select` projection (queries) or FromEntity (in-memory)
No rules at all (a bare id)?                -> no validator class
Two features need the same DTO?             -> duplicate until the third; share only a genuinely single concept
```

## Examples

The first example below (FluentValidation, Reports) is illustrative, not template code; use it when a rule spans fields. The DataAnnotations example after it is the default; the landed `CreateOrderRequest` is the real one.

```csharp
// Features/Reports/Dtos.cs
// Infrastructure/Persistence/Entities/Report.cs: the limit lives on the entity, visible to Api and to the EF configuration
public class Report { public const int TitleMaxLength = 200; /* ... */ }

// Features/Reports/Dtos.cs
public sealed record CreateReportRequest(string Title, DateOnly PeriodStart, DateOnly PeriodEnd);

public sealed class CreateReportRequestValidator : AbstractValidator<CreateReportRequest>
{
    public CreateReportRequestValidator()
    {
        RuleFor(x => x.Title).NotEmpty().MaximumLength(Report.TitleMaxLength);
        RuleFor(x => x.PeriodEnd).GreaterThanOrEqualTo(x => x.PeriodStart)
            .WithMessage("PeriodEnd must not be before PeriodStart");
    }
}

public sealed record ReportDto(Guid Id, string Title, DateOnly PeriodStart, DateOnly PeriodEnd, string Status);

// In the service: project in the query so EF selects only these columns
db.Reports.Select(e => new ReportDto(e.Id, e.Title, e.PeriodStart, e.PeriodEnd, e.Status))
// In-memory option: a static ReportDto.FromEntity(Report e) next to the DTO

// Program.cs
builder.Services.AddValidatorsFromAssemblyContaining<Program>();
```

Registering validators only puts `IValidator<T>` in DI. The .NET 10 `AddValidation()` automatic enforcement covers DataAnnotations and `IValidatableObject` only, and only for types in the assembly where it is registered (a DTO in a referenced assembly silently passes). A FluentValidation validator therefore needs an explicit endpoint filter or a manual `ValidateAsync` call in the handler (`backend` skill, `CreateAsync`).

DataAnnotations case:

```csharp
public sealed record UpdateProfileRequest(
    [property: Required, MaxLength(100)] string DisplayName,
    [property: EmailAddress] string? ContactEmail);
```

`[ValidatableType]` and `[SkipValidation]` are experimental in .NET 10; verify against the SDK before using them.

## Quality Checklist

- [ ] DTO is a `record`; request and response are separate types
- [ ] The validator is actually invoked: `Validator.TryValidateObject` for DataAnnotations as Orders does (automatic only if `AddValidation()` is registered); FluentValidation needs an explicit call
- [ ] No entity exposed; no internal-only field in a response
- [ ] Every string has a length limit; limits declared once
- [ ] Mapping is a `Select` projection in the query, or `FromEntity` with the DTO for in-memory mapping

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Endpoint returns the entity | Map to a response DTO |
| Mutable `class` DTO | `record` with positional or init-only properties |
| Validation only in the Angular form | Server-side validation always |
| `MaximumLength(200)` repeated in validator, EF config and form | One `const` on the entity, reused |
| Extra DTO layers, mapper profiles, `Result<T>` wrappers for one endpoint | One request, one response, hand-written mapping |
| Enum serialized as int | String conversion |

## Related Skills

`backend`, `creating-application-services`, `database`.
