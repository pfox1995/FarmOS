import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ProductListResponse, Product } from '@/types/product';

export function useProducts(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ['products', 'list', params],
    queryFn: async () => {
      const { data } = await api.get<ProductListResponse>('/api/products', { params });
      return data;
    },
  });
}

export function useProduct(id: number) {
  return useQuery({
    queryKey: ['products', 'detail', id],
    queryFn: async () => {
      const { data } = await api.get<Product>(`/api/products/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useSearchProducts(q: string, page = 1) {
  return useQuery({
    queryKey: ['products', 'search', q, page],
    queryFn: async () => {
      const { data } = await api.get<ProductListResponse>('/api/products/search', { params: { q, page } });
      return data;
    },
    enabled: q.length > 0,
  });
}
