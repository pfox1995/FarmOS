import type { Category } from './category';
import type { Store } from './store';

export interface Product {
  id: number;
  name: string;
  description: string | null;
  price: number;
  discountRate: number;
  thumbnail: string | null;
  images: string[];
  options: ProductOption[];
  stock: number;
  rating: number;
  reviewCount: number;
  salesCount: number;
  createdAt: string;
  category?: Category;
  store?: Store;
  storeName?: string;
}

export interface ProductOption {
  name: string;
  values: string[];
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
