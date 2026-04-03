import { useState } from 'react';
import {
  useSegmentSummary,
  useSegmentCustomers,
  usePopularItems,
  useRefreshSegments,
} from '@/admin/hooks/useAnalytics';
import { formatPrice } from '@/lib/utils';
import DataTable from '@/admin/components/common/DataTable';
import type { CustomerSegment } from '@/admin/types/segment';

const SEGMENT_CONFIG: Record<string, { label: string; color: string }> = {
  vip: { label: 'VIP', color: 'bg-yellow-100 text-yellow-800 border-yellow-300' },
  loyal: { label: '충성', color: 'bg-green-100 text-green-800 border-green-300' },
  repeat: { label: '재구매', color: 'bg-blue-100 text-blue-800 border-blue-300' },
  new: { label: '신규', color: 'bg-purple-100 text-purple-800 border-purple-300' },
  at_risk: { label: '이탈위험', color: 'bg-orange-100 text-orange-800 border-orange-300' },
  dormant: { label: '휴면', color: 'bg-gray-100 text-gray-800 border-gray-300' },
};

export default function AnalyticsPage() {
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);
  const { data: summaries, isLoading } = useSegmentSummary();
  const { data: customers, isLoading: loadingCustomers } = useSegmentCustomers(selectedSegment);
  const { data: popularItems } = usePopularItems();
  const refreshMutation = useRefreshSegments();

  const customerColumns = [
    {
      key: 'name',
      header: '이름',
      render: (row: CustomerSegment) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: 'email',
      header: '이메일',
      render: (row: CustomerSegment) => <span className="text-gray-500">{row.email}</span>,
    },
    {
      key: 'total_spent',
      header: '총 구매액',
      render: (row: CustomerSegment) => formatPrice(row.total_spent),
    },
    {
      key: 'order_count',
      header: '주문수',
      render: (row: CustomerSegment) => `${row.order_count}건`,
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">분석</h2>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="bg-[#03C75A] text-white px-4 py-2 rounded text-sm font-medium hover:bg-[#02b050] disabled:opacity-50 transition-colors"
        >
          {refreshMutation.isPending ? '갱신 중...' : '세그먼트 갱신'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {isLoading ? (
          <div className="col-span-6 text-center text-gray-400 py-8">로딩 중...</div>
        ) : (
          (summaries ?? []).map((s) => {
            const config = SEGMENT_CONFIG[s.segment] ?? {
              label: s.segment,
              color: 'bg-gray-100 text-gray-800 border-gray-300',
            };
            return (
              <button
                key={s.segment}
                onClick={() =>
                  setSelectedSegment(selectedSegment === s.segment ? null : s.segment)
                }
                className={`border rounded-lg p-4 text-center transition-all ${config.color} ${
                  selectedSegment === s.segment ? 'ring-2 ring-[#03C75A] scale-105' : ''
                }`}
              >
                <p className="text-2xl font-bold">{s.count}</p>
                <p className="text-sm font-medium mt-1">{config.label}</p>
              </button>
            );
          })
        )}
      </div>

      {selectedSegment && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-600">
              {SEGMENT_CONFIG[selectedSegment]?.label ?? selectedSegment} 고객 목록
            </h3>
          </div>
          {loadingCustomers ? (
            <div className="p-8 text-center text-gray-400">로딩 중...</div>
          ) : (
            <DataTable
              columns={customerColumns}
              data={customers ?? []}
              rowKey={(row) => row.user_id}
            />
          )}
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-600">인기 상품</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left">
                <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">순위</th>
                <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">상품명</th>
                <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">판매수</th>
                <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">매출</th>
              </tr>
            </thead>
            <tbody>
              {(popularItems ?? []).map((item, i) => (
                <tr key={item.product_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{i + 1}</td>
                  <td className="px-4 py-3">{item.name}</td>
                  <td className="px-4 py-3">{item.total_sold}개</td>
                  <td className="px-4 py-3">{formatPrice(item.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(popularItems ?? []).length === 0 && (
            <div className="text-center py-8 text-gray-400">데이터가 없습니다.</div>
          )}
        </div>
      </div>
    </div>
  );
}
