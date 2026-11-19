import { ChangeDetectionStrategy, Component } from '@angular/core';
import { OrdersComponent } from './features/orders/orders.component';

@Component({
  selector: 'app-root',
  imports: [OrdersComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: '<main><h1>Orders (example)</h1><app-orders /></main>',
})
export class App {}
