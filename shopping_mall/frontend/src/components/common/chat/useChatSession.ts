import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ChatSession, ChatSessionMessage } from './types.ts';

/**
 * Fetch all sessions for the user
 */
export function useListSessions(userId: number | null, enabled: boolean = true) {
  return useQuery({
    queryKey: ['chat-sessions', userId],
    queryFn: async () => {
      const { data } = await api.get('/api/chatbot/sessions', {
        params: { user_id: userId },
        headers: { 'X-User-Id': userId },
      });
      return data as ChatSession[];
    },
    enabled: !!userId && enabled,
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * Fetch the user's active session if one exists
 */
export function useActiveSession(userId: number | null) {
  return useQuery({
    queryKey: ['chat-active-session', userId],
    queryFn: async () => {
      const { data } = await api.get('/api/chatbot/sessions/active', {
        params: { user_id: userId },
        headers: { 'X-User-Id': userId },
      });
      return data as ChatSession | null;
    },
    enabled: !!userId,
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * Create a new chat session for the user
 */
export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: number) => {
      const { data } = await api.post('/api/chatbot/sessions', {
        user_id: userId,
      }, {
        headers: { 'X-User-Id': userId },
      });
      return data as ChatSession;
    },
    onSuccess: (newSession, userId) => {
      // Invalidate and refetch sessions list and active session query
      queryClient.invalidateQueries({ queryKey: ['chat-sessions', userId] });
      queryClient.invalidateQueries({ queryKey: ['chat-active-session', userId] });
      // Invalidate session messages cache for new session
      queryClient.invalidateQueries({ queryKey: ['chat-session-messages', newSession.id] });
      queryClient.invalidateQueries({ queryKey: ['chat-session', newSession.id] });
      // Force immediate refetch
      queryClient.refetchQueries({ queryKey: ['chat-active-session', userId] });
    },
  });
}

/**
 * Fetch a specific session by ID
 */
export function useGetSession(sessionId: number | null, userId: number | null = null) {
  return useQuery({
    queryKey: ['chat-session', sessionId],
    queryFn: async () => {
      // Get all sessions and find the matching one
      const { data } = await api.get('/api/chatbot/sessions', {
        params: { user_id: userId },
        headers: { 'X-User-Id': userId },
      });
      const sessions = data as ChatSession[];
      return sessions.find(s => s.id === sessionId) || null;
    },
    enabled: !!sessionId && !!userId,
    staleTime: 1000 * 30, // 30 seconds
  });
}

/**
 * Fetch messages for a specific session
 */
export function useSessionMessages(sessionId: number | null, userId: number | null = null) {
  return useQuery({
    queryKey: ['chat-session-messages', sessionId],
    queryFn: async () => {
      const { data } = await api.get(`/api/chatbot/sessions/${sessionId}/messages`, {
        headers: { 'X-User-Id': userId },
      });
      return data as ChatSessionMessage[];
    },
    enabled: !!sessionId,
    staleTime: 1000 * 60 * 5, // 5 minutes - 응답 생성 중 세션 전환했다가 돌아올 때 캐시 사용
    gcTime: 1000 * 60 * 10, // 10 minutes - 캐시 유지 시간
  });
}

/**
 * Close a chat session
 */
export function useCloseSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, userId }: { sessionId: number; userId: number | null }) => {
      const { data } = await api.post(`/api/chatbot/sessions/${sessionId}/close`, {}, {
        headers: { 'X-User-Id': userId },
      });
      return data as ChatSession;
    },
    onMutate: async ({ sessionId, userId }) => {
      // Cancel ongoing queries
      await queryClient.cancelQueries({ queryKey: ['chat-sessions', userId] });
      await queryClient.cancelQueries({ queryKey: ['chat-active-session', userId] });

      // Optimistically update sessions list
      const previousSessions = queryClient.getQueryData(['chat-sessions', userId]) as ChatSession[] | undefined;
      if (previousSessions) {
        const updatedSessions = previousSessions.map((session) =>
          session.id === sessionId ? { ...session, status: 'closed' as const } : session
        );
        queryClient.setQueryData(['chat-sessions', userId], updatedSessions);
      }

      // Clear active session
      queryClient.setQueryData(['chat-active-session', userId], null);

      return { previousSessions };
    },
    onSuccess: (closedSession, { userId }) => {
      // Refetch to ensure data is synchronized
      queryClient.refetchQueries({ queryKey: ['chat-sessions', userId] });
      queryClient.refetchQueries({ queryKey: ['chat-active-session', userId] });
    },
    onError: (error, { userId }, context) => {
      // Revert on error
      if (context?.previousSessions) {
        queryClient.setQueryData(['chat-sessions', userId], context.previousSessions);
      }
    },
  });
}

