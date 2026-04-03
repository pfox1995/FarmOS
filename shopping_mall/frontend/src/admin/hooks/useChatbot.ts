import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ChatLog } from '@/admin/types/chatlog';

export function useChatLogs(intent?: string) {
  return useQuery<ChatLog[]>({
    queryKey: ['chat-logs', intent],
    queryFn: async () => {
      const params = intent ? { intent } : {};
      const { data } = await api.get('/api/chatbot/logs', { params });
      return data;
    },
  });
}

export function useEscalatedChatLogs() {
  return useQuery<ChatLog[]>({
    queryKey: ['chat-logs-escalated'],
    queryFn: async () => {
      const { data } = await api.get('/api/chatbot/logs/escalated');
      return data;
    },
  });
}
