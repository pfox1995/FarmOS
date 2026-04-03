import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ExpenseEntry, ExpenseCreatePayload } from '@/admin/types/expense';

export function useExpenses(startDate?: string, endDate?: string) {
  return useQuery<ExpenseEntry[]>({
    queryKey: ['expenses', startDate, endDate],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const { data } = await api.get('/api/reports/expenses', { params });
      return data;
    },
  });
}

export function useCreateExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ExpenseCreatePayload) => {
      const { data } = await api.post('/api/reports/expenses', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
    },
  });
}

export function useClassifyExpenses() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/api/reports/expenses/classify');
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expenses'] });
    },
  });
}
