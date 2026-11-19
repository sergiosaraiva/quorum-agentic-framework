---
name: evaluating-usability
description: Use when reviewing a screen or flow for usability, defining the UX of a screen that has no design yet, reviewing a design before implementation, or writing UX acceptance criteria. Task-scoped cognitive walkthrough, heuristic checks, state and microcopy checks, accessibility (WCAG 2.2 AA default) and severity rubric.
---

# Evaluating Usability

Findings are evidence-backed observations, never a bare pass/fail verdict.

## 1. Context first

Before judging, state: who the user is, their task, frequency (daily vs occasional), device and environment, and the cost of an error. A review without a named task is opinion.

## 2. Methods, most reliable first

| Method | Use |
|--------|-----|
| Cognitive walkthrough of one named task | Per step: will the user know what to do, see the control, link it to their goal, understand the feedback? |
| Heuristic review (section 3) | Broad sweep of a screen |
| State and microcopy audit (sections 4-5) | Every state, every label and message |
| Accessibility check (section 6) | Automated scan plus keyboard pass plus screen-reader spot-check |
| Real-user testing | Recommend when risk is high; you cannot replace it |

## 3. Heuristics as concrete checks

| Heuristic | Check |
|-----------|-------|
| Visibility of status | Loading, saving, success and progress are shown; long actions give feedback within about 1 s |
| Match to the user's language | Labels use the user's domain terms, never internal codes or enum values |
| Control and freedom | Cancel, undo or confirm-before-destroy; back works; unsaved changes warned |
| Consistency | Same action, same label, same place across screens; native conventions respected |
| Error prevention | Constraints, sensible defaults, disabled-with-reason, confirmation for irreversible actions |
| Recognition over recall | Options visible; context kept; no memorizing values from another screen |
| Efficiency | Shortcuts, bulk actions, remembered filters, fewest steps and page switches for frequent tasks |
| Minimal design | Each element earns its place; primary action is obvious, one per view |
| Error recovery | Message says what happened, why, and the fix; input preserved |
| Help | Inline hints where the doubt occurs, not a separate manual |

## 4. States

Every data-bound view defines: loading, empty (with the next action), error (with retry), partial, success, disabled, and permission-denied. Tables add sorting, paging or virtual scroll, and no-results-for-filter. Forms add pristine, dirty, invalid, submitting, submitted.

## 5. Microcopy

Verb-first button labels naming the outcome ("Save report", not "OK"); sentence case; one term per concept; errors in plain language, no stack or status codes shown to users; numbers, dates and currency formatted for the locale; units visible.

## 6. Accessibility (WCAG 2.2 AA default)

| Area | Check |
|------|-------|
| Keyboard | Every function reachable and operable by keyboard; logical focus order; no traps; visible focus; skip link on page-level layouts |
| Names and roles | Native elements first; every control has an accessible name; ARIA only where native cannot |
| Contrast | 4.5:1 text, 3:1 large text and UI components; colour never the only signal |
| Target size | At least 24x24 CSS px |
| Forms | Visible labels, errors tied to fields (`aria-describedby`), required marked in text |
| Dynamic content | Status and errors announced (`role="status"` / `role="alert"`); focus managed on dialogs and route changes |
| Motion and zoom | Reflow at 320 px width and 200% zoom; respect `prefers-reduced-motion` |

## 7. Severity rubric

| Level | Meaning |
|-------|---------|
| Blocker | User cannot complete the task, or data loss or wrong action likely |
| Major | Task completed with significant difficulty, error or detour |
| Minor | Friction or inconsistency; workaround obvious |
| Note | Polish or idea |

Rate by frequency x impact x persistence. Accessibility failures that block keyboard or screen-reader completion are Major or higher.

## 8. Finding format

```
UX-01  Major  Orders table, "Refund" action (file + anchor)
Scenario: Walkthrough of "refund an invoice": the button label is "Process"; no confirmation; success shows nothing.
Category: visibility of status, error prevention
Fix: label "Refund invoice", confirm dialog stating amount, success message with a link to the refund.
```

## 9. Defining a screen (no design exists)

Produce: the user task and frequency; the flow with step count; layout of regions; every state from section 4; components with reuse of existing ones first; microcopy; keyboard path; acceptance criteria. Choose where the next step lives: inline edit, expandable row, side panel, modal, or page; prefer the lightest that keeps context. Say what was deferred.

## 10. UX acceptance criteria

Write testable lines: "From the orders list, a user refunds an invoice in at most 3 interactions", "Each state in section 4 is reachable and displays a next action", "All controls operable by keyboard only", "Axe scan has no serious or critical violations". These feed `test-automator` and `writing-playwright-e2e-tests`.

## Quality Checklist

- [ ] Context of use and task stated
- [ ] Each finding has evidence, a heuristic, a severity and a fix
- [ ] All states and microcopy reviewed
- [ ] Accessibility checked, keyboard path included
- [ ] Reuse of existing components considered before new ones
- [ ] No verdict without evidence; limits of the review stated

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| "Looks fine" | Name the task and the evidence |
| Reviewing only the happy path | Walk every state |
| Machine codes in labels | User-language labels |
| Accessibility as a final pass | Check during definition and review |

## Related Skills

- `frontend`: implementation rules
- `writing-playwright-e2e-tests`: automating the acceptance criteria
