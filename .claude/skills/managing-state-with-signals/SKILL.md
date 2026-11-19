---
name: managing-state-with-signals
description: Use when state is shared across components in an Angular app. Signal store services with private writable signals, computed derivations and effects for side effects only, without adding NgRx unless a concrete limitation justifies it.
---

# Managing State with Signals

Design Principles: `.claude/agents/_SHARED-PATTERNS.md` `## Design Principles`. Local state stays local; a store is the exception.

## When NOT to Add a Store

| Situation | Do instead |
|-----------|-----------|
| State used by one component | `signal()` / `computed()` in the component |
| Server data only read and rendered | `httpResource`/`rxResource` in the component (`creating-angular-api-clients`) |
| Parent to child data | `input()` / `output()` |
| Fewer than 2 unrelated consumers | Local state |

No NgRx, event bus or generic `Store<T>` base class by default. At most one store per feature, provided at route level unless truly app-wide.

## Quick Reference

- A store is an injectable service: private writable `signal()`s, public `asReadonly()` and `computed()` views, mutation methods using `.set()` / `.update()`.
- Never mutate in place (`arr.push(x)`); produce a new reference with `.update(prev => [...prev, x])`.
- `computed()` derives values; never keep a second signal in sync by hand.
- `effect()` performs side effects (logging, persistence, analytics); never use it to set another signal.
- Scope: root-provided for app-wide state; provide in route `providers` or a component for feature or instance state.
- Escalate to NgRx or similar only for a concrete need (many transitions, time-travel debugging) and record why.

## Decision Tree

```
Shared by 2+ unrelated components?         -> signal store service
Derived purely from other signals?         -> computed()
Reacts to a signal changing (side effect)? -> effect()
Persist across reloads?                    -> effect() writing to storage inside try/catch; hydrate in the constructor
Complex state machine, many transitions?   -> consider NgRx, justify it
```

## Example: signal store

```typescript
@Injectable({ providedIn: 'root' })
export class ReportsStore {
  private readonly _reports = signal<ReportDto[]>([]);
  private readonly _selectedId = signal<string | null>(null);

  readonly reports = this._reports.asReadonly();
  readonly selected = computed(() =>
    this._reports().find(r => r.id === this._selectedId()) ?? null);
  readonly draftCount = computed(() =>
    this._reports().filter(r => r.status === 'draft').length);

  setReports(reports: ReportDto[]): void { this._reports.set(reports); }
  select(id: string): void { this._selectedId.set(id); }
  add(report: ReportDto): void { this._reports.update(prev => [...prev, report]); }
}
```

Only readonly signals and computed values are public, so nothing can bypass the store methods.

## Example: effect for a side effect

```typescript
constructor() {
  effect(() => {
    const selected = this.store.selected();
    if (selected) this.analytics.track('report_selected', { reportId: selected.id });
  });
}
```

If an `effect()` calls `.set()` on another signal, replace it with `computed()`.

## Loading state in a store

When a store owns the fetch, hold status explicitly: `status = signal<'idle' | 'loading' | 'error' | 'ready'>('idle')` plus the error. Components render the same four states as in `frontend`. Ignore stale responses when the request key changes (`switchMap` or a resource, not nested subscribes).

## Quality Checklist

- [ ] Writable signals private; only readonly signals and computed exposed
- [ ] No in-place mutation of array or object values
- [ ] `computed()` for derivation; `effect()` only for side effects
- [ ] At least 2 real consumers; scope (root vs route) matches the sharing need
- [ ] Storage reads and writes guarded against failure
- [ ] Tests exercise the store through its public signals (`writing-angular-tests`)

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `this._reports().push(r)` | `this._reports.update(p => [...p, r])` |
| `effect()` that sets another signal | `computed()` |
| Exposing the writable signal | `.asReadonly()` plus methods |
| NgRx for simple list/detail state | Signal store first |
| Copying `httpResource` data into a store with one consumer | Keep the resource in the component |

## Related Skills

- `frontend`: components consuming store signals
- `creating-angular-api-clients`: API calls feeding the store
- `writing-angular-tests`: store tests
