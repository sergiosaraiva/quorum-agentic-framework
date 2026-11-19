---
name: creating-dtos-and-validation
description: Creates request/response DTOs as C# records with server-side validation via DataAnnotations or FluentValidation, and hand-written entity-to-DTO mapping. Use when adding or changing an API request or response shape, a validator, or a column-length limit shared by DTO, validator and database.
---

# Creating DTOs and Validation

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## Quick Reference

- DTOs are `record` types: immutable, value equality, concise. Defined in the feature's `Dtos.cs`
- One request type and one response type per use case. Never reuse one DTO for both directions (a request must not accept a response-only field)
- Never return an EF Core entity from an endpoint; map to a response DTO with a static `FromEntity(...)` factory next to the DTO. No AutoMapper unless the team explicitly chooses it
- No parallel domain/application/API DTO copies, no generic `Result<T>` envelope hierarchy, no validator for a type with no rules
- Server-side validation is mandatory regardless of client-side checks
- A limit that mirrors a column length is one named `const` beside the DTO, reused by the validator and the EF configuration. The Angular form mirrors it as one named constant. Tunable business limits come from Options (`creating-configuration-options`)
- Expose enums as strings (`JsonStringEnumConverter` or map to string), never raw ordinals
- Response DTOs omit internal-only fields (soft-delete flags, audit principals the client should not see)

## Decision Tree

```
Simple required/range/length checks only?   -> DataAnnotations on the record (use [property: ...] on positional records)
Cross-field or conditional validation?      -> FluentValidation
Response differs from the entity?           -> dedicated response DTO + FromEntity
No rules at all (a bare id)?                -> no validator class
Two features need the same DTO?             -> duplicate until the third; share only a genuinely single concept
```

## Examples

```csharp
// Features/Reports/Dtos.cs
public sealed record CreateReportRequest(string Title, DateOnly PeriodStart, DateOnly PeriodEnd)
{
    public const int TitleMaxLength = 200;   // mirrors the column length; declared once
}

public sealed class CreateReportRequestValidator : AbstractValidator<CreateReportRequest>
{
    public CreateReportRequestValidator()
    {
        RuleFor(x => x.Title).NotEmpty().MaximumLength(CreateReportRequest.TitleMaxLength);
        RuleFor(x => x.PeriodEnd).GreaterThanOrEqualTo(x => x.PeriodStart)
            .WithMessage("PeriodEnd must not be before PeriodStart");
    }
}

public sealed record ReportDto(Guid Id, string Title, DateOnly PeriodStart, DateOnly PeriodEnd, string Status)
{
    public static ReportDto FromEntity(Report e) => new(e.Id, e.Title, e.PeriodStart, e.PeriodEnd, e.Status.ToString());
}

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
- [ ] The validator is actually invoked (DataAnnotations via `AddValidation()` is automatic; FluentValidation is not)
- [ ] No entity exposed; no internal-only field in a response
- [ ] Every string has a length limit; limits declared once
- [ ] `FromEntity` lives with the DTO

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Endpoint returns the entity | Map to a response DTO |
| Mutable `class` DTO | `record` with positional or init-only properties |
| Validation only in the Angular form | Server-side validation always |
| `MaximumLength(200)` repeated in validator, EF config and form | One `const`, reused |
| Extra DTO layers, mapper profiles, `Result<T>` wrappers for one endpoint | One request, one response, hand-written mapping |
| Enum serialized as int | String conversion |

## Related Skills

`backend`, `creating-application-services`, `database`.
