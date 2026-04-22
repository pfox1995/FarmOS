// Design Ref §5.3 — 오늘/7일/30일 집계 카드.
// Plan SC-2 커버: 제어 타입/소스/우선순위 분포와 평균 duration.

import { MdBarChart, MdCategory, MdBolt } from 'react-icons/md';
import type { ActivitySummary } from '@/types';

interface Props {
  summary: ActivitySummary | null;
  range: ActivitySummary['range'];
  loading: boolean;
  onRangeChange: (range: ActivitySummary['range']) => void;
}

const RANGE_LABELS: Record<ActivitySummary['range'], string> = {
  today: '오늘',
  '7d': '7일',
  '30d': '30일',
};

const CT_LABELS: Record<string, string> = {
  ventilation: '환기',
  irrigation: '관수',
  lighting: '조명',
  shading: '차광/보온',
};

const SRC_LABELS: Record<string, string> = {
  rule: '규칙',
  llm: 'AI',
  tool: 'AI Tool',
  manual: '수동',
};

function topEntry(obj: Record<string, number> | undefined): [string, number] | null {
  if (!obj) return null;
  const entries = Object.entries(obj);
  if (entries.length === 0) return null;
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0];
}

function Card({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-white rounded-xl border p-3 flex flex-col gap-0.5">
      <div className="flex items-center gap-1.5 text-xs text-gray-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-lg font-bold text-gray-800 mt-0.5 leading-tight">{value}</div>
      {sub && <div className="text-[11px] text-gray-400 truncate">{sub}</div>}
    </div>
  );
}

export default function AIActivitySummaryCards({
  summary,
  range,
  loading,
  onRangeChange,
}: Props) {
  const topCt = topEntry(summary?.by_control_type);
  const topSrc = topEntry(summary?.by_source);

  return (
    <div className="space-y-2">
      {/* 탭 */}
      <div
        className="inline-flex rounded-lg bg-gray-100 p-0.5"
        role="tablist"
        aria-label="집계 기간 선택"
      >
        {(Object.keys(RANGE_LABELS) as ActivitySummary['range'][]).map((r) => {
          const active = range === r;
          return (
            <button
              key={r}
              role="tab"
              aria-selected={active}
              onClick={() => onRangeChange(r)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                active ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {RANGE_LABELS[r]}
            </button>
          );
        })}
      </div>

      {/* 카드 3개 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <Card
          icon={<MdBarChart className="text-indigo-500" />}
          label="총 판단"
          value={
            loading && !summary
              ? '…'
              : `${summary?.total ?? 0}건`
          }
          sub={
            summary?.latest_at
              ? `최근 ${new Date(summary.latest_at).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}`
              : undefined
          }
        />
        <Card
          icon={<MdCategory className="text-blue-500" />}
          label="최다 제어"
          value={topCt ? `${CT_LABELS[topCt[0]] ?? topCt[0]}` : '-'}
          sub={topCt ? `${topCt[1]}건` : undefined}
        />
        <Card
          icon={<MdBolt className="text-amber-500" />}
          label="최다 소스"
          value={topSrc ? `${SRC_LABELS[topSrc[0]] ?? topSrc[0]}` : '-'}
          sub={topSrc ? `${topSrc[1]}건` : undefined}
        />
      </div>
    </div>
  );
}
