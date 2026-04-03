import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Shipment, ShipmentCreatePayload } from '@/admin/types/shipment';

export function useShipments(status?: string) {
  return useQuery<Shipment[]>({
    queryKey: ['shipments', status],
    queryFn: async () => {
      const params = status ? { status } : {};
      const { data } = await api.get('/api/shipments', { params });
      return data;
    },
  });
}

export function useCreateShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ShipmentCreatePayload) => {
      const { data } = await api.post('/api/shipments', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shipments'] });
    },
  });
}
