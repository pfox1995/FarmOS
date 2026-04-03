interface StatCardProps {
  title: string;
  value: string;
  change: number;
  icon: string;
}

export default function StatCard({ title, value, change, icon }: StatCardProps) {
  const safeChange = change ?? 0;
  const isPositive = safeChange >= 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 flex items-start gap-4">
      <div className="w-12 h-12 rounded-lg bg-[#03C75A]/10 flex items-center justify-center text-2xl">
        {icon}
      </div>
      <div className="flex-1">
        <p className="text-sm text-gray-500 mb-1">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className={`text-sm mt-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
          {isPositive ? '+' : ''}{safeChange.toFixed(1)}% 전일 대비
        </p>
      </div>
    </div>
  );
}
