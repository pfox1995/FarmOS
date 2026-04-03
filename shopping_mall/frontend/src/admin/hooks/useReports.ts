import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { WeeklyReport } from '@/admin/types/report';

export function useWeeklyReports() {
  return useQuery<WeeklyReport[]>({
    queryKey: ['weekly-reports'],
    queryFn: async () => {
      const { data } = await api.get('/api/reports/weekly');
      return data;
    },
  });
}

export function useWeeklyReportDetail(id: number | null) {
  return useQuery<WeeklyReport>({
    queryKey: ['weekly-report', id],
    queryFn: async () => {
      const { data } = await api.get(`/api/reports/weekly/${id}`);
      return data;
    },
    enabled: id !== null,
  });
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/api/reports/weekly/generate');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['weekly-reports'] });
    },
  });
}
