import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#03C75A', '#0088FE', '#FFBB28', '#FF8042', '#A855F7', '#EF4444'];

const SEGMENT_LABELS: Record<string, string> = {
  vip: 'VIP',
  loyal: '충성',
  repeat: '재구매',
  new: '신규',
  at_risk: '이탈위험',
  dormant: '휴면',
};

interface SegmentPieProps {
  data: { name: string; count: number }[];
}

export default function SegmentPie({ data }: SegmentPieProps) {
  const chartData = data.map((d) => ({
    name: SEGMENT_LABELS[d.name] ?? d.name,
    value: d.count,
  }));

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">고객 세그먼트</h3>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="45%"
            outerRadius={90}
            dataKey="value"
            label={({ name, percent }: { name?: string; percent?: number }) => `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}
          >
            {chartData.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => [`${value}명`, '고객수']} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
