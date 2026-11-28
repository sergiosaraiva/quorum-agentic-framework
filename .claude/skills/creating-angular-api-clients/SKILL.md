---
name: creating-angular-api-clients
description: Use when an Angular feature needs to call the backend API. Typed HttpClient/httpResource services per resource, interceptors for auth and error mapping, and DTO parity with the C# records.
---

# Creating Angular API Clients

Design Principles: `.claude/agents/_SHARED-PATTERNS.md` `## Design Principles`.

## Quick Reference

| Topic | Rule |
|-------|------|
| Shape | One injectable service per resource (`ReportsApi` in the feature folder, `features/reports/reports-api.service.ts`; landed `features/orders/orders-api.service.ts`); never a god API service |
| Typing | Every call generic-typed (`http.get<ReportDto>`); no `any` responses |
| Interfaces | Mirror the backend DTO record field for field: names (camelCase JSON), types, nullability. Drift is a regression (`verifying-cross-file-coupling` C1) |
| Cross-cutting | Auth header, API origin and error mapping live in `HttpInterceptorFn`s registered once in `app.config.ts`; never per service |
| No wrappers | Call `HttpClient`/`httpResource` directly. No generic `BaseApiService<T>`, repository or mapper layer; no generated client unless OpenAPI generation is adopted deliberately |
| Config | Page sizes, polling intervals, timeouts, origin are config, not literals. The base URL comes from the `API_BASE_URL` token (`core/api-config.ts`); the resource path is a fixed constant of the service |
| Errors | The error interceptor maps every failure to one `ApiError` (`status`, `message`, problem `traceId`/`code`; status 0 = unreachable). Client methods do not catch or re-map; the component reads the error from the observable or the resource `.error()` |
| Allowed catch | A documented expected-status recovery (404 to `null`) that rethrows or logs everything else |

## Decision Tree

```
One-shot fetch or mutation?                     -> Observable from HttpClient
Read-and-render, refetch when a signal changes? -> httpResource() (request fn reads signals)
Needs retry, debounce, polling, composition?    -> Observable + RxJS (interval + switchMap; never setInterval + subscribe)
Auth header?                                    -> interceptor
Error display?                                  -> component decides from ApiError; client does nothing
```

Pick Observable or `httpResource` per method; do not write both for one call.

## Example: client

```typescript
export interface ReportDto { id: string; title: string; status: 'draft' | 'published' }
export interface Page<T> { items: T[]; page: number; pageSize: number; totalCount: number }   // mirrors PagedResponse<T>

@Injectable({ providedIn: 'root' })
export class ReportsApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${inject(API_BASE_URL)}/reports`;

  create(request: { title: string }): Observable<ReportDto> {
    return this.http.post<ReportDto>(this.baseUrl, request);
  }

  listReports(page: Signal<number> = signal(1), pageSize: Signal<number> = signal(20)) {
    // httpResource re-runs only when a signal read inside the function changes.
    return httpResource<Page<ReportDto>>(
      () => `${this.baseUrl}?page=${page()}&pageSize=${pageSize()}`);
  }
}
```

`httpResource()` must be created in an injection context (field initializer or constructor), or pass `{ injector }`. A default `pageSize` that can vary should come from config.

## Example: interceptors

```typescript
// Landed: core/auth.interceptor.ts. AUTH_TOKEN supplies the token; isTrustedUrl allows this origin and URLs under API_BASE_URL
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(AUTH_TOKEN)();
  if (!token || !isTrustedUrl(req.url, inject(API_BASE_URL))) return next(req);   // never send the token to other hosts
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};

export const errorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(catchError((e: unknown) => throwError(() => toApiError(e))));

// app.config.ts: bearer first (request side), error mapping sees the response
provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]));
```

A `startsWith('/api/')` prefix check is wrong: it never matches an absolute `API_BASE_URL`, so the token is silently dropped. Keep tokens in memory (or an httpOnly cookie flow), not `localStorage`, unless a security review accepted it.

## Quality Checklist

- [ ] One service per resource; every call typed; interfaces match the backend DTO exactly
- [ ] Auth and error mapping in interceptors; the token goes only to API URLs
- [ ] No per-method `catchError` that hides status, `traceId` or `code`
- [ ] No base class or wrapper; no unused second style for the same call
- [ ] Tunables are config; request paths are constants
- [ ] Tests use `HttpTestingController` (`writing-angular-tests`)

## Common Mistakes

| Wrong | Correct |
|-------|---------|
| `http.get(url)` untyped | `http.get<ReportDto>(url)` |
| Header set in every method | One interceptor |
| `ApiService<T>` pass-through base | `HttpClient` in the feature service |
| `.subscribe()` with no error handling | Handle `ApiError` in the component or read `.error()` |
| TS field `state` vs C# `Status` | Same name, camelCase on the wire |

## Related Skills

- `frontend`: consumes this data
- `managing-state-with-signals`: when a store owns the result
- `verifying-cross-file-coupling`: DTO to interface parity
