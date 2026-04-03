import type { Product } from './product';

export interface CartItem {
  id: number;
  productId: number;
  quantity: number;
  selectedOption: Record<string, string> | null;
  product: Product;
}

export interface CartResponse {
  items: CartItem[];
  totalPrice: number;
}
