import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { HarvestSchedule, HarvestCreatePayload } from '@/admin/types/harvest';

export function useHarvestSchedules() {
  return useQuery<HarvestSchedule[]>({
    queryKey: ['harvest-schedules'],
    queryFn: async () => {
      const { data } = await api.get('/api/calendar');
      return data;
    },
  });
}

export function useCreateHarvestSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: HarvestCreatePayload) => {
      const { data } = await api.post('/api/calendar', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['harvest-schedules'] });
    },
  });
}
