// Design Ref §5.4 — 판단 상세 모달 (사용자 친화 간소화 버전).
// 사용자 관점에서 한눈에 이해 가능한 "AI 판단 결과 / 적용된 제어 / 당시 센서값" 3개 섹션으로 구성.
// JSON·턴별 trace 등 디버그성 정보는 제외.

import { useEffect, useRef, useState } from 'react';
import { MdClose, MdContentCopy, MdCheck, MdWarningAmber } from 'react-icons/md';
import type { AIDecision, ReasoningTurn, ToolCallTrace } from '@/types';

interface Props {
  open: boolean;
  decision: AIDecision | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
}

const CT_LABELS: Record<string, string> = {
  ventilation: '환기',
  irrigation: '관수',
  lighting: '조명',
  shading: '차광/보온',
};

const PR_LABELS: Record<string, { label: string; cls: string }> = {
  emergency: { label: '긴급', cls: 'bg-red-100 text-red-700' },
  high: { label: '높음', cls: 'bg-orange-100 text-orange-700' },
  medium: { label: '중간', cls: 'bg-blue-100 text-blue-700' },
  low: { label: '낮음', cls: 'bg-gray-100 text-gray-600' },
};

const SRC_LABELS: Record<string, { label: string; cls: string }> = {
  rule: { label: '규칙', cls: 'bg-yellow-100 text-yellow-700' },
  llm: { label: 'AI', cls: 'bg-purple-100 text-purple-700' },
  tool: { label: 'AI Tool', cls: 'bg-indigo-100 text-indigo-700' },
  manual: { label: '수동', cls: 'bg-green-100 text-green-700' },
};

function isReasoningTurn(
  entry: ToolCallTrace | ReasoningTurn,
): entry is ReasoningTurn {
  return typeof (entry as ReasoningTurn).turn === 'number';
}

// LLM 출력 텍스트에 등장하는 MCP tool 이름을 한국어 도메인 용어로 치환.
// 사용자 관점에서 "control_irrigation 호출" → "관수/양액 수행" 처럼 읽히도록.
const TOOL_LABEL_MAP: Record<string, string> = {
  control_ventilation: '환기',
  control_irrigation: '관수/양액',
  control_lighting: '조명',
  control_shading: '차광/보온',
  read_sensors: '센서 조회',
  read_weather: '기상 조회',
  read_crop_profile: '작물 정보 조회',
  read_control_state: '제어 상태 조회',
};

function humanizeToolNames(text: string): string {
  if (!text) return text;
  let out = text;
  for (const [tool, label] of Object.entries(TOOL_LABEL_MAP)) {
    // `tool` 이름은 전체 일치로만 치환. 백틱/따옴표 감싸진 경우도 함께 제거.
    const patterns = [
      new RegExp('`' + tool + '`', 'g'),
      new RegExp('"' + tool + '"', 'g'),
      new RegExp("'" + tool + "'", 'g'),
      new RegExp('\\b' + tool + '\\b', 'g'),
    ];
    for (const p of patterns) out = out.replace(p, label);
  }
  return out;
}

// LLM decision 에서 "최종 결론 텍스트" 하나를 골라낸다.
// 우선순위: Part B 강제 종합 요약 > 마지막 turn 의 reasoning > decision.reason fallback
function getFinalConclusion(decision: AIDecision): string {
  const entries = decision.tool_calls ?? [];
  const turns = entries.filter(isReasoningTurn);

  const summary = turns.find((t) => t.is_summary && t.reasoning);
  if (summary) return summary.reasoning;

  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].reasoning) return turns[i].reasoning;
  }
  return decision.reason || '내용 없음';
}

// decision.action 을 control_type 에 맞는 사람이 읽기 쉬운 라벨-값 쌍으로 변환.
function formatAction(
  controlType: string,
  action: Record<string, unknown>,
): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  const get = <T,>(k: string) => action[k] as T | undefined;

  if (controlType === 'ventilation') {
    const w = get<number>('window_open_pct');
    const f = get<number>('fan_speed');
    if (w != null) rows.push({ label: '창문 개방', value: `${w}%` });
    if (f != null) rows.push({ label: '환기팬', value: `${f} RPM` });
  } else if (controlType === 'irrigation') {
    const valve = get<boolean>('valve_open');
    const water = get<number>('water_amount_L');
    const nut = get<{ N?: number; P?: number; K?: number }>('nutrient');
    if (valve != null) rows.push({ label: '밸브', value: valve ? '열림' : '닫힘' });
    if (water != null && water > 0) rows.push({ label: '관수량', value: `${water} L` });
    if (nut && (nut.N != null || nut.P != null || nut.K != null)) {
      rows.push({
        label: '양액 비율',
        value: `N ${nut.N ?? '-'} / P ${nut.P ?? '-'} / K ${nut.K ?? '-'}`,
      });
    }
  } else if (controlType === 'lighting') {
    const on = get<boolean>('on');
    const b = get<number>('brightness_pct');
    if (on != null) rows.push({ label: '보광등', value: on ? `ON (${b ?? 0}%)` : 'OFF' });
  } else if (controlType === 'shading') {
    const sh = get<number>('shade_pct');
    const ins = get<number>('insulation_pct');
    if (sh != null) rows.push({ label: '차광막', value: `${sh}%` });
    if (ins != null) rows.push({ label: '보온커튼', value: `${ins}%` });
  }
  return rows;
}

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // 무시 (일부 브라우저는 https 요구)
    }
  };
  return (
    <button
      onClick={onCopy}
      className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-indigo-600 transition-colors"
      aria-label={label ?? 'Copy'}
    >
      {copied ? <MdCheck className="text-green-500" /> : <MdContentCopy />}
      {copied ? '복사됨' : '복사'}
    </button>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-gray-100 pt-3 mt-3 first:border-0 first:pt-0 first:mt-0">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
        {title}
      </h4>
      {children}
    </div>
  );
}

