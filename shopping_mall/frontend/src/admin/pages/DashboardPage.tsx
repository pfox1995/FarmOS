import { useDashboard, useEscalatedLogs } from '@/admin/hooks/useDashboard';
import StatCard from '@/admin/components/dashboard/StatCard';
import RevenueChart from '@/admin/components/dashboard/RevenueChart';
import SegmentPie from '@/admin/components/dashboard/SegmentPie';
import { formatPrice, formatDate, truncate } from '@/lib/utils';

export default function DashboardPage() {
  const { data: dashboard, isLoading, isError } = useDashboard();
  const { data: escalated } = useEscalatedLogs();

  if (isLoading) {
    return <div className="p-6 text-gray-400">로딩 중...</div>;
  }

  if (isError || !dashboard) {
    return <div className="p-6 text-red-500">대시보드 데이터를 불러올 수 없습니다.</div>;
  }

  const escalatedList = Array.isArray(escalated) ? escalated : [];

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-xl font-bold text-gray-900">대시보드</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="오늘 매출"
          value={formatPrice(dashboard.today_revenue)}
          change={dashboard.revenue_change}
          icon="💵"
        />
        <StatCard
          title="주문수"
          value={`${dashboard.today_orders}건`}
          change={dashboard.orders_change}
          icon="📦"
        />
        <StatCard
          title="신규고객"
          value={`${dashboard.new_customers}명`}
          change={dashboard.customers_change}
          icon="👤"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RevenueChart data={dashboard.weekly_revenue ?? []} />
        <SegmentPie data={dashboard.segments ?? []} />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">
          미처리 에스컬레이션
          {escalatedList.length > 0 && (
            <span className="ml-2 text-red-500">({escalatedList.length}건)</span>
          )}
        </h3>
        {escalatedList.length > 0 ? (
          <div className="space-y-2">
            {escalatedList.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-3 p-3 bg-red-50 rounded border border-red-100"
              >
                <span className="text-xs text-gray-400 whitespace-nowrap mt-0.5">
                  {formatDate(log.created_at)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{truncate(log.question, 100)}</p>
                  <p className="text-xs text-gray-500 mt-1">{truncate(log.answer, 120)}</p>
                </div>
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full whitespace-nowrap">
                  {log.intent}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-sm">미처리 에스컬레이션이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
