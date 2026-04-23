import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { useAuth } from '@/context/AuthContext';
import { CROP_OPTIONS, FARMLAND_TYPES, FARMER_TYPES, safeAreaConvert } from '@/constants/farming';
import DaumPostcode from 'react-daum-postcode';
import { MdSearch } from 'react-icons/md';
import { formatDaumAddress, type DaumPostcodeData } from '@/utils/daumAddress';

const API_BASE = 'http://localhost:8000/api/v1';

/* ────────────── 타입 ────────────── */
interface ProfileData {
  farmname: string;
  location: string;
  area: string;
  main_crop: string;
  crop_variety: string;
  farmland_type: string;
  is_promotion_area: boolean;
  has_farm_registration: boolean;
  farmer_type: string;
  years_rural_residence: string;
  years_farming: string;
}

/* ────────────── 메인 컴포넌트 ────────────── */
export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [editing, setEditing] = useState<string | null>(null); // 'farm' | 'crop' | 'detail'
  const [draft, setDraft] = useState<ProfileData | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const [isPostcodeOpen, setIsPostcodeOpen] = useState(false);
  const postcodeCloseButtonRef = useRef<HTMLButtonElement | null>(null);

  const handleCompletePostcode = (data: DaumPostcodeData) => {
    setDraft(d => d ? { ...d, location: formatDaumAddress(data) } : d);
    setIsPostcodeOpen(false);
  };

  useEffect(() => {
    if (isPostcodeOpen) {
      postcodeCloseButtonRef.current?.focus();
    }
  }, [isPostcodeOpen]);

  useEffect(() => {
    if (!isPostcodeOpen) return;
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsPostcodeOpen(false);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isPostcodeOpen]);

  // 서버에서 전체 프로필 로드 (10초 타임아웃 + 재시도)
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    (async () => {
      setLoadError(false);
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          credentials: 'include',
          signal: controller.signal,
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        const p: ProfileData = {
          farmname: data.farmname || '',
          location: data.location || '',
          area: data.area ? String(data.area) : '',
          main_crop: data.main_crop || '',
          crop_variety: data.crop_variety || '',
          farmland_type: data.farmland_type || '',
          is_promotion_area: data.is_promotion_area ?? false,
          has_farm_registration: data.has_farm_registration ?? false,
          farmer_type: data.farmer_type || '일반',
          years_rural_residence: data.years_rural_residence ? String(data.years_rural_residence) : '',
          years_farming: data.years_farming ? String(data.years_farming) : '',
        };
        setProfile(p);
        setDraft(p);
      } catch {
        if (controller.signal.aborted) return; // StrictMode cleanup — 무시
        setLoadError(true);
        toast.error('프로필을 불러올 수 없습니다.');
      } finally {
        clearTimeout(timeout);
      }
    })();

    return () => { controller.abort(); clearTimeout(timeout); };
  }, [retryCount]);

  const startEdit = (section: string) => {
    setDraft(profile ? { ...profile } : null);
    setEditing(section);
  };

  const cancelEdit = () => {
    setDraft(profile ? { ...profile } : null);
    setEditing(null);
  };

  const saveSection = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const body = {
        farmname: draft.farmname,
        location: draft.location,
        area: draft.area ? parseFloat(draft.area) : 0,
        main_crop: draft.main_crop,
        crop_variety: draft.crop_variety,
        farmland_type: draft.farmland_type,
        is_promotion_area: draft.is_promotion_area,
        has_farm_registration: draft.has_farm_registration,
        farmer_type: draft.farmer_type,
        years_rural_residence: draft.years_rural_residence ? parseInt(draft.years_rural_residence) : 0,
        years_farming: draft.years_farming ? parseInt(draft.years_farming) : 0,
      };
      const res = await fetch(`${API_BASE}/auth/onboarding`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error();
      setProfile({ ...draft });
      setEditing(null);
      await refreshUser();
      toast.success('프로필이 저장되었습니다.');
    } catch {
      toast.error('저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const inputClass = 'w-full px-4 py-3 text-lg border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-primary outline-none transition';
  const selectClass = `${inputClass} bg-white appearance-none cursor-pointer`;

  if (!profile || !draft) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        {loadError ? (
          <>
            <p className="text-gray-500">프로필을 불러올 수 없습니다.</p>
            <button
              onClick={() => setRetryCount(c => c + 1)}
              className="px-4 py-2 text-sm font-semibold text-primary border border-primary/30 rounded-lg hover:bg-primary/5 transition"
            >
              다시 시도
            </button>
          </>
        ) : (
          <div className="text-gray-400">불러오는 중...</div>
        )}
      </div>
    );
  }

  const hasEmptyFields = !profile.farmname && !profile.main_crop && !profile.farmland_type;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="module-title">내 프로필</h1>
        <p className="text-gray-500 mt-1">농장 정보와 영농 상세를 관리합니다</p>
      </div>

      {/* 미완성 안내 배너 */}
      {hasEmptyFields && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-accent/10 border border-accent/30 rounded-xl p-4 flex items-start gap-3"
        >
          <span className="text-2xl flex-shrink-0">📝</span>
          <div>
            <p className="font-semibold text-gray-800">프로필을 완성해주세요</p>
            <p className="text-sm text-gray-600 mt-0.5">
              보조금 적격성 확인, 맞춤 시세 알림 등 FarmOS의 핵심 기능을 이용할 수 있습니다.
            </p>
          </div>
        </motion.div>
      )}

      {/* 계정 정보 (읽기 전용) */}
      <Section title="계정 정보" icon="👤">
        <InfoRow label="아이디" value={user?.user_id || ''} />
        <InfoRow label="이름" value={user?.name || ''} />
      </Section>

      {/* 농장 기본정보 */}
      <Section
        title="농장 기본정보"
        icon="🏡"
        isEditing={editing === 'farm'}
        onEdit={() => startEdit('farm')}
        onCancel={cancelEdit}
        onSave={saveSection}
        saving={saving}
      >
        {editing === 'farm' ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">농장 이름</label>
              <input type="text" value={draft.farmname} onChange={e => setDraft(d => d ? { ...d, farmname: e.target.value } : d)} placeholder="예: 행복한 사과농장" className={inputClass} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">주소</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  placeholder="주소를 검색하세요"
                  value={draft.location}
                  onClick={() => setIsPostcodeOpen(true)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setIsPostcodeOpen(true);
                    }
                  }}
                  tabIndex={0}
                  className={`${inputClass} cursor-pointer`}
                />
                <button
                  type="button"
                  onClick={() => setIsPostcodeOpen(true)}
                  className="flex-shrink-0 bg-primary text-white p-3 rounded-xl font-bold flex items-center justify-center shadow hover:bg-primary/90 transition-colors"
                  title="주소 찾기"
                  aria-label="주소 찾기"
                >
                  <MdSearch className="text-xl" />
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">경작 면적 (평)</label>
              <input type="number" step="0.1" min="0" value={draft.area} onChange={e => setDraft(d => d ? { ...d, area: e.target.value } : d)} placeholder="예: 3300" className={inputClass} />
              {(() => { const c = safeAreaConvert(draft.area); return c && (
                <p className="text-sm text-gray-500 mt-1">약 {c.m2.toFixed(0)}m² ({c.ha.toFixed(2)}ha)</p>
              ); })()}
            </div>
          </div>
        ) : (
          <>
            <InfoRow label="농장명" value={profile.farmname || '-'} empty={!profile.farmname} />
            <InfoRow label="주소" value={profile.location || '-'} empty={!profile.location} />
            <InfoRow
              label="면적"
              value={(() => { const c = safeAreaConvert(profile.area); return c ? `${profile.area}평 (약 ${c.ha.toFixed(2)}ha)` : '-'; })()}
              empty={!profile.area}
            />
          </>
        )}
      </Section>

      {/* 재배 정보 */}
      <Section
        title="재배 정보"
        icon="🌾"
        isEditing={editing === 'crop'}
        onEdit={() => startEdit('crop')}
        onCancel={cancelEdit}
        onSave={saveSection}
        saving={saving}
      >
        {editing === 'crop' ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">주요 재배 작물</label>
              <select value={draft.main_crop} onChange={e => setDraft(d => d ? { ...d, main_crop: e.target.value } : d)} className={selectClass}>
                <option value="">선택하세요</option>
                {CROP_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">품종</label>
              <input type="text" value={draft.crop_variety} onChange={e => setDraft(d => d ? { ...d, crop_variety: e.target.value } : d)} placeholder="예: 홍로, 부사" className={inputClass} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">농지 유형</label>
              <select value={draft.farmland_type} onChange={e => setDraft(d => d ? { ...d, farmland_type: e.target.value } : d)} className={selectClass}>
                <option value="">선택하세요</option>
                {FARMLAND_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
        ) : (
          <>
            <InfoRow label="주요 작물" value={profile.main_crop || '-'} empty={!profile.main_crop} />
            <InfoRow label="품종" value={profile.crop_variety || '-'} empty={!profile.crop_variety} />
            <InfoRow label="농지 유형" value={profile.farmland_type || '-'} empty={!profile.farmland_type} />
          </>
        )}
      </Section>

      {/* 영농 상세 */}
      <Section
        title="영농 상세정보"
        icon="📋"
        isEditing={editing === 'detail'}
        onEdit={() => startEdit('detail')}
        onCancel={cancelEdit}
        onSave={saveSection}
        saving={saving}
      >
        {editing === 'detail' ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">농업인 유형</label>
              <select value={draft.farmer_type} onChange={e => setDraft(d => d ? { ...d, farmer_type: e.target.value } : d)} className={selectClass}>
                {FARMER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">농촌 거주 연수</label>
                <input type="number" min="0" value={draft.years_rural_residence} onChange={e => setDraft(d => d ? { ...d, years_rural_residence: e.target.value } : d)} placeholder="년" className={inputClass} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">영농 경력 연수</label>
                <input type="number" min="0" value={draft.years_farming} onChange={e => setDraft(d => d ? { ...d, years_farming: e.target.value } : d)} placeholder="년" className={inputClass} />
              </div>
            </div>
            <label className="flex items-center justify-between cursor-pointer p-3 bg-surface rounded-xl">
              <div>
                <div className="font-medium text-gray-800 text-sm">농업경영체 등록</div>
                <div className="text-xs text-gray-500">보조금 필수 요건</div>
              </div>
              <div className="relative">
                <input type="checkbox" checked={draft.has_farm_registration} onChange={e => setDraft(d => d ? { ...d, has_farm_registration: e.target.checked } : d)} className="sr-only peer" />
                <div className="w-11 h-6 rounded-full bg-gray-300 peer-checked:bg-primary transition-colors" />
                <div className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
              </div>
            </label>
            <label className="flex items-center justify-between cursor-pointer p-3 bg-surface rounded-xl">
              <div>
                <div className="font-medium text-gray-800 text-sm">농업진흥지역</div>
                <div className="text-xs text-gray-500">직불금 단가 차등</div>
              </div>
              <div className="relative">
                <input type="checkbox" checked={draft.is_promotion_area} onChange={e => setDraft(d => d ? { ...d, is_promotion_area: e.target.checked } : d)} className="sr-only peer" />
                <div className="w-11 h-6 rounded-full bg-gray-300 peer-checked:bg-primary transition-colors" />
                <div className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
              </div>
            </label>
          </div>
        ) : (
          <>
            <InfoRow label="농업인 유형" value={profile.farmer_type || '-'} />
            <InfoRow label="농촌 거주" value={profile.years_rural_residence ? `${profile.years_rural_residence}년` : '-'} empty={!profile.years_rural_residence} />
            <InfoRow label="영농 경력" value={profile.years_farming ? `${profile.years_farming}년` : '-'} empty={!profile.years_farming} />
            <InfoRow label="농업경영체" value={profile.has_farm_registration ? '등록됨' : '미등록'} badge={profile.has_farm_registration ? 'success' : 'warning'} />
            <InfoRow label="진흥지역" value={profile.is_promotion_area ? '해당' : '비해당'} />
          </>
        )}
      </Section>

      {/* 카카오 우편번호 모달 (해충진단과 동일) */}
      {isPostcodeOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="presentation"
          onClick={() => setIsPostcodeOpen(false)}
        >
          {/* Focus Trap Sentinel (Start) */}
          <div tabIndex={0} onFocus={() => postcodeCloseButtonRef.current?.focus()} aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-postcode-modal-title"
            className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden flex flex-col"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex justify-between items-center p-4 border-b border-gray-100">
              <h3 id="profile-postcode-modal-title" className="font-bold text-gray-800 text-lg">주소 검색</h3>
              <button
                type="button"
                ref={postcodeCloseButtonRef}
                aria-label="주소 검색 닫기"
                onClick={() => setIsPostcodeOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                닫기
              </button>
            </div>
            <div className="w-full h-[400px]">
              <DaumPostcode onComplete={handleCompletePostcode} style={{ height: '100%' }} />
            </div>
          </div>
          {/* Focus Trap Sentinel (End) */}
          <div tabIndex={0} onFocus={() => postcodeCloseButtonRef.current?.focus()} aria-hidden="true" />
        </div>
      )}
    </div>
  );
}

