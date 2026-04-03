import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { CartResponse } from '@/types/cart';

export function useCart() {
  return useQuery({
    queryKey: ['cart'],
    queryFn: async () => {
      const { data } = await api.get<CartResponse>('/api/cart');
      return data;
    },
  });
}

export function useAddToCart() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { productId: number; quantity: number; selectedOption?: Record<string, string> }) => {
      const { data } = await api.post('/api/cart', body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart'] }),
  });
}

export function useUpdateCartItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, quantity }: { id: number; quantity: number }) => {
      const { data } = await api.put(`/api/cart/${id}`, { quantity });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart'] }),
  });
}

export function useRemoveCartItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/cart/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart'] }),
  });
}
