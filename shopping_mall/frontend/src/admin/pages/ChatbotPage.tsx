import { useState } from 'react';
import { useChatLogs, useEscalatedChatLogs } from '@/admin/hooks/useChatbot';
import ChatLogTable from '@/admin/components/chatbot/ChatLogTable';

const INTENTS = ['order_status', 'product_info', 'return_refund', 'complaint', 'general'];

export default function ChatbotPage() {
  const [tab, setTab] = useState<'all' | 'escalated'>('all');
  const [intentFilter, setIntentFilter] = useState<string>('');

  const { data: allLogs, isLoading: loadingAll } = useChatLogs(intentFilter || undefined);
  const { data: escalatedLogs, isLoading: loadingEsc } = useEscalatedChatLogs();

  const isLoading = tab === 'all' ? loadingAll : loadingEsc;
  const data = tab === 'all' ? allLogs : escalatedLogs;

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-bold text-gray-900">챗봇 관리</h2>

      <div className="flex items-center gap-4">
        <div className="flex gap-1 bg-gray-100 rounded p-1">
          <button
            onClick={() => setTab('all')}
            className={`px-4 py-1.5 text-sm rounded transition-colors ${
              tab === 'all' ? 'bg-white font-semibold shadow-sm' : 'text-gray-500'
            }`}
          >
            전체 로그
          </button>
          <button
            onClick={() => setTab('escalated')}
            className={`px-4 py-1.5 text-sm rounded transition-colors ${
              tab === 'escalated' ? 'bg-white font-semibold shadow-sm' : 'text-gray-500'
            }`}
          >
            에스컬레이션
          </button>
        </div>

        {tab === 'all' && (
          <select
            value={intentFilter}
            onChange={(e) => setIntentFilter(e.target.value)}
            className="border border-gray-300 rounded px-3 py-1.5 text-sm"
          >
            <option value="">전체 의도</option>
            {INTENTS.map((intent) => (
              <option key={intent} value={intent}>
                {intent}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400">로딩 중...</div>
        ) : (
          <ChatLogTable data={data ?? []} />
        )}
      </div>
    </div>
  );
}
