import { useState, useRef, useEffect } from 'react';
import { useSessionMessages, useSendMessage, useCloseSession, useGetSession } from './useChatSession.ts';
import { INTENT_LABEL } from '@/admin/constants/chatbot';
import type { ChatSessionMessage } from './types.ts';

const QUICK_ACTIONS = [
  { label: '📦 배송 조회', intent: 'delivery', text: '배송 현황을 알고 싶어요' },
  { label: '🍎 재고 확인', intent: 'stock', text: '재고 확인해 주세요' },
  { label: '❄️ 보관 방법', intent: 'storage', text: '상품 보관 방법이 궁금해요' },
  { label: '↩️ 교환/환불', intent: 'exchange', text: '교환/환불하고 싶어요' },
  { label: '🌸 제철 상품', intent: 'season', text: '요즘 제철 상품이 뭔가요?' },
];

const WELCOME = {
  role: 'bot' as const,
  text: '안녕하세요! FarmOS 마켓 고객지원입니다.\n무엇이든 물어보세요 😊',
};

interface ChatMessageViewProps {
  sessionId: number;
  userId: number | null;
  onBackClick: () => void;
}

export default function ChatMessageView({ sessionId, userId, onBackClick }: ChatMessageViewProps) {
  const { data: sessionMessages = [] } = useSessionMessages(sessionId, userId);
  const { data: session } = useGetSession(sessionId, userId);
  const { mutate: send, isPending } = useSendMessage();
  const { mutate: closeSession, isPending: isClosing } = useCloseSession();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'bot'; text: string; intent?: string; escalated?: boolean }>>([WELCOME]);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const isClosed = session?.status === 'closed';

  const handleCloseSession = () => {
    closeSession(
      { sessionId, userId },
      {
        onSuccess: (closedSession) => {
          // 세션 종료 성공 후 목록으로 돌아가기
          setTimeout(() => {
            onBackClick();
          }, 0);
        },
        onError: (error) => {
          console.error('Failed to close session:', error);
          // 에러 발생 시에도 백으로 돌아가기 (나중에 목록에서 상태 확인)
          onBackClick();
        },
      }
    );
  };

  // Initialize messages from session (빈 경우 WELCOME 포함)
  // React Query 캐시에서 optimistic update를 하므로 sessionMessages를 그대로 사용
  useEffect(() => {
    setMessages(sessionMessages.length === 0 ? [WELCOME] : sessionMessages);
  }, [sessionMessages]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, [messages, isPending]);

  // Focus input when view opens
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = (question: string, intent?: string) => {
    if (!question.trim() || isPending) return;

    // Add user message optimistically
    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setInput('');

    send(
      {
        question,
        userId,
        sessionId,
        history: messages.slice(-4).map(({ role, text }) => ({ role, text })),
        intent,
      },
      {
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            { role: 'bot', text: data.answer, intent: data.intent, escalated: data.escalated },
          ]);
        },
        onError: () => {
          setMessages((prev) => [
            ...prev,
            { role: 'bot', text: '죄송합니다. 잠시 후 다시 시도해 주세요.' },
          ]);
        },
      }
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  return (
    <div className="flex flex-col h-full relative">
      {/* Header */}
      <div className="flex items-start justify-between px-4 py-4 bg-[#03C75A] text-white shrink-0 gap-3 sticky top-0 z-20">
        <div className="flex items-start gap-2">
          <button
            onClick={onBackClick}
            className="text-white/80 hover:text-white text-lg leading-none flex-shrink-0 mt-1"
            aria-label="뒤로가기"
          >
            ←
          </button>
          <span className="text-lg flex-shrink-0">🤖</span>
          <div className="min-w-0">
            <p className="text-sm font-semibold">FarmOS 고객지원</p>
            <p className="text-xs opacity-80">{isClosed ? '상담 종료' : 'AI 챗봇'}</p>
          </div>
        </div>
        {!isClosed && (
          <div className="flex items-start gap-2 flex-shrink-0 mt-1">
            <button
              onClick={handleCloseSession}
              disabled={isClosing}
              className="text-xs bg-white/40 hover:bg-white/50 disabled:opacity-50 px-2.5 py-1.5 rounded text-white font-medium transition-colors whitespace-nowrap"
              title="채팅 종료"
            >
              {isClosing ? '종료 중' : '종료'}
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {messages.map((msg, idx) => {
          // Generate stable key from timestamp or fallback to role+index combination
          const key = msg.createdAt ? `${msg.role}-${msg.createdAt}` : `${msg.role}-${idx}`;
          return (
          <div key={key} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[82%] ${msg.role === 'bot' ? 'space-y-1' : ''}`}>
              <div
                className={`px-3 py-2 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-[#03C75A] text-white rounded-br-sm'
                    : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                }`}
              >
                {msg.text}
              </div>
              {msg.role === 'bot' && msg.intent && (
                <div className="flex items-center gap-1.5 px-1">
                  <span className="text-xs text-gray-400">
                    [{INTENT_LABEL[msg.intent] ?? msg.intent}]
                  </span>
                  {msg.escalated && (
                    <span className="text-xs text-red-500 font-medium">상담원 연결 필요</span>
                  )}
                </div>
              )}
            </div>
          </div>
          );
        })}
        {isPending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-sm">
              <span className="flex gap-1 items-center h-4">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      {!isClosed && (
        <div className="px-3 py-2 border-t border-gray-100 flex gap-1.5 overflow-x-auto shrink-0 bg-white" style={{ scrollbarWidth: 'thin', scrollbarColor: '#d1d5db #f3f4f6' }}>
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.intent}
              onClick={() => handleSend(action.text, action.intent)}
              disabled={isPending}
              className="shrink-0 text-xs px-2.5 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:border-[#03C75A] hover:text-[#03C75A] transition-colors disabled:opacity-40"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-3 py-3 border-t border-gray-100 shrink-0 bg-white">
        {isClosed ? (
          <div className="flex items-center justify-center py-2 text-gray-500 text-sm">
            이 상담은 종료되었어요
          </div>
        ) : (
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="메시지를 입력하세요..."
              disabled={isPending}
              className="flex-1 text-sm border border-gray-200 rounded-full px-4 py-2 outline-none focus:border-[#03C75A] transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isPending}
              className="w-9 h-9 bg-[#03C75A] text-white rounded-full flex items-center justify-center shrink-0 hover:bg-[#02b050] transition-colors disabled:opacity-40 text-lg"
            >
              ↑
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
