import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { CustomerSegment, SegmentSummary } from '@/admin/types/segment';

export function useSegmentSummary() {
  return useQuery<SegmentSummary[]>({
    queryKey: ['segment-summary'],
    queryFn: async () => {
      const { data } = await api.get('/api/analytics/segments');
      return data;
    },
  });
}

export function useSegmentCustomers(segment: string | null) {
  return useQuery<CustomerSegment[]>({
    queryKey: ['segment-customers', segment],
    queryFn: async () => {
      const { data } = await api.get(`/api/analytics/segments/${segment}`);
      return data;
    },
    enabled: segment !== null,
  });
}

export function usePopularItems() {
  return useQuery<{ product_id: number; name: string; total_sold: number; revenue: number }[]>({
    queryKey: ['popular-items'],
    queryFn: async () => {
      const { data } = await api.get('/api/analytics/popular-items');
      return data;
    },
  });
}

export function useRefreshSegments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/api/analytics/segments/refresh');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segment-summary'] });
      queryClient.invalidateQueries({ queryKey: ['segment-customers'] });
    },
  });
}