export default function AIDecisionDetailModal({
  open,
  decision,
  loading,
  error,
  onClose,
}: Props) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    setTimeout(() => closeBtnRef.current?.focus(), 10);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const time = decision?.timestamp
    ? new Date(decision.timestamp).toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '';

  const priority = decision ? PR_LABELS[decision.priority] : null;
  const source = decision ? SRC_LABELS[decision.source] : null;
  const snapshot = decision?.sensor_snapshot;
  const actionRows = decision
    ? formatAction(decision.control_type, decision.action ?? {})
    : [];

  // LLM 기반 결정은 통합 요약을, 규칙/수동 결정은 decision.reason 을 보여준다.
  const isLlmOrigin =
    decision && (decision.source === 'tool' || decision.source === 'llm');
  const conclusionTitle = isLlmOrigin
    ? 'AI 판단 결과'
    : decision?.source === 'rule'
      ? '규칙 기반 판단'
      : '판단 근거';
  const rawConclusionText = decision
    ? isLlmOrigin
      ? getFinalConclusion(decision)
      : decision.reason || '내용 없음'
    : '';
  const conclusionText = humanizeToolNames(rawConclusionText);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-decision-detail-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <h3 id="ai-decision-detail-title" className="font-semibold text-gray-800">
            판단 상세
          </h3>
          <button
            ref={closeBtnRef}
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 text-gray-500"
            aria-label="닫기"
          >
            <MdClose className="text-xl" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 overflow-y-auto flex-1">
          {loading && !decision && (
            <div className="text-sm text-gray-500 py-8 text-center">불러오는 중…</div>
          )}

          {error && (
            <div className="flex items-start gap-2 bg-red-50 text-red-700 rounded-lg p-3 text-sm">
              <MdWarningAmber className="text-xl shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {decision && (
            <>
              {/* Meta */}
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-xs text-gray-500">{time}</span>
                <span className="text-sm font-medium text-gray-800">
                  {CT_LABELS[decision.control_type] ?? decision.control_type}
                </span>
                {priority && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${priority.cls}`}
                  >
                    {priority.label}
                  </span>
                )}
                {source && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${source.cls}`}
                  >
                    {source.label}
                  </span>
                )}
              </div>

              {/* 1. AI 판단 결과 / 판단 근거 */}
              <Section title={conclusionTitle}>
                <div
                  className={
                    isLlmOrigin
                      ? 'bg-emerald-50 border border-emerald-200 rounded-lg p-3'
                      : ''
                  }
                >
                  <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {conclusionText}
                  </p>
                </div>
              </Section>

              {/* 2. 적용된 제어 */}
              <Section title="적용된 제어">
                {actionRows.length === 0 ? (
                  <p className="text-xs text-gray-400">변경 사항 없음</p>
                ) : (
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                    {actionRows.map((row, i) => (
                      <div key={i} className="contents">
                        <dt className="text-gray-500">{row.label}</dt>
                        <dd className="font-medium text-gray-800">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </Section>

              {/* 3. 당시 센서 값 */}
              {snapshot && (
                <Section title="당시 센서 값">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    {snapshot.temperature != null && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">온도</span>
                        <span className="font-medium text-gray-800">
                          {snapshot.temperature}°C
                        </span>
                      </div>
                    )}
                    {snapshot.humidity != null && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">대기 습도</span>
                        <span className="font-medium text-gray-800">
                          {snapshot.humidity}%
                        </span>
                      </div>
                    )}
                    {snapshot.light_intensity != null && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">조도</span>
                        <span className="font-medium text-gray-800">
                          {snapshot.light_intensity} lx
                        </span>
                      </div>
                    )}
                    {snapshot.soil_moisture != null && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">토양 수분</span>
                        <span className="font-medium text-gray-800">
                          {snapshot.soil_moisture}%
                        </span>
                      </div>
                    )}
                  </div>
                </Section>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {decision && (
          <div className="border-t px-5 py-2.5 text-[11px] text-gray-400 flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 truncate">
              <span>
                duration{' '}
                <span className="font-mono text-gray-600">
                  {decision.duration_ms != null ? `${decision.duration_ms}ms` : '-'}
                </span>
              </span>
              <span className="truncate">
                id{' '}
                <span className="font-mono text-gray-600">
                  {decision.id.slice(0, 8)}…
                </span>
              </span>
            </div>
            <CopyButton text={decision.id} label="Copy decision id" />
          </div>
        )}
      </div>
    </div>
  );
}
