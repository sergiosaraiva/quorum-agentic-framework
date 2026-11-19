import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AUTH_TOKEN, authInterceptor } from './auth.interceptor';
import { API_BASE_URL } from './api-config';

describe('authInterceptor', () => {
  function setup(token: string | null | undefined, apiBase = '/api') {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: apiBase },
        ...(token === undefined ? [] : [{ provide: AUTH_TOKEN, useValue: () => token }]),
      ],
    });
    return { http: TestBed.inject(HttpClient), controller: TestBed.inject(HttpTestingController) };
  }

  it('adds a bearer header when a token is available', () => {
    const { http, controller } = setup('abc123');

    http.get('/api/orders').subscribe();

    expect(controller.expectOne('/api/orders').request.headers.get('Authorization')).toBe('Bearer abc123');
  });

  it('adds no header when the provider returns null', () => {
    const { http, controller } = setup(null);

    http.get('/api/orders').subscribe();

    expect(controller.expectOne('/api/orders').request.headers.has('Authorization')).toBe(false);
  });

  it('adds no header with the default provider', () => {
    const { http, controller } = setup(undefined);

    http.get('/api/orders').subscribe();

    expect(controller.expectOne('/api/orders').request.headers.has('Authorization')).toBe(false);
  });

  it('adds the header for the configured absolute API base URL', () => {
    const { http, controller } = setup('abc123', 'https://api.example.com/v1');

    http.get('https://api.example.com/v1/orders').subscribe();

    expect(controller.expectOne('https://api.example.com/v1/orders').request.headers.get('Authorization')).toBe('Bearer abc123');
  });

  it('adds no header for a foreign host', () => {
    const { http, controller } = setup('abc123');

    http.get('https://evil.example.org/steal').subscribe();

    expect(controller.expectOne('https://evil.example.org/steal').request.headers.has('Authorization')).toBe(false);
  });

  it('adds no header for a host that only shares the API base URL as a prefix', () => {
    const { http, controller } = setup('abc123', 'https://api.example.com');

    http.get('https://api.example.com.evil.org/orders').subscribe();

    expect(controller.expectOne('https://api.example.com.evil.org/orders').request.headers.has('Authorization')).toBe(false);
  });

  it('adds no header for a protocol-relative URL to another host', () => {
    const { http, controller } = setup('abc123');

    http.get('//evil.example.org/steal').subscribe();

    expect(controller.expectOne('//evil.example.org/steal').request.headers.has('Authorization')).toBe(false);
  });
});
