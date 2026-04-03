import { useState } from 'react';
import Markdown from 'react-markdown';
import { useWeeklyReports, useWeeklyReportDetail, useGenerateReport } from '@/admin/hooks/useReports';
import { formatPrice, formatDate } from '@/lib/utils';

export default function ReportsPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: reports, isLoading } = useWeeklyReports();
  const { data: detail, isLoading: loadingDetail } = useWeeklyReportDetail(selectedId);
  const generateMutation = useGenerateReport();

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">리포트</h2>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          className="bg-[#03C75A] text-white px-4 py-2 rounded text-sm font-medium hover:bg-[#02b050] disabled:opacity-50 transition-colors"
        >
          {generateMutation.isPending ? '생성 중...' : '리포트 생성'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-600">주간 리포트 목록</h3>
          </div>
          {isLoading ? (
            <div className="p-4 text-gray-400 text-sm">로딩 중...</div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
              {(reports ?? []).map((report) => (
                <button
                  key={report.id}
                  onClick={() => setSelectedId(report.id)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                    selectedId === report.id ? 'bg-green-50 border-l-4 border-[#03C75A]' : ''
                  }`}
                >
                  <p className="text-sm font-medium text-gray-800">
                    {report.week_start} ~ {report.week_end}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    순이익: {formatPrice(report.net_profit)}
                  </p>
                </button>
              ))}
              {(reports ?? []).length === 0 && (
                <div className="p-4 text-gray-400 text-sm text-center">리포트가 없습니다.</div>
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 p-6">
          {selectedId === null ? (
            <div className="text-center text-gray-400 py-16">
              좌측에서 리포트를 선택하세요.
            </div>
          ) : loadingDetail ? (
            <div className="text-center text-gray-400 py-16">로딩 중...</div>
          ) : detail?.content ? (
            <div className="prose prose-sm max-w-none">
              <Markdown>{detail.content}</Markdown>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-16">
              <p>기간: {detail?.week_start} ~ {detail?.week_end}</p>
              <p className="mt-2">순이익: {detail ? formatPrice(detail.net_profit) : '-'}</p>
              <p className="mt-1 text-xs">생성일: {detail ? formatDate(detail.created_at) : '-'}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
