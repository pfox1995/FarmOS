// Design Ref: §4.3 — useManualControl 훅
import { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import type { ManualControlState, ControlCommand, ControlEvent } from '@/types';

const API_BASE = 'https://iot.lilpa.moe/api/v1';

export function useManualControl() {
  const [controlState, setControlState] = useState<ManualControlState | null>(null);
  const [simMode, setSimMode] = useState(false);
  const [loading, setLoading] = useState(true);

  // 디바운스용 타이머 ref
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  // 수동 조작 시각 기록 — AI rule SSE 방어용
  const manualTimestamps = useRef<Record<string, number>>({});
  // Design Ref: §5.1 — ON/OFF 마스터 스위치용 이전 슬라이더 값 저장 (세션 내)
  const lastKnownValuesRef = useRef<Partial<{
    ventilation: { window_open_pct: number; fan_speed: number };
    shading: { shade_pct: number; insulation_pct: number };
  }>>({});

  // 초기 로드: GET /control/state
  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/control/state`, { credentials: 'omit' });
      if (res.ok) {
        const data = await res.json();
        // Design Ref: §5.4 — 서버가 on 필드 미반환 시 led_on로 fallback
        const normalized = {
          ...data,
          ventilation: {
            ...data.ventilation,
            on: data.ventilation?.on ?? data.ventilation?.led_on ?? false,
          },
          shading: {
            ...data.shading,
            on: data.shading?.on ?? data.shading?.led_on ?? false,
          },
        };
        setControlState(normalized);
      }
    } catch {
      // 연결 실패 시 무시
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  // API POST 공통
  const _postControl = useCallback((
    controlType: string,
    action: Record<string, unknown>,
  ) => {
    return fetch(`${API_BASE}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'omit',
      body: JSON.stringify({
        control_type: controlType,
        action,
        source: 'manual',
      }),
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast.error(body.detail || body.message || `제어 요청 실패 (${res.status})`);
        fetchState();
        return Promise.reject(new Error(body.detail || `HTTP ${res.status}`));
      }
      return res;
    }).catch((err) => {
      if (err instanceof TypeError) {
        toast.error('서버에 연결할 수 없습니다');
        fetchState();
      }
      throw err;
    });
  }, [fetchState]);

  // 낙관적 업데이트 공통
  const _optimisticUpdate = useCallback((
    controlType: ControlCommand['control_type'],
    action: Record<string, unknown>,
  ) => {
    manualTimestamps.current[controlType] = Date.now();
    setControlState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [controlType]: { ...prev[controlType], ...action, source: 'manual', locked: true },
      };
    });
  }, []);

  // 슬라이더용 — 디바운스 300ms (드래그 중 연속 호출 방지)
  const sendCommand = useCallback((
    controlType: ControlCommand['control_type'],
    action: Record<string, unknown>,
  ) => {
    _optimisticUpdate(controlType, action);

    const timerKey = controlType;
    if (debounceTimers.current[timerKey]) {
      clearTimeout(debounceTimers.current[timerKey]);
    }
    debounceTimers.current[timerKey] = setTimeout(() => {
      _postControl(controlType, action);
    }, 300);
  }, [_optimisticUpdate, _postControl]);

  // 버튼용 — 즉시 실행 (밸브 토글, ON/OFF 등)
  const sendCommandImmediate = useCallback((
    controlType: ControlCommand['control_type'],
    action: Record<string, unknown>,
  ) => {
    _optimisticUpdate(controlType, action);
    _postControl(controlType, action);
  }, [_optimisticUpdate, _postControl]);

  // 시뮬레이션: ESP8266 버튼 누름 흉내
  const simulateButton = useCallback((
    controlType: ControlCommand['control_type'],
  ) => {
    if (!controlState) return;

    const current = controlState[controlType];
    const newActive = !current.active;

    let toggleState: Record<string, unknown>;
    switch (controlType) {
      case 'ventilation':
        // Design Ref: §5.2 — 시뮬 OFF 시 현재값 저장 → 수동 ON 토글 시 복원 가능
        if (!newActive) {
          lastKnownValuesRef.current.ventilation = {
            window_open_pct: current.window_open_pct,
            fan_speed: current.fan_speed,
          };
        }
        toggleState = {
          window_open_pct: newActive ? 100 : 0,
          fan_speed: newActive ? 1500 : 0,
          on: newActive,
        };
        break;
      case 'irrigation':
        toggleState = { valve_open: newActive };
        break;
      case 'lighting':
        toggleState = { on: newActive, brightness_pct: newActive ? 60 : 0 };
        break;
      case 'shading':
        // Design Ref: §5.2 — 시뮬 OFF 시 현재값 저장
        if (!newActive) {
          lastKnownValuesRef.current.shading = {
            shade_pct: current.shade_pct,
            insulation_pct: current.insulation_pct,
          };
        }
        toggleState = {
          shade_pct: newActive ? 50 : 0,
          insulation_pct: 0,
          on: newActive,
        };
        break;
    }

    // 낙관적 업데이트
    manualTimestamps.current[controlType] = Date.now();
    setControlState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [controlType]: { ...prev[controlType], ...toggleState, source: 'button', active: newActive, led_on: newActive, locked: true },
      };
    });

    fetch(`${API_BASE}/control/report`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'farmos-iot-default-key',
      },
      credentials: 'omit',
      body: JSON.stringify({
        device_id: 'simulator',
        control_type: controlType,
        state: toggleState,
        source: 'button',
      }),
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast.error(body.detail || body.message || `시뮬레이션 요청 실패 (${res.status})`);
        fetchState();
      }
    }).catch(() => {
      toast.error('서버에 연결할 수 없습니다');
      fetchState();
    });
  }, [controlState, fetchState]);

  // 잠금 해제 → AI 규칙이 다시 제어
  const unlockControl = useCallback((
    controlType: ControlCommand['control_type'],
  ) => {
    // 낙관적 업데이트
    setControlState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [controlType]: { ...prev[controlType], locked: false },
      };
    });

    fetch(`${API_BASE}/control/unlock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'omit',
      body: JSON.stringify({ control_type: controlType }),
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast.error(body.detail || body.message || `잠금 해제 실패 (${res.status})`);
        fetchState();
      }
    }).catch(() => {
      toast.error('서버에 연결할 수 없습니다');
      fetchState();
    });
  }, [fetchState]);

  // SSE control 이벤트로 상태 업데이트
  // 수동 조작 후 5초간 AI rule/tool 소스의 SSE는 무시 (슬라이더 복귀 방지)
  const handleControlEvent = useCallback((event: ControlEvent) => {
    const ct = event.control_type as keyof ManualControlState;
    const isAISource = ['rule', 'tool', 'ai'].includes(event.source);
    const lastManual = manualTimestamps.current[ct] || 0;
    const elapsed = Date.now() - lastManual;

    if (isAISource && elapsed < 5000) {
      return; // 수동 조작 후 5초간 AI SSE 무시
    }

    setControlState(prev => {
      if (!prev) return prev;
      if (!(ct in prev)) return prev;
      return {
        ...prev,
        [ct]: { ...prev[ct], ...event.state, source: event.source, updated_at: event.timestamp },
      };
    });
  }, []);

  // cleanup timers
  useEffect(() => {
    return () => {
      Object.values(debounceTimers.current).forEach(clearTimeout);
    };
  }, []);

  return {
    controlState,
    simMode,
    setSimMode,
    loading,
    sendCommand,
    sendCommandImmediate,
    simulateButton,
    unlockControl,
    handleControlEvent,
    refetch: fetchState,
    lastKnownValuesRef, // Design Ref: §5.3 — 마스터 스위치 복원값 공유
  };
}
