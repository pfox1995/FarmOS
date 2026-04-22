import { useState, useEffect, useCallback } from 'react';
import type {
  AIAgentStatus,
  AIDecision,
  ActivitySummary,
  CropProfile,
  DecisionListResponse,
} from '@/types';
import { onAIDecisionEvent } from '@/hooks/useSensorData';

// Design Ref §5.3 — 2-base 전략:
// - Relay: AI Agent 상태/토글/Override (기존 기능)
// - FarmOS BE: decisions/summary/detail (agent-action-history 신규, Bridge 적재 데이터)
const RELAY_API_BASE = 'https://iot.lilpa.moe/api/v1';
const FARMOS_API_BASE =
  (import.meta as unknown as { env?: { VITE_FARMOS_API_BASE?: string } }).env
    ?.VITE_FARMOS_API_BASE ?? 'http://localhost:8000/api/v1';

const POLL_INTERVAL = 60000; // SSE가 실시간 처리하므로 폴링은 60초 fallback

export function useAIAgent() {
  const [status, setStatus] = useState<AIAgentStatus | null>(null);
  const [decisions, setDecisions] = useState<AIDecision[]>([]);
  const [loading, setLoading] = useState(true);

  // agent-action-history 신규 상태
  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [summaryRange, setSummaryRange] = useState<ActivitySummary['range']>('today');
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [listLoading, setListLoading] = useState(false);

  // 날짜 범위 필터 (decisions 목록 재조회 시 사용)
  const [dateSince, setDateSince] = useState<Date | null>(null);
  const [dateUntil, setDateUntil] = useState<Date | null>(null);

  // ── 기존 Relay 상태 fetch ─────────────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (dateSince) params.set('since', dateSince.toISOString());
      if (dateUntil) params.set('until', dateUntil.toISOString());

      const [statusRes, decisionsRes] = await Promise.all([
        fetch(`${RELAY_API_BASE}/ai-agent/status`, { credentials: 'omit' }),
        fetch(`${FARMOS_API_BASE}/ai-agent/decisions?${params}`, {
          credentials: 'include',
        }),
      ]);
      if (statusRes.ok) {
        const data = await statusRes.json();
        setStatus(data);
      }
      if (decisionsRes.ok) {
        const data = (await decisionsRes.json()) as DecisionListResponse;
        setDecisions(data.items ?? []);
        setNextCursor(data.next_cursor ?? null);
        setHasMore(Boolean(data.has_more));
      } else if (decisionsRes.status === 401) {
        // FarmOS 로그인 안된 경우 — Relay fallback 으로 최근 20건 시도 (필터 미적용)
        try {
          const fb = await fetch(
            `${RELAY_API_BASE}/ai-agent/decisions?limit=20`,
            { credentials: 'omit' }
          );
          if (fb.ok) {
            const arr = (await fb.json()) as AIDecision[];
            setDecisions(Array.isArray(arr) ? arr : []);
            setHasMore(false);
            setNextCursor(null);
          }
        } catch {
          // 무시
        }
      }
    } catch {
      // 무시
    } finally {
      setLoading(false);
    }
  }, [dateSince, dateUntil]);

  // 날짜 필터 변경 API — AIAgentPanel 에서 DateRangeFilter 로부터 호출.
  const setDateRange = useCallback(
    (since: Date | null, until: Date | null) => {
      setDateSince(since);
      setDateUntil(until);
    },
    [],
  );

  // ── FarmOS /activity/summary ──────────────────────────────────────────────
  const fetchSummary = useCallback(
    async (range: ActivitySummary['range']) => {
      setSummaryLoading(true);
      try {
        const res = await fetch(
          `${FARMOS_API_BASE}/ai-agent/activity/summary?range=${range}`,
          { credentials: 'include' }
        );
        if (res.ok) {
          const data = (await res.json()) as ActivitySummary;
          setSummary(data);
          setSummaryRange(range);
        }
      } catch {
        // 무시
      } finally {
        setSummaryLoading(false);
      }
    },
    []
  );

  // ── FarmOS /decisions?cursor=… (더보기) ───────────────────────────────────
  const fetchMore = useCallback(
    async (opts?: { control_type?: string; source?: string; priority?: string }) => {
      if (listLoading) return;
      setListLoading(true);
      try {
        const params = new URLSearchParams({ limit: '20' });
        if (nextCursor) params.set('cursor', nextCursor);
        if (opts?.control_type) params.set('control_type', opts.control_type);
        if (opts?.source) params.set('source', opts.source);
        if (opts?.priority) params.set('priority', opts.priority);
        if (dateSince) params.set('since', dateSince.toISOString());
        if (dateUntil) params.set('until', dateUntil.toISOString());

        const res = await fetch(
          `${FARMOS_API_BASE}/ai-agent/decisions?${params}`,
          { credentials: 'include' }
        );
        if (res.ok) {
          const data = (await res.json()) as DecisionListResponse;
          setDecisions((prev) => {
            const seen = new Set(prev.map((d) => d.id));
            const fresh = (data.items ?? []).filter((d) => !seen.has(d.id));
            return [...prev, ...fresh];
          });
          setNextCursor(data.next_cursor ?? null);
          setHasMore(Boolean(data.has_more));
        }
      } catch {
        // 무시
      } finally {
        setListLoading(false);
      }
    },
    [listLoading, nextCursor, dateSince, dateUntil]
  );

  // ── FarmOS /decisions/{id} (단건 상세) ────────────────────────────────────
  const fetchDetail = useCallback(async (id: string): Promise<AIDecision | null> => {
    // 먼저 메모리 캐시 확인
    const cached = decisions.find((d) => d.id === id);
    try {
      const res = await fetch(
        `${FARMOS_API_BASE}/ai-agent/decisions/${encodeURIComponent(id)}`,
        { credentials: 'include' }
      );
      if (res.ok) {
        const fresh = (await res.json()) as AIDecision;
        // 캐시 업데이트
        setDecisions((prev) =>
          prev.map((d) => (d.id === fresh.id ? { ...d, ...fresh } : d))
        );
        return fresh;
      }
      if (res.status === 404) {
        return null;
      }
    } catch {
      // 네트워크 실패 시 캐시로 대체
    }
    return cached ?? null;
  }, [decisions]);

  // ── 초기 로드 + 주기 폴링 ─────────────────────────────────────────────────
  useEffect(() => {
    fetchStatus();
    fetchSummary('today');
    const timer = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchStatus, fetchSummary]);

  // ── SSE ai_decision 이벤트 → 즉시 prepend + 요약 증분 ─────────────────────
  useEffect(() => {
    return onAIDecisionEvent((data) => {
      const decision = data as AIDecision;

      setDecisions((prev) => {
        if (prev.some((d) => d.id === decision.id)) return prev;
        return [decision, ...prev];
      });

      setStatus((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          latest_decision: decision,
          total_decisions: prev.total_decisions + 1,
        };
      });

      if (decision.control_type && decision.action) {
        setStatus((prev) => {
          if (!prev) return prev;
          const ct = decision.control_type as keyof typeof prev.control_state;
          if (!(ct in prev.control_state)) return prev;
          return {
            ...prev,
            control_state: {
              ...prev.control_state,
              [ct]: { ...prev.control_state[ct], ...decision.action },
            },
          };
        });
      }

      // 요약 증분 (today 탭 활성 시만 즉시 반영, 그 외는 다음 fetchSummary 대기)
      setSummary((prev) => {
        if (!prev || prev.range !== 'today') return prev;
        const nextByCt = { ...prev.by_control_type };
        nextByCt[decision.control_type] = (nextByCt[decision.control_type] ?? 0) + 1;
        const nextBySrc = { ...prev.by_source };
        nextBySrc[decision.source] = (nextBySrc[decision.source] ?? 0) + 1;
        const nextByPr = { ...prev.by_priority };
        nextByPr[decision.priority] = (nextByPr[decision.priority] ?? 0) + 1;
        return {
          ...prev,
          total: prev.total + 1,
          by_control_type: nextByCt,
          by_source: nextBySrc,
          by_priority: nextByPr,
          latest_at: decision.timestamp,
        };
      });
    });
  }, []);

  // ── 기존 Relay 기능: toggle / crop-profile / override ─────────────────────
  const toggle = useCallback(async () => {
    try {
      const res = await fetch(`${RELAY_API_BASE}/ai-agent/toggle`, {
        method: 'POST',
        credentials: 'omit',
      });
      if (res.ok) {
        await fetchStatus();
      }
    } catch {
      // 무시
    }
  }, [fetchStatus]);

  const updateCropProfile = useCallback(
    async (profile: CropProfile) => {
      try {
        const res = await fetch(`${RELAY_API_BASE}/ai-agent/crop-profile`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'omit',
          body: JSON.stringify(profile),
        });
        if (res.ok) {
          await fetchStatus();
        }
      } catch {
        // 무시
      }
    },
    [fetchStatus]
  );

  const override = useCallback(
    async (controlType: string, values: Record<string, unknown>, reason: string) => {
      try {
        await fetch(`${RELAY_API_BASE}/ai-agent/override`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'omit',
          body: JSON.stringify({ control_type: controlType, values, reason }),
        });
        await fetchStatus();
      } catch {
        // 무시
      }
    },
    [fetchStatus]
  );

  return {
    // 기존
    status,
    decisions,
    loading,
    toggle,
    updateCropProfile,
    override,
    refetch: fetchStatus,
    // agent-action-history 신규
    summary,
    summaryRange,
    summaryLoading,
    fetchSummary,
    hasMore,
    listLoading,
    fetchMore,
    fetchDetail,
    // 날짜 범위 필터
    dateSince,
    dateUntil,
    setDateRange,
  };
}
