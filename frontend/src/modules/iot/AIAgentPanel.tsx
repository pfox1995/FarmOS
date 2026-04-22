// Design Ref §5 — AI Agent 제어 패널.
// agent-action-history (module-4) 통합:
//  - 상단에 AIActivitySummaryCards 삽입
//  - 최근 판단 row click → AIDecisionDetailModal
//  - 기존 "전체 N건 보기" 인라인 펼침 → "더보기(cursor pagination)" 버튼

import { useEffect, useState } from 'react';
import {
  MdSmartToy,
  MdAir,
  MdWaterDrop,
  MdLightMode,
  MdShield,
  MdSettings,
  MdHistory,
  MdAutoAwesome,
  MdExpandMore,
} from 'react-icons/md';
import type { AIDecision } from '@/types';
import CropProfileModal from './CropProfileModal';
import AIActivitySummaryCards from './AIActivitySummaryCards';
import AIDecisionDetailModal from './AIDecisionDetailModal';
import { useAIAgent } from '@/hooks/useAIAgent';
import DateRangeFilter, {
  type DateRangeValue,
} from '@/components/DateRangeFilter';

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    emergency: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    medium: 'bg-blue-100 text-blue-700',
    low: 'bg-gray-100 text-gray-600',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[priority] || colors.low}`}>
      {priority}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    rule: 'bg-yellow-100 text-yellow-700',
    llm: 'bg-purple-100 text-purple-700',
    tool: 'bg-indigo-100 text-indigo-700',
    manual: 'bg-green-100 text-green-700',
  };
  const labels: Record<string, string> = {
    rule: '규칙',
    llm: 'AI',
    tool: 'AI Tool',
    manual: '수동',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[source] || 'bg-gray-100 text-gray-600'}`}>
      {labels[source] || source}
    </span>
  );
}

function ControlCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl border p-4 space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <span className="font-semibold text-gray-800 text-sm">{title}</span>
        <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200 font-medium">
          가상 제어
        </span>
      </div>
      <div className="text-sm text-gray-600">{children}</div>
    </div>
  );
}

