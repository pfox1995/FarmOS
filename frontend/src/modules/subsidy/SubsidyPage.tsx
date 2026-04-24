import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  MdCheckCircle,
  MdWarning,
  MdBlock,
  MdChat,
  MdClose,
  MdSend,
  MdExpandMore,
  MdExpandLess,
} from 'react-icons/md';
import {
  type Citation,
  type EligibilityResult,
  type MatchResponse,
  type PaymentCalculation,
  type SubsidyAskResponse,
  askSubsidy,
  fetchMatch,
} from './api';

const STATUS_CONFIG = {
  eligible: {
    label: '신청 가능',
    icon: MdCheckCircle,
    cardClass: 'border-green-300 bg-green-50',
    badgeClass: 'bg-green-600 text-white',
    iconClass: 'text-green-600',
  },
  needs_review: {
    label: '추가 확인 필요',
    icon: MdWarning,
    cardClass: 'border-amber-300 bg-amber-50',
    badgeClass: 'bg-amber-500 text-white',
    iconClass: 'text-amber-600',
  },
  ineligible: {
    label: '해당 없음',
    icon: MdBlock,
    cardClass: 'border-gray-200 bg-gray-50',
    badgeClass: 'bg-gray-400 text-white',
    iconClass: 'text-gray-400',
  },
} as const;

function formatKrw(amount: number | null): string {
  if (amount == null) return '';
  if (amount >= 10_000_000) return `${(amount / 10_000_000).toFixed(2)}천만원`;
  if (amount >= 10_000) return `${(amount / 10_000).toLocaleString()}만원`;
  return `${amount.toLocaleString()}원`;
}

