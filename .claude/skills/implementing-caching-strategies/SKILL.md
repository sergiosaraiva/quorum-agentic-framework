---
name: implementing-caching-strategies
description: Implements caching only when a measured need exists, choosing tenant-safe HybridCache, IMemoryCache for single-instance-safe non-tenant data, or a distributed cache (Redis/ElastiCache) for data shared across scaled-out instances, with explicit expiration and invalidation. Use when a profiled read is slow or loads the database, or when reviewing a cache for staleness and tenant-leak risk.
---

# Implementing Caching Strategies

Design Principles: `.claude/agents/_SHARED-PATTERNS.md`.

## When NOT to Cache

A cache adds invalidation, staleness, tenant-leak and memory risk. Add one only if all hold:

- A measured problem exists (profiled latency or database load on this exact read); record the measurement in the PR
- The data tolerates staleness for the chosen expiry, or the write path can invalidate it explicitly
- Cheaper fixes were tried: an index, a better query, `AsNoTracking`, fewer round trips, a smaller projection (`tuning-postgresql-queries`)

Never cache per-request authorization decisions, data needing read-your-writes, or cheap results. Expiry and size limits are tunables: Options (`creating-configuration-options`).

## Quick Reference

- Use `HybridCache` (in-process L1 plus optional distributed L2, stampede protection built in): one mechanism instead of a per-call-site choice between memory and distributed
- Tenant data (including reference data in a per-tenant database): feature code does not inject `IMemoryCache`/`HybridCache` directly. It uses a thin `ITenantCache` wrapper that derives the key prefix (`t:{tenantId}:`) and a tag (`tenant:{tenantId}`) from the resolved tenant, never from a caller-supplied prefix. Skip the wrapper in a single-tenant product
- Anything that captures the tenant resolver or `ITenantCache` is registered `Scoped`, never `Singleton` (a singleton would bind the first tenant for every later request)
- Offboarding or incident response that must drop one tenant's entries goes through an admin path using the tag, not key scanning (`KEYS`/`SCAN`)
- Genuinely non-tenant, process-wide data (static config) may use `IMemoryCache`; say so in a comment
- Every entry has an explicit expiration; none lives forever
- Cache-aside: check, miss, query, store, return
- When more than one instance runs, an in-memory cache is per instance: acceptable only for data where brief divergence is harmless, otherwise add the distributed L2

## Decision Tree

```
Measured need?                         -> no: do not cache
Tenant data?                           -> ITenantCache (HybridCache-backed), never raw IMemoryCache
Non-tenant, process-wide, staleness ok?-> IMemoryCache with a comment
Shared across instances and must agree?-> HybridCache with a distributed L2 (Redis/ElastiCache)
Changed by a write elsewhere?          -> explicit RemoveAsync in the write path; TTL alone is not correctness
One tenant must be purged?             -> tag-based admin purge
```

## Example

```csharp
// GetOrCreateAsync returns ValueTask<T>; keep the method ValueTask<T> (no implicit conversion to Task<T>).
public sealed class CountryLookupService(ITenantCache cache, AppDbContext db, IOptions<CacheOptions> options)
{
    public ValueTask<IReadOnlyList<CountryDto>> GetAllAsync(CancellationToken ct) =>
        cache.GetOrCreateAsync("countries:all", async innerCt =>
        {
            var rows = await db.Countries.AsNoTracking().ToListAsync(innerCt);
            return (IReadOnlyList<CountryDto>)rows.Select(CountryDto.FromEntity).ToList();
        }, new HybridCacheEntryOptions { Expiration = options.Value.LookupExpiration }, ct);
}

// Program.cs
builder.Services.AddHybridCache();
builder.Services.AddScoped<CountryLookupService>();   // Scoped: it captures the tenant-aware cache
```

Write path:

```csharp
await db.SaveChangesAsync(ct);
await cache.RemoveAsync("countries:all", ct);   // invalidate explicitly
```

Distributed L2 (only after a measured need): register `AddStackExchangeRedisCache(...)` with the endpoint from Options and a secret from the secrets manager; provision the cache cluster through your infrastructure-as-code tool (`implementing-infrastructure-as-code`, flag the tool choice).

## Quality Checklist

- [ ] A recorded measurement justifies the cache
- [ ] Explicit expiration from Options; explicit invalidation where correctness depends on it
- [ ] Tenant data keyed and tagged by the resolved tenant; tenant-capturing services are `Scoped`
- [ ] No authorization decision or read-your-writes data cached
- [ ] A test proves tenant A's entry is not served to tenant B

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| Cache added because "it might be slow" | Measure first |
| Raw `IMemoryCache` for tenant data | Tenant-aware wrapper |
| `Singleton` service capturing the tenant cache | `Scoped` |
| No expiry | Explicit expiry |
| Relying on TTL for correctness-sensitive data | Invalidate in the write path |
| Purging by `KEYS`/`SCAN` | Tag-based removal |

## Related Skills

`creating-application-services`, `database`, `creating-configuration-options`, `tuning-postgresql-queries`.
