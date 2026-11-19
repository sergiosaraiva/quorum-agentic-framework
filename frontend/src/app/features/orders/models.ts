// Mirrors src/Api/Features/Orders/Dtos.cs; change both in the same PR.
export interface OrderResponse {
  id: string;
  customerName: string;
  totalAmount: number;
  status: string;
  createdAt: string;
}

export interface PagedResponse<T> {
  items: T[];
  page: number;
  pageSize: number;
  totalCount: number;
}