function Section({
  title, icon, children, isEditing, onEdit, onCancel, onSave, saving,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
  isEditing?: boolean;
  onEdit?: () => void;
  onCancel?: () => void;
  onSave?: () => void;
  saving?: boolean;
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title flex items-center gap-2">
          <span>{icon}</span> {title}
        </h2>
        {onEdit && !isEditing && (
          <button
            onClick={onEdit}
            className="px-3 py-1.5 text-sm font-medium text-primary border border-primary/30 rounded-lg hover:bg-primary/5 transition"
          >
            수정
          </button>
        )}
        {isEditing && (
          <div className="flex gap-2">
            <button onClick={onCancel} className="px-3 py-1.5 text-sm font-medium text-gray-500 border border-gray-300 rounded-lg hover:bg-gray-50 transition">
              취소
            </button>
            <button onClick={onSave} disabled={saving} className="px-3 py-1.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition disabled:opacity-50">
              {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        )}
      </div>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  );
}

function InfoRow({ label, value, empty, badge }: {
  label: string;
  value: string;
  empty?: boolean;
  badge?: 'success' | 'warning' | 'danger';
}) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-50 last:border-0">
      <span className="text-gray-500 text-sm">{label}</span>
      {badge ? (
        <span className={`badge-${badge}`}>{value}</span>
      ) : (
        <span className={`text-sm font-medium ${empty ? 'text-gray-300 italic' : 'text-gray-800'}`}>
          {value}
        </span>
      )}
    </div>
  );
}