export default function SubsidyPage() {
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<EligibilityResult | null>(null);
  const [askOpen, setAskOpen] = useState(false);

  useEffect(() => {
    fetchMatch()
      .then(setMatch)
      .catch((err) => toast.error(`매칭 실패: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-20 text-gray-500">
        공익직불사업 자격을 확인하는 중...
      </div>
    );
  }

  if (!match) {
    return <div className="card text-center">데이터를 불러올 수 없습니다.</div>;
  }

  const allResults = [
    ...match.eligible,
    ...match.needs_review,
    ...match.ineligible,
  ];

  return (
    <div className="space-y-6">
      {/* 안내 헤더 */}
      <div className="card bg-gradient-to-r from-primary/5 to-primary/10 border-primary/20">
        <div className="flex items-start gap-3">
          <div className="text-4xl">🌾</div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              2026년도 기본형 공익직불사업
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              귀하의 프로필 정보를 바탕으로 신청 가능한 지원금을 분석했습니다.
              각 카드를 클릭하면 상세 정보와 근거 조항을 확인할 수 있습니다.
            </p>
          </div>
        </div>
      </div>

      {/* 결과 요약 */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryTile
          count={match.eligible.length}
          label="신청 가능"
          tone="green"
        />
        <SummaryTile
          count={match.needs_review.length}
          label="추가 확인"
          tone="amber"
        />
        <SummaryTile
          count={match.ineligible.length}
          label="해당 없음"
          tone="gray"
        />
      </div>

      {/* 지원금 카드 목록 */}
      <div className="space-y-3">
        {allResults.length === 0 ? (
          <div className="card text-center text-gray-500">
            등록된 지원금 정보가 없습니다.
          </div>
        ) : (
          allResults.map((r) => (
            <SubsidyCard key={r.subsidy_code} result={r} onClick={() => setSelected(r)} />
          ))
        )}
      </div>

      {/* 질의응답 버튼 (하단 고정) */}
      <button
        onClick={() => setAskOpen(true)}
        className="fixed bottom-24 lg:bottom-8 right-6 bg-primary text-white rounded-full px-5 py-3 shadow-lg flex items-center gap-2 hover:bg-primary/90 transition"
      >
        <MdChat className="text-xl" />
        <span className="font-semibold">시행지침 질문</span>
      </button>

      {/* 상세 드로어 */}
      {selected && (
        <DetailDrawer result={selected} onClose={() => setSelected(null)} />
      )}

      {/* Q&A 모달 */}
      {askOpen && <AskModal onClose={() => setAskOpen(false)} />}
    </div>
  );
}

// ─── 하위 컴포넌트 ────────────────────────────────────────

function SummaryTile({
  count,
  label,
  tone,
}: {
  count: number;
  label: string;
  tone: 'green' | 'amber' | 'gray';
}) {
  const toneMap = {
    green: 'bg-green-50 border-green-200 text-green-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    gray: 'bg-gray-50 border-gray-200 text-gray-700',
  };
  return (
    <div className={`border-2 rounded-2xl p-4 text-center ${toneMap[tone]}`}>
      <div className="text-3xl font-bold">{count}</div>
      <div className="text-xs font-semibold mt-1">{label}</div>
    </div>
  );
}

function SubsidyCard({
  result,
  onClick,
}: {
  result: EligibilityResult;
  onClick: () => void;
}) {
  const cfg = STATUS_CONFIG[result.status];
  const Icon = cfg.icon;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left card border-2 transition-all hover:shadow-md ${cfg.cardClass}`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`text-3xl ${cfg.iconClass} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-lg text-gray-900">
              {result.subsidy_name}
            </h3>
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.badgeClass}`}
            >
              {cfg.label}
            </span>
          </div>
          {result.estimated_amount_krw != null && (
            <p className="text-primary font-bold mt-1">
              예상 수령액: {formatKrw(result.estimated_amount_krw)}
            </p>
          )}
          {result.reasons.length > 0 && (
            <p className="text-sm text-gray-700 mt-2 line-clamp-2">
              {result.reasons[0].text}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

function DetailDrawer({
  result,
  onClose,
}: {
  result: EligibilityResult;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-t-3xl sm:rounded-2xl w-full sm:max-w-lg max-h-[85vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-xl font-bold text-gray-900">
            {result.subsidy_name}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 p-1"
          >
            <MdClose className="text-2xl" />
          </button>
        </div>

        <span
          className={`inline-block px-3 py-1 rounded-full text-sm font-semibold mb-4 ${STATUS_CONFIG[result.status].badgeClass}`}
        >
          {STATUS_CONFIG[result.status].label}
        </span>

        {result.estimated_amount_krw != null && (
          <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 mb-4">
            <p className="text-sm text-gray-600">예상 수령액</p>
            <p className="text-2xl font-bold text-primary">
              {formatKrw(result.estimated_amount_krw)}
            </p>
            {result.payment_calculation && (
              <PaymentBreakdown calc={result.payment_calculation} />
            )}
          </div>
        )}

        <div className="space-y-3">
          <h3 className="font-semibold text-gray-900">판정 사유</h3>
          <ul className="space-y-2 text-sm text-gray-700">
            {result.reasons.map((reason, i) => (
              <li key={i} className="flex gap-2 items-start">
                <span className="text-gray-400 flex-shrink-0 leading-relaxed">•</span>
                <span className="flex-1 leading-relaxed">
                  {reason.text}
                  {reason.source && (
                    <span className="ml-2 inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-md bg-primary text-white shadow-sm align-middle whitespace-nowrap">
                      {reason.source}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {(result.source_clauses.length > 0 || result.source_articles.length > 0) && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 mb-2">출처</p>
            {result.source_articles.length > 0 && (
              <p className="text-sm text-gray-700 mb-3">
                {result.source_articles.join(' · ')}
              </p>
            )}
            {result.source_clauses.length > 0 && (
              <ul className="space-y-2">
                {result.source_clauses.map((clause) => (
                  <li
                    key={clause.tag}
                    className="flex gap-2 items-start text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2"
                  >
                    <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded-md bg-primary text-white shadow-sm whitespace-nowrap flex-shrink-0 mt-0.5">
                      {clause.tag}
                    </span>
                    <span className="flex-1 leading-relaxed">{clause.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-6 text-xs text-gray-400 text-center">
          실제 지급은 농업경영체 등록·현장 확인 등 정식 절차를 거쳐 확정됩니다.
        </div>
      </div>
    </div>
  );
}

// 예상 수령액의 계산식 표시 (fixed 는 1줄, tiered 는 구간별 여러 줄).
// 총액은 이미 상단에 크게 표시되므로 여기서는 내역과 합만 작게 보여 준다.
function PaymentBreakdown({ calc }: { calc: PaymentCalculation }) {
  return (
    <div className="mt-3 pt-3 border-t border-primary/20 space-y-2">
      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
        계산 내역
      </p>
      <ul className="space-y-1.5">
        {calc.steps.map((step, i) => (
          <li key={i} className="flex items-start justify-between gap-3 text-xs">
            <span className="text-gray-700 leading-relaxed flex-1">
              {step.description}
            </span>
            <span className="text-gray-900 font-semibold whitespace-nowrap">
              {formatKrw(step.amount_krw)}
            </span>
          </li>
        ))}
      </ul>
      {calc.steps.length > 1 && (
        <div className="flex items-center justify-between pt-1.5 border-t border-gray-200 text-xs">
          <span className="font-semibold text-gray-700">합계</span>
          <span className="font-bold text-primary">{formatKrw(calc.total_krw)}</span>
        </div>
      )}
      {calc.note && (
        <p className="text-[11px] text-gray-500 leading-relaxed pt-1">※ {calc.note}</p>
      )}
    </div>
  );
}

function AskModal({ onClose }: { onClose: () => void }) {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<SubsidyAskResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!question.trim() || loading) return;
    setLoading(true);
    setResponse(null);
    try {
      const res = await askSubsidy(question.trim());
      setResponse(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '알 수 없는 오류';
      toast.error(`질문 처리 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  // 닫기 확인: 답변이 이미 표시되어 있거나, 입력창에 질문이 작성 중이거나,
  // LLM 호출이 진행 중일 때만 한 번 더 확인한다. 빈 상태에서는 바로 닫는다.
  const requestClose = () => {
    const hasUnsavedInput = question.trim().length > 0;
    const hasResponse = response !== null;
    if (!loading && !hasUnsavedInput && !hasResponse) {
      onClose();
      return;
    }
    const msg = loading
      ? '답변 생성 중입니다. 지금 닫으면 결과를 볼 수 없습니다. 닫으시겠어요?'
      : '현재 작성/조회 중인 내용이 있습니다. 창을 닫으시겠어요?';
    if (window.confirm(msg)) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={requestClose}
    >
      <div
        className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">
            시행지침 질문하기
          </h2>
          <button onClick={requestClose} className="text-gray-400 hover:text-gray-700 p-1">
            <MdClose className="text-2xl" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {response && (
            <div className="space-y-3">
              <div className="bg-primary/5 rounded-xl p-4">
                <p className="text-xs font-semibold text-gray-500 mb-1">질문</p>
                <p className="text-gray-900">{response.question}</p>
              </div>
              <div className="bg-white border-2 border-primary/20 rounded-xl p-4">
                <p className="text-xs font-semibold text-primary mb-2">답변</p>
                <p className="text-gray-900 whitespace-pre-wrap leading-relaxed">
                  {response.answer}
                </p>
              </div>
              {response.citations.length > 0 && (
                <CitationsSection citations={response.citations} />
              )}
              {response.escalation_needed && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
                  시행지침만으로 답변하기 어려운 질문입니다.
                  농관원 콜센터(1334) 또는 지자체 담당자에게 문의해주세요.
                </div>
              )}
            </div>
          )}

          {!response && !loading && (
            <div className="text-center text-gray-500 py-8 space-y-2">
              <p>공익직불사업에 관한 질문을 자유롭게 입력하세요.</p>
              <p className="text-xs">예: "소농직불금 받으려면 무엇이 필요해요?"</p>
              <p className="text-xs">예: "청년농인데 부정수급 걸리면 어떻게 돼요?"</p>
            </div>
          )}

          {loading && <LlmLoadingIndicator />}
        </div>

        <div className="p-4 border-t border-gray-100 flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="질문을 입력하세요"
            className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:border-primary"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !question.trim()}
            className="bg-primary text-white px-5 py-2.5 rounded-xl disabled:opacity-50 flex items-center gap-1 hover:bg-primary/90 transition"
          >
            <MdSend />
            <span className="hidden sm:inline">전송</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// LLM 응답 대기 중 표시. 3 단계 stepper + 스켈레톤으로 "동작 중" 인식을 준다.
function LlmLoadingIndicator() {
  return (
    <div className="space-y-4 py-4" role="status" aria-live="polite">
      <div className="flex items-center justify-center gap-3 text-primary">
        <span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0ms' }} />
        <span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" style={{ animationDelay: '150ms' }} />
        <span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" style={{ animationDelay: '300ms' }} />
      </div>
      <p className="text-center text-sm text-gray-600">
        시행지침에서 근거 조항을 찾고 답변을 작성하고 있습니다...
      </p>
      <div className="space-y-2 mx-auto max-w-md">
        <div className="h-3 bg-gray-200 rounded animate-pulse" />
        <div className="h-3 bg-gray-200 rounded animate-pulse w-5/6" />
        <div className="h-3 bg-gray-200 rounded animate-pulse w-4/6" />
      </div>
    </div>
  );
}

// ─── 근거 조항 섹션 (접을 수 있는 citation 카드) ─────────

function CitationsSection({ citations }: { citations: Citation[] }) {
  // 백엔드 dedup 이 안 된 경우를 대비한 프론트 방어 로직 (중복 article 제거)
  const deduped = useMemo(() => {
    const seen = new Set<string>();
    const out: Citation[] = [];
    for (const c of citations) {
      const key = `${c.chapter}__${c.article}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(c);
    }
    return out.slice(0, 3);
  }, [citations]);

  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 mb-2">
        근거 조항 ({deduped.length}건)
      </p>
      <div className="space-y-2">
        {deduped.map((c, i) => (
          <CitationCard key={`${c.chapter}-${c.article}-${i}`} c={c} />
        ))}
      </div>
    </div>
  );
}

function CitationCard({ c }: { c: Citation }) {
  const [open, setOpen] = useState(false);

  // 백엔드 snippet 이 아직 정리되지 않은 경우를 대비한 프론트 방어 로직
  const cleanSnippet = useMemo(() => cleanSnippetFallback(c.snippet), [c.snippet]);
  const cleanChapter = useMemo(
    () => c.chapter.replace(/\s*>\s*\(장 내 최상위 절\)|\s*>\s*\(상위 미지정\)/g, ''),
    [c.chapter],
  );
  const hasSnippet = Boolean(cleanSnippet);

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => hasSnippet && setOpen(!open)}
        className={`w-full text-left px-3 py-2.5 flex items-start gap-2 ${
          hasSnippet ? 'hover:bg-gray-100 cursor-pointer' : 'cursor-default'
        }`}
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">
            {c.article || '(제목 없음)'}
          </p>
          {cleanChapter && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{cleanChapter}</p>
          )}
        </div>
        {hasSnippet && (
          <span className="flex-shrink-0 text-gray-400 text-lg mt-0.5">
            {open ? <MdExpandLess /> : <MdExpandMore />}
          </span>
        )}
      </button>
      {open && hasSnippet && (
        <div className="px-3 pb-3 pt-2 border-t border-gray-200 bg-white">
          <p className="text-xs text-gray-700 leading-relaxed">{cleanSnippet}</p>
        </div>
      )}
    </div>
  );
}

/** 백엔드 정리가 안 된 snippet 을 프론트에서도 한 번 더 털어냄 (방어 로직). */
function cleanSnippetFallback(raw: string | undefined): string {
  if (!raw) return '';
  return raw
    .replace(/\|\s*-{3,}\s*(?:\|\s*-{3,}\s*)+\|/g, ' ')   // table separator rows
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')                  // image placeholders
    .replace(/^#{1,6}\s*/gm, '')                            // markdown headers
    .replace(/[☑□]/g, '')                                    // check-box chars
    .replace(/\s*\|\s*/g, ' · ')                             // remaining pipes → middle dot
    .replace(/(?:\s*·\s*){2,}/g, ' · ')                      // collapse consecutive dots
    .replace(/\s+/g, ' ')                                     // collapse whitespace
    .replace(/^[\s·]+|[\s·]+$/g, '')                         // trim dots/spaces
    .slice(0, 350);
}
