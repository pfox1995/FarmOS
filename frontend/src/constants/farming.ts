/**
 * 농업 관련 공유 상수 — OnboardingPage, ProfilePage 등에서 공통 사용.
 * 백엔드 schemas/auth.py 의 FarmlandType / FarmerType Literal 과 동기화.
 */

export const CROP_OPTIONS = [
  '감자', '고추', '들깨', '무', '배추', '벼',
  '양배추', '오이', '옥수수', '콩', '토마토', '파',
] as const;

export const FARMLAND_TYPES = [
  { value: '논', label: '논 (수도작)', desc: '벼 등 수도작 재배' },
  { value: '밭', label: '밭 (전작)', desc: '채소, 과수 등 밭작물' },
  { value: '과수원', label: '과수원', desc: '사과, 배 등 과수 재배' },
  { value: '혼합', label: '혼합', desc: '논 + 밭 혼합 경영' },
] as const;

export const FARMER_TYPES = [
  { value: '일반', label: '일반 농업인' },
  { value: '청년농업인', label: '청년농업인 (만 18~40세)' },
  { value: '후계농업경영인', label: '후계농업경영인' },
  { value: '전업농업인', label: '전업농업인' },
] as const;

/** 평 → m² / ha 변환. 음수·NaN 은 null 반환. */
export function safeAreaConvert(pyeong: string): { m2: number; ha: number } | null {
  const val = parseFloat(pyeong);
  if (!pyeong || isNaN(val) || val < 0) return null;
  const m2 = val * 3.306;
  return { m2, ha: m2 / 10000 };
}
