import { InjectionToken } from '@angular/core';

/** Base URL of the API. Override per environment in app.config.ts; never hard-code it in a service. */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => '/api',
});