/**
 * Delete a chat session
 */
export function useDeleteSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, userId }: { sessionId: number; userId: number | null }) => {
      await api.delete(`/api/chatbot/sessions/${sessionId}`, {
        headers: { 'X-User-Id': userId },
      });
    },
    onSuccess: (_, { userId, sessionId }) => {
      // Get current active session to check if it's being deleted
      const activeSession = queryClient.getQueryData(['chat-active-session', userId]) as ChatSession | null | undefined;

      // If the deleted session is the active one, clear it
      if (activeSession?.id === sessionId) {
        queryClient.setQueryData(['chat-active-session', userId], null);
      }

      // Invalidate and refetch sessions list and active session
      queryClient.invalidateQueries({ queryKey: ['chat-sessions', userId] });
      queryClient.invalidateQueries({ queryKey: ['chat-active-session', userId] });
      queryClient.refetchQueries({ queryKey: ['chat-sessions', userId] });
      queryClient.refetchQueries({ queryKey: ['chat-active-session', userId] });
    },
  });
}

/**
 * Send a message to the chatbot
 */
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      question,
      userId,
      sessionId,
      history,
      intent,
    }: {
      question: string;
      userId: number | null;
      sessionId: number;
      history?: Array<{ role: string; text: string }>;
      intent?: string;
    }) => {
      const { data } = await api.post('/api/chatbot/ask', {
        question,
        user_id: userId,
        session_id: sessionId,
        history: history || [],
        ...(intent ? { intent } : {}),
      }, {
        headers: { 'X-User-Id': userId },
      });
      return data as { answer: string; intent: string; escalated: boolean };
    },
    onMutate: async ({ question, userId, sessionId }) => {
      // Cancel ongoing queries to prevent race conditions
      await queryClient.cancelQueries({ queryKey: ['chat-session-messages', sessionId] });
      await queryClient.cancelQueries({ queryKey: ['chat-sessions', userId] });

      // Optimistically update messages cache with user message
      const previousMessages = queryClient.getQueryData(['chat-session-messages', sessionId]) as ChatSessionMessage[] | undefined;
      if (previousMessages) {
        const optimisticMessages = [
          ...previousMessages,
          { role: 'user' as const, text: question }
        ];
        queryClient.setQueryData(['chat-session-messages', sessionId], optimisticMessages);
      }

      // Optimistically update the sessions list with the new question
      const previousSessions = queryClient.getQueryData(['chat-sessions', userId]) as ChatSession[] | undefined;
      if (previousSessions) {
        const updatedSessions = previousSessions.map((session) =>
          session.id === sessionId
            ? { ...session, messagePreview: question, updatedAt: new Date().toISOString() }
            : session
        );
        queryClient.setQueryData(['chat-sessions', userId], updatedSessions);
      }

      return { previousMessages, previousSessions };
    },
    onSuccess: (data, { userId, sessionId }, context) => {
      // Update messages cache with bot response
      const currentMessages = queryClient.getQueryData(['chat-session-messages', sessionId]) as ChatSessionMessage[] | undefined;
      if (currentMessages) {
        queryClient.setQueryData(['chat-session-messages', sessionId], [
          ...currentMessages,
          {
            role: 'bot' as const,
            text: data.answer,
            intent: data.intent,
            escalated: data.escalated
          }
        ]);
      }

      // Refetch sessions list to update with the actual response
      queryClient.refetchQueries({ queryKey: ['chat-sessions', userId] });
    },
    onError: (error, { userId, sessionId }, context) => {
      // Revert to previous data on error
      if (context?.previousMessages) {
        queryClient.setQueryData(['chat-session-messages', sessionId], context.previousMessages);
      }
      if (context?.previousSessions) {
        queryClient.setQueryData(['chat-sessions', userId], context.previousSessions);
      }
    },
  });
}
