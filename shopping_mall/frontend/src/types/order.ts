import type { Product } from './product';

export interface Order {
  id: number;
  totalPrice: number;
  status: string;
  shippingAddress: ShippingAddress | null;
  paymentMethod: string | null;
  createdAt: string;
  items: OrderItem[];
}

export interface OrderItem {
  id: number;
  productId: number;
  quantity: number;
  price: number;
  selectedOption: Record<string, string> | null;
  product: Product;
}

export interface ShippingAddress {
  zipCode: string;
  address: string;
  detail: string;
  recipient: string;
  phone: string;
}

export interface OrderCreateRequest {
  items: { productId: number; quantity: number; selectedOption?: Record<string, string> }[];
  shippingAddress: ShippingAddress;
  paymentMethod: string;
}
