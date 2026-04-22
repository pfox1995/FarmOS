// 공통 날짜 범위 필터 — preset 탭(오늘/7일/30일/직접) + 커스텀 range 달력.
// AI Agent 최근 판단 · 관수 이력 · 센서 알림 등에서 공용 사용.

import { useEffect, useRef, useState } from 'react';
import { DayPicker, type DateRange } from 'react-day-picker';
import 'react-day-picker/style.css';
import { subDays } from 'date-fns';
import { ko } from 'date-fns/locale';
import { MdCalendarMonth, MdClose } from 'react-icons/md';

export type RangePreset = 'all' | 'today' | '7d' | '30d' | 'custom';

export interface DateRangeValue {
  since: Date | null;
  until: Date | null;
  preset: RangePreset;
}

interface Props {
  value: DateRangeValue;
  onChange: (v: DateRangeValue) => void;
  className?: string;
}

const PRESET_LABELS: Record<Exclude<RangePreset, 'custom'>, string> = {
  all: '전체',
  today: '오늘',
  '7d': '7일',
  '30d': '30일',
};

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function endOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
}

export function computePresetRange(
  preset: Exclude<RangePreset, 'custom' | 'all'>,
): {
  since: Date;
  until: Date;
} {
  // date-fns subDays 는 달력일(calendar day) 단위로 빼므로 DST 전환일에도
  // ±1 시간 오차가 없다. (KST 는 DST 미사용이지만 글로벌 안전성 차원)
  const now = new Date();
  const until = endOfDay(now);
  if (preset === 'today') return { since: startOfDay(now), until };
  if (preset === '7d') return { since: startOfDay(subDays(now, 6)), until };
  // 30d
  return { since: startOfDay(subDays(now, 29)), until };
}

function fmt(d: Date | null): string {
  if (!d) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export default function DateRangeFilter({ value, onChange, className }: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange | undefined>(
    value.since && value.until
      ? { from: value.since, to: value.until }
      : undefined,
  );
  const rootRef = useRef<HTMLDivElement | null>(null);

  // 바깥 클릭 시 팝오버 닫기
  useEffect(() => {
    if (!pickerOpen) return;
    const onClick = (e: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) setPickerOpen(false);
    };
    const onTouch = (e: TouchEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) setPickerOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Esc') setPickerOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('touchstart', onTouch);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('touchstart', onTouch);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [pickerOpen]);

  const selectPreset = (p: Exclude<RangePreset, 'custom'>) => {
    if (p === 'all') {
      onChange({ since: null, until: null, preset: 'all' });
      setDraft(undefined);
      setPickerOpen(false);
      return;
    }
    const { since, until } = computePresetRange(p);
    onChange({ since, until, preset: p });
    setDraft({ from: since, to: until });
    setPickerOpen(false);
  };

  const openCustom = () => {
    // 현재 값이 있으면 초안에 세팅
    setDraft(
      value.since && value.until
        ? { from: value.since, to: value.until }
        : undefined,
    );
    setPickerOpen(true);
  };

  const applyCustom = () => {
    if (draft?.from) {
      const since = startOfDay(draft.from);
      const until = endOfDay(draft.to ?? draft.from);
      onChange({ since, until, preset: 'custom' });
      setPickerOpen(false);
    }
  };

  const clearCustom = () => {
    setDraft(undefined);
  };

  return (
    <div
      ref={rootRef}
      className={`relative inline-flex items-center gap-1 ${className ?? ''}`}
    >
      {(Object.keys(PRESET_LABELS) as Array<Exclude<RangePreset, 'custom'>>).map(
        (p) => {
          const active = value.preset === p;
          return (
            <button
              key={p}
              type="button"
              onClick={() => selectPreset(p)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                active
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {PRESET_LABELS[p]}
            </button>
          );
        },
      )}

      <button
        type="button"
        onClick={openCustom}
        className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
          value.preset === 'custom'
            ? 'bg-indigo-600 text-white shadow-sm'
            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
        }`}
      >
        <MdCalendarMonth className="text-sm" />
        {value.preset === 'custom' && value.since && value.until
          ? `${fmt(value.since)} ~ ${fmt(value.until)}`
          : '직접 지정'}
      </button>

      {pickerOpen && (
        <div className="absolute z-50 top-full left-0 mt-2 bg-white rounded-xl shadow-2xl border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-700">
              날짜 범위 선택
            </span>
            <button
              type="button"
              onClick={() => setPickerOpen(false)}
              className="p-1 rounded hover:bg-gray-100 text-gray-400"
              aria-label="닫기"
            >
              <MdClose />
            </button>
          </div>
          <DayPicker
            mode="range"
            selected={draft}
            onSelect={setDraft}
            locale={ko}
            weekStartsOn={0}
            classNames={{
              root: 'text-sm',
              caption_label: 'font-medium',
              day: 'rounded-md',
              today: 'font-bold text-indigo-600',
              selected: '!bg-indigo-600 !text-white',
              range_start: '!bg-indigo-700',
              range_end: '!bg-indigo-700',
              range_middle: '!bg-indigo-100 !text-indigo-900',
            }}
          />
          <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t">
            <button
              type="button"
              onClick={clearCustom}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              초기화
            </button>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPickerOpen(false)}
                className="px-3 py-1 text-xs text-gray-600 rounded hover:bg-gray-100"
              >
                취소
              </button>
              <button
                type="button"
                onClick={applyCustom}
                disabled={!draft?.from}
                className="px-3 py-1 text-xs text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:bg-gray-300"
              >
                적용
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