// Design Ref §5.3 — row 전체 클릭 시 모달. 인라인 tool_calls 펼침은 제거됨.
function DecisionRow({
  decision,
  onOpen,
}: {
  decision: AIDecision;
  onOpen: (id: string) => void;
}) {
  // 년-월-일 시:분 (24h). ko-KR locale 의 기본 포맷("2026. 04. 22. 14:30") 대신
  // 공백/구분자를 가지런히 직접 포맷.
  const d = new Date(decision.timestamp);
  const pad = (n: number) => String(n).padStart(2, '0');
  const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  const typeLabels: Record<string, string> = {
    ventilation: '환기',
    irrigation: '관수',
    lighting: '조명',
    shading: '차광/보온',
  };
  const toolCount = decision.tool_calls?.length ?? 0;

  return (
    <button
      type="button"
      data-testid="ai-decision-row"
      onClick={() => onOpen(decision.id)}
      className="w-full text-left py-2.5 border-b border-gray-100 last:border-0 hover:bg-white/60 rounded px-1 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-[88px] mt-0.5 leading-tight">
          <div className="text-[11px] text-gray-500 font-mono">{dateStr}</div>
          <div className="text-[11px] text-gray-400 font-mono">{timeStr}</div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-800">
              {typeLabels[decision.control_type] || decision.control_type}
            </span>
            <PriorityBadge priority={decision.priority} />
            <SourceBadge source={decision.source} />
            {toolCount > 0 && (
              <span className="text-[10px] text-indigo-500">· 도구 {toolCount}</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-1 leading-relaxed line-clamp-2">
            {decision.reason}
          </p>
        </div>
      </div>
    </button>
  );
}

export default function AIAgentPanel() {
  const {
    status,
    decisions,
    loading,
    toggle,
    updateCropProfile,
    // agent-action-history
    summary,
    summaryRange,
    summaryLoading,
    fetchSummary,
    hasMore,
    listLoading,
    fetchMore,
    fetchDetail,
    setDateRange,
  } = useAIAgent();

  const [profileOpen, setProfileOpen] = useState(false);

  // 최근 판단 날짜 범위 필터 상태 — 기본값: 전체(필터 없음)
  const [decisionRange, setDecisionRange] = useState<DateRangeValue>({
    since: null,
    until: null,
    preset: 'all',
  });
  const handleRangeChange = (v: DateRangeValue) => {
    setDecisionRange(v);
    setDateRange(v.since, v.until);
  };

  // 상세 모달 상태
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailDecision, setDetailDecision] = useState<AIDecision | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const openDetail = async (id: string) => {
    const cached = decisions.find((d) => d.id === id) ?? null;
    setDetailDecision(cached);
    setDetailError(null);
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      const fresh = await fetchDetail(id);
      if (fresh) {
        setDetailDecision(fresh);
      } else if (!cached) {
        setDetailError('해당 판단을 찾을 수 없습니다 (삭제되었거나 30일이 지났을 수 있습니다).');
      }
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetailOpen(false);
    // 약간의 애니메이션 여유 후 초기화
    setTimeout(() => {
      setDetailDecision(null);
      setDetailError(null);
    }, 150);
  };

  // 탭 변경 시 해당 range summary 재조회
  useEffect(() => {
    // 초기 today 는 훅에서 자동 로드. 탭 변경은 onRangeChange 에서만 트리거.
  }, []);

  if (loading) {
    return (
      <div className="card animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-48 mb-4" />
        <div className="h-32 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!status) {
    return (
      <div className="card">
        <div className="flex items-center gap-2 text-gray-400">
          <MdSmartToy className="text-2xl" />
          <h3 className="font-semibold">AI Agent 제어</h3>
          <span className="ml-auto text-xs">IoT 서버 연결 대기중...</span>
        </div>
      </div>
    );
  }

  const { control_state: cs, crop_profile } = status;

  return (
    <>
      <div className="card space-y-5" data-testid="ai-agent-panel">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MdSmartToy className="text-2xl text-purple-600" />
            <h3 className="section-title !mb-0">AI Agent 제어</h3>
            {status.enabled && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setProfileOpen(true)}
              className="p-2 hover:bg-gray-100 rounded-lg text-gray-500"
              title="작물 프로필 설정"
            >
              <MdSettings className="text-lg" />
            </button>
            <button
              onClick={toggle}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                status.enabled
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {status.enabled ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        {/* Crop Info */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <MdAutoAwesome className="text-green-500" />
          <span>
            {crop_profile.name} / {crop_profile.growth_stage} / 적정 {crop_profile.optimal_temp[0]}~{crop_profile.optimal_temp[1]}C
          </span>
        </div>

        {/* agent-action-history — 요약 카드 */}
        <AIActivitySummaryCards
          summary={summary}
          range={summaryRange}
          loading={summaryLoading}
          onRangeChange={(r) => fetchSummary(r)}
        />

        {/* 4대 제어 카드 */}
        {status.enabled ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <ControlCard
              icon={<MdAir className="text-xl text-blue-500" />}
              title="환기"
            >
              <div className="flex justify-between">
                <span>창문 개방</span>
                <span className="font-semibold text-gray-800">{cs.ventilation.window_open_pct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${cs.ventilation.window_open_pct}%` }} />
              </div>
              <div className="flex justify-between mt-1.5">
                <span>팬 속도</span>
                <span className="font-semibold text-gray-800">{cs.ventilation.fan_speed} RPM</span>
              </div>
            </ControlCard>

            <ControlCard
              icon={<MdWaterDrop className="text-xl text-cyan-500" />}
              title="관수/양액"
            >
              <div className="flex justify-between">
                <span>밸브</span>
                <span className={`font-semibold ${cs.irrigation.valve_open ? 'text-cyan-600' : 'text-gray-400'}`}>
                  {cs.irrigation.valve_open ? '열림' : '닫힘'}
                </span>
              </div>
              <div className="flex justify-between mt-1">
                <span>금일 급수량</span>
                <span className="font-semibold text-gray-800">{cs.irrigation.daily_total_L.toFixed(1)}L</span>
              </div>
              <div className="flex justify-between mt-1">
                <span>N:P:K</span>
                <span className="font-semibold text-gray-800">
                  {cs.irrigation.nutrient.N}:{cs.irrigation.nutrient.P}:{cs.irrigation.nutrient.K}
                </span>
              </div>
            </ControlCard>

            <ControlCard
              icon={<MdLightMode className="text-xl text-amber-500" />}
              title="조명"
            >
              <div className="flex justify-between">
                <span>상태</span>
                <span className={`font-semibold ${cs.lighting.on ? 'text-amber-600' : 'text-gray-400'}`}>
                  {cs.lighting.on ? 'ON' : 'OFF'}
                </span>
              </div>
              <div className="flex justify-between mt-1">
                <span>밝기</span>
                <span className="font-semibold text-gray-800">{cs.lighting.brightness_pct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div className="bg-amber-400 h-1.5 rounded-full transition-all" style={{ width: `${cs.lighting.brightness_pct}%` }} />
              </div>
            </ControlCard>

            <ControlCard
              icon={<MdShield className="text-xl text-emerald-500" />}
              title="차광/보온"
            >
              <div className="flex justify-between">
                <span>차광막</span>
                <span className="font-semibold text-gray-800">{cs.shading.shade_pct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div className="bg-emerald-400 h-1.5 rounded-full transition-all" style={{ width: `${cs.shading.shade_pct}%` }} />
              </div>
              <div className="flex justify-between mt-1.5">
                <span>보온커튼</span>
                <span className="font-semibold text-gray-800">{cs.shading.insulation_pct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div className="bg-orange-400 h-1.5 rounded-full transition-all" style={{ width: `${cs.shading.insulation_pct}%` }} />
              </div>
            </ControlCard>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <MdSmartToy className="text-4xl mx-auto mb-2 opacity-30" />
            <p className="text-sm">AI Agent가 비활성 상태입니다</p>
            <p className="text-xs mt-1">ON 버튼을 눌러 활성화하세요</p>
          </div>
        )}

        {/* 최근 판단 — 상세 모달 + 더보기. AI Agent 활성 여부와 무관하게 상시 표시. */}
        <div>
          <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
            <div className="flex items-center gap-2">
              <MdHistory className="text-gray-400" />
              <span className="text-sm font-semibold text-gray-700">최근 판단</span>
              <span className="text-xs text-gray-400">
                (표시 {decisions.length}건)
              </span>
            </div>
            <DateRangeFilter value={decisionRange} onChange={handleRangeChange} />
          </div>
          <div className="bg-gray-50 rounded-xl p-2 max-h-96 overflow-y-auto">
            {decisions.length === 0 ? (
              <p className="py-6 text-xs text-gray-400 text-center">
                아직 기록된 판단 내역이 없습니다.
              </p>
            ) : (
              <>
                {decisions.map((d) => (
                  <DecisionRow key={d.id} decision={d} onOpen={openDetail} />
                ))}
                {hasMore && (
                  <div className="pt-2 pb-1 flex justify-center">
                    <button
                      data-testid="ai-more-btn"
                      onClick={() => fetchMore()}
                      disabled={listLoading}
                      className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 disabled:text-gray-400"
                    >
                      <MdExpandMore className="text-base" />
                      {listLoading ? '불러오는 중…' : '더보기'}
                    </button>
                  </div>
                )}
                {!hasMore && decisions.length > 5 && (
                  <p className="pt-2 pb-1 text-[11px] text-gray-400 text-center">
                    모든 이력을 불러왔습니다
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* 작물 프로필 모달 */}
      <CropProfileModal
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        current={crop_profile}
        onSave={updateCropProfile}
      />

      {/* 판단 상세 모달 */}
      <AIDecisionDetailModal
        open={detailOpen}
        decision={detailDecision}
        loading={detailLoading}
        error={detailError}
        onClose={closeDetail}
      />
    </>
  );
}
