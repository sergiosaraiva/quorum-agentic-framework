import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { OrdersApiService } from './orders-api.service';
import { OrderResponse } from './models';

type ViewState = 'loading' | 'error' | 'empty' | 'data';

@Component({
  selector: 'app-orders',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @switch (state()) {
      @case ('loading') { <p role="status">Loading orders...</p> }
      @case ('error') { <p role="alert" class="error">Orders could not be loaded.</p> }
      @case ('empty') { <p>No orders yet.</p> }
      @case ('data') {
        <table>
          <caption>Orders</caption>
          <thead><tr><th>Customer</th><th>Total</th><th>Status</th></tr></thead>
          <tbody>
            @for (order of orders(); track order.id) {
              <tr><td>{{ order.customerName }}</td><td>{{ order.totalAmount }}</td><td>{{ order.status }}</td></tr>
            }
          </tbody>
        </table>
      }
    }
  `,
  styles: `.error { color: var(--color-error); }`,
})
export class OrdersComponent implements OnInit {
  private readonly api = inject(OrdersApiService);

  protected readonly orders = signal<OrderResponse[]>([]);
  protected readonly state = signal<ViewState>('loading');

  ngOnInit(): void {
    this.api.list().subscribe({
      next: (page) => {
        this.orders.set(page.items);
        this.state.set(page.items.length === 0 ? 'empty' : 'data');
      },
      error: () => this.state.set('error'),
    });
  }
}
