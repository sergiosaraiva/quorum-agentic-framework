import { HttpInterceptorFn } from '@angular/common/http';
import { InjectionToken, inject } from '@angular/core';
import { API_BASE_URL } from './api-config';

/**
 * Supplies the current access token, or null when the user is not signed in.
 * The default returns null (no authentication wired yet). Override it in app.config.ts with your
 * identity provider integration, for example `{ provide: AUTH_TOKEN, useValue: () => session.accessToken() }`.
 */
export const AUTH_TOKEN = new InjectionToken<() => string | null>('AUTH_TOKEN', {
  providedIn: 'root',
  factory: () => () => null,
});

/** True for same-origin URLs (relative or absolute) and for URLs under the configured API base URL. */
function isTrustedUrl(url: string, apiBase: string): boolean {
  try {
    if (new URL(url, location.origin).origin === location.origin) {
      return true;
    }
  } catch {
    return false; // unparseable URL: never send credentials
  }
  const base = apiBase.endsWith('/') ? apiBase : `${apiBase}/`;
  return url === apiBase || url.startsWith(base);
}

/**
 * Adds `Authorization: Bearer <token>` when a token is available AND the request goes to this app's origin or
 * the configured API base URL. A request to any other host never receives the token.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(AUTH_TOKEN)();
  if (!token || !isTrustedUrl(req.url, inject(API_BASE_URL))) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
