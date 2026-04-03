import { useState, type FormEvent } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useExpenses, useCreateExpense, useClassifyExpenses } from '@/admin/hooks/useExpenses';
import { formatPrice, formatDate } from '@/lib/utils';

export default function ExpensesPage() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [formData, setFormData] = useState({
    date: '',
    description: '',
    amount: '',
    category: '',
  });

  const { data: expenses, isLoading } = useExpenses(
    startDate || undefined,
    endDate || undefined
  );
  const createMutation = useCreateExpense();
  const classifyMutation = useClassifyExpenses();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      {
        date: formData.date,
        description: formData.description,
        amount: Number(formData.amount),
        category: formData.category || undefined,
      },
      {
        onSuccess: () => {
          setFormData({ date: '', description: '', amount: '', category: '' });
        },
      }
    );
  };

  const categorySummary = (expenses ?? []).reduce<Record<string, number>>((acc, e) => {
    const cat = e.category ?? '미분류';
    acc[cat] = (acc[cat] ?? 0) + e.amount;
    return acc;
  }, {});

  const chartData = Object.entries(categorySummary).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-xl font-bold text-gray-900">비용 관리</h2>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">비용 등록</h3>
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">날짜</label>
            <input
              type="date"
              value={formData.date}
              onChange={(e) => setFormData((f) => ({ ...f, date: e.target.value }))}
              className="border border-gray-300 rounded px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">설명</label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData((f) => ({ ...f, description: e.target.value }))}
              className="border border-gray-300 rounded px-3 py-2 text-sm w-48"
              placeholder="비용 내역"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">금액</label>
            <input
              type="number"
              value={formData.amount}
              onChange={(e) => setFormData((f) => ({ ...f, amount: e.target.value }))}
              className="border border-gray-300 rounded px-3 py-2 text-sm w-32"
              placeholder="금액"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">카테고리 (선택)</label>
            <input
              type="text"
              value={formData.category}
              onChange={(e) => setFormData((f) => ({ ...f, category: e.target.value }))}
              className="border border-gray-300 rounded px-3 py-2 text-sm w-32"
              placeholder="카테고리"
            />
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-[#03C75A] text-white px-5 py-2 rounded text-sm font-medium hover:bg-[#02b050] disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending ? '등록 중...' : '등록'}
          </button>
        </div>
      </form>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">기간:</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          />
          <span className="text-gray-400">~</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={() => classifyMutation.mutate()}
          disabled={classifyMutation.isPending}
          className="bg-purple-600 text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-purple-700 disabled:opacity-50 transition-colors"
        >
          {classifyMutation.isPending ? '분류 중...' : 'AI 자동 분류'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h3 className="text-sm font-semibold text-gray-600">비용 목록</h3>
          </div>
          {isLoading ? (
            <div className="p-8 text-center text-gray-400">로딩 중...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left">
                    <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">날짜</th>
                    <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">설명</th>
                    <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">금액</th>
                    <th className="px-4 py-3 font-semibold text-gray-600 bg-gray-50">카테고리</th>
                  </tr>
                </thead>
                <tbody>
                  {(expenses ?? []).map((exp) => (
                    <tr key={exp.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        {formatDate(exp.date, 'yyyy-MM-dd')}
                      </td>
                      <td className="px-4 py-3">{exp.description}</td>
                      <td className="px-4 py-3 font-medium">{formatPrice(exp.amount)}</td>
                      <td className="px-4 py-3">
                        {exp.category ? (
                          <span className="inline-flex items-center gap-1">
                            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-xs font-medium">
                              {exp.category}
                            </span>
                            {exp.auto_classified && (
                              <span className="text-xs text-purple-500" title="AI 자동분류">
                                AI
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-xs">미분류</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(expenses ?? []).length === 0 && (
                <div className="text-center py-8 text-gray-400">데이터가 없습니다.</div>
              )}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">카테고리별 총액</h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v: number) => `${(v / 10000).toFixed(0)}만`}
                />
                <Tooltip formatter={(value) => [formatPrice(Number(value)), '총액']} />
                <Bar dataKey="value" fill="#03C75A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-16 text-gray-400">데이터가 없습니다.</div>
          )}
        </div>
      </div>
    </div>
  );
}
