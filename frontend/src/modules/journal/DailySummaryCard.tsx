import { useState, useEffect } from "react";
import { MdChevronLeft, MdChevronRight, MdAutorenew } from "react-icons/md";
import type { DailySummaryAPI } from "@/types";

interface Props {
  fetchDailySummary: (date: string) => Promise<DailySummaryAPI | null>;
}

export default function DailySummaryCard({ fetchDailySummary }: Props) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [summary, setSummary] = useState<DailySummaryAPI | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchDailySummary(date).then((res) => {
      setSummary(res);
      setLoading(false);
    });
  }, [date, fetchDailySummary]);

  const moveDate = (days: number) => {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    setDate(d.toISOString().slice(0, 10));
  };

  const dateLabel = new Date(date).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="card bg-gradient-to-r from-green-50 to-emerald-50">
      {/* 날짜 네비게이션 */}
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={() => moveDate(-1)}
          className="p-1 text-gray-400 hover:text-gray-600 cursor-pointer"
        >
          <MdChevronLeft className="text-xl" />
        </button>
        <h3 className="text-sm font-semibold text-gray-700">
          {dateLabel} 영농보고서
        </h3>
        <button
          onClick={() => moveDate(1)}
          className="p-1 text-gray-400 hover:text-gray-600 cursor-pointer"
        >
          <MdChevronRight className="text-xl" />
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-4 text-gray-400">
          <MdAutorenew className="animate-spin mr-2" /> 요약 생성 중...
        </div>
      )}

      {!loading && summary && summary.entry_count > 0 && (
        <div className="space-y-3">
          {/* 통계 */}
          <div className="flex gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-primary">
                {summary.entry_count}
              </p>
              <p className="text-xs text-gray-500">작업 건수</p>
            </div>
            {summary.crops.length > 0 && (
              <div>
                <p className="text-2xl font-bold text-emerald-600">
                  {summary.crops.length}
                </p>
                <p className="text-xs text-gray-500">작목 수</p>
              </div>
            )}
            {summary.weather && (
              <div>
                <p className="text-2xl font-bold text-cyan-600">
                  {summary.weather}
                </p>
                <p className="text-xs text-gray-500">날씨</p>
              </div>
            )}
          </div>

          {/* 작업단계 배지 */}
          {summary.stages_worked.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {summary.stages_worked.map((stage) => (
                <span
                  key={stage}
                  className="badge bg-green-100 text-green-700 text-xs"
                >
                  {stage}
                </span>
              ))}
            </div>
          )}

          {/* LLM 요약문 */}
          <p className="text-sm text-gray-700 leading-relaxed">
            {summary.summary_text}
          </p>
        </div>
      )}

      {!loading && summary && summary.entry_count === 0 && (
        <p className="text-sm text-gray-400 text-center py-3">
          이 날짜에 기록된 영농일지가 없습니다.
        </p>
      )}

      {!loading && !summary && (
        <p className="text-sm text-gray-400 text-center py-3">
          요약을 불러올 수 없습니다.
        </p>
      )}
    </div>
  );
}
