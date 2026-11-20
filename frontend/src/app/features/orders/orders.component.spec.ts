import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { OrdersComponent } from './orders.component';

describe('OrdersComponent', () => {
  function setup() {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const fixture = TestBed.createComponent(OrdersComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    return { fixture, http };
  }

  it('renders the empty state when the API returns no orders', async () => {
    const { fixture, http } = setup();

    http.expectOne((r) => r.url === '/api/orders').flush({ items: [], page: 1, pageSize: 20, totalCount: 0 });
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No orders yet.');
  });

  it('renders a row per order', async () => {
    const { fixture, http } = setup();

    http.expectOne((r) => r.url === '/api/orders').flush({
      items: [{ id: '1', customerName: 'Acme Ltd', totalAmount: 10, status: 'draft', createdAt: '2026-01-01T00:00:00Z' }],
      page: 1, pageSize: 20, totalCount: 1,
    });
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Acme Ltd');
  });

  it('renders the error state when the request fails', async () => {
    const { fixture, http } = setup();

    http.expectOne((r) => r.url === '/api/orders').flush('boom', { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('could not be loaded');
  });
});
