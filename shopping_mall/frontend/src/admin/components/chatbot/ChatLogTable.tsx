import DataTable from '@/admin/components/common/DataTable';
import { formatDate, truncate } from '@/lib/utils';
import type { ChatLog } from '@/admin/types/chatlog';

const intentColors: Record<string, string> = {
  order_status: 'bg-blue-100 text-blue-700',
  product_info: 'bg-green-100 text-green-700',
  return_refund: 'bg-orange-100 text-orange-700',
  complaint: 'bg-red-100 text-red-700',
  general: 'bg-gray-100 text-gray-700',
};

interface ChatLogTableProps {
  data: ChatLog[];
}

export default function ChatLogTable({ data }: ChatLogTableProps) {
  const columns = [
    {
      key: 'created_at',
      header: '시간',
      render: (row: ChatLog) => (
        <span className="text-gray-500 whitespace-nowrap">{formatDate(row.created_at)}</span>
      ),
    },
    {
      key: 'intent',
      header: '의도',
      render: (row: ChatLog) => (
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
            intentColors[row.intent] ?? 'bg-gray-100 text-gray-700'
          }`}
        >
          {row.intent}
        </span>
      ),
    },
    {
      key: 'question',
      header: '질문',
      render: (row: ChatLog) => <span>{truncate(row.question, 80)}</span>,
    },
    {
      key: 'answer',
      header: '답변',
      render: (row: ChatLog) => (
        <span className="text-gray-500">{truncate(row.answer, 100)}</span>
      ),
    },
    {
      key: 'escalated',
      header: '에스컬레이션',
      render: (row: ChatLog) =>
        row.escalated ? (
          <span className="text-red-600 font-semibold">Y</span>
        ) : (
          <span className="text-gray-400">N</span>
        ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={data}
      rowKey={(row) => row.id}
      rowClassName={(row) => (row.escalated ? 'bg-red-50' : '')}
    />
  );
}
