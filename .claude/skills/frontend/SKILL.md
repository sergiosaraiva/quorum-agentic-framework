---
name: frontend
description: Use when creating or changing Angular components or pages. Standalone components, signals for state, OnPush change detection, strict TypeScript, plain Angular with CSS/SCSS (no mandated component library), explicit loading/error/empty/data states and accessible markup (WCAG 2.2 AA default).
---

# Creating Angular Components

Design Principles: `.claude/agents/_SHARED-PATTERNS.md` `## Design Principles` (simplest design, reuse first, no hard-coded values).

## Quick Reference

| Topic | Rule |
|-------|------|
| Components | Standalone only; no `NgModule` for new features. Omit `standalone: true` if your Angular major defaults to it (verify) |
| Change detection | `ChangeDetectionStrategy.OnPush` on every component unless your Angular major already defaults to it (verify) |
| State | `signal()` / `computed()`; inputs `input()` / `input.required()`; outputs `output()`. No `@Input()`/`@Output()` decorators in new code |
| Templates | `@if` / `@for` / `@switch`. `track <stable id>` on every `@for`; never `$index` on a reorderable list |
| Async data | Every component or page that loads data renders 4 states: loading, error, empty, data |
| TypeScript | `strict: true`; no `any` without a one-line justifying comment |
| Forms | Reactive Forms (`FormGroup`/`FormControl`) beyond one trivial field |
| Styling | Plain CSS/SCSS, component-scoped for layout; shared look from design tokens (CSS custom properties) in one global stylesheet. No second component library or utility framework unless the team decided it |
| Accessibility | WCAG 2.2 AA is the default bar: semantic elements first, labelled controls, visible focus, keyboard operable, contrast, live region for async status |
| Config | URLs, page sizes, thresholds, switches come from the API, a typed runtime config service or `environment` config; a fixed UI constant is a named `const` |

## Decision Tree

```
Async data?                  -> 4 states. A shared state-container component once 2+ pages repeat the same states
Local reactive state?        -> signal() + computed(), not a mutable class field
React to an input changing?  -> read the input signal in computed()/effect(); no ngOnChanges
State shared across unrelated components? -> managing-state-with-signals
Need a shared component?     -> reuse an existing one; extract only at the third real use (second if copies must agree)
Form?                        -> Reactive Forms
Native element exists (button, a, select, dialog)? -> use it before building a custom widget
```

## Example: all four states

```typescript
@Component({
  selector: 'app-report-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (reports.isLoading()) {
      <p role="status">Loading reports</p>
    } @else if (reports.error()) {
      <p role="alert">Reports could not be loaded. Try again.</p>
    } @else if (!reports.hasValue() || reports.value().items.length === 0) {
      <p>No reports yet.</p>
    } @else {
      <ul>
        @for (report of reports.value().items; track report.id) {
          <li>{{ report.title }}</li>
        }
      </ul>
    }
  `,
})
export class ReportList {
  private readonly api = inject(ReportsApi);
  protected readonly reports = this.api.listReports(); // see creating-angular-api-clients
}
```

Why: the four states are one flat chain ending in an unconditional `@else`, so no combination renders nothing. The empty guard uses `!hasValue() ||` so the final branch reads `value()` without `!`. Status text uses `role="status"`/`role="alert"` so assistive technology announces it.

## Example: signal inputs and derived state

```typescript
export class ReportFilter {
  readonly reports = input.required<ReportDto[]>();
  readonly status = signal<'all' | 'draft' | 'published'>('all');
  readonly visible = computed(() =>
    this.reports().filter(r => this.status() === 'all' || r.status === this.status()));
}
```

## Accessibility baseline (every UI change)

- Interactive elements are real `button`/`a`/`input`; a click handler on a `div` is a defect.
- Every control has a programmatic label (`label for`; `aria-label` only when no visible text).
- Focus order follows reading order; focus is visible and moved deliberately after a dialog opens or a route changes.
- Colour is never the only signal; text contrast 4.5:1, large text and UI components 3:1.
- Target size at least 24x24 CSS px; errors name the field and the fix.

## Quality Checklist

- [ ] No `NgModule`, no `*ngIf`/`*ngFor`, no decorator inputs/outputs in new code
- [ ] OnPush in effect; no mutation of signal values in place
- [ ] 4 states handled for anything async; `track` on every `@for`
- [ ] No `any` without justification; no hard-coded URLs, limits or switches
- [ ] Keyboard path and accessible names verified for each new control
- [ ] No speculative store, wrapper or generic base component

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `@Input() report!: ReportDto` | `report = input.required<ReportDto>()` |
| `ngOnChanges` to recompute | `computed()` reading the input signal |
| Blank screen on an empty list | Explicit empty state with the next action |
| `<div (click)>` | `<button type="button" (click)>` |
| `track $index` on a reorderable list | `track item.id` |

## Related Skills

- `creating-angular-api-clients`: typed data source
- `managing-state-with-signals`: shared state
- `writing-angular-tests`, `writing-playwright-e2e-tests`: tests
- `evaluating-usability`: UX review of the result
