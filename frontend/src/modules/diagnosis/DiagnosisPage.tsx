import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { MdCameraAlt, MdHistory, MdCheckCircle, MdChat, MdInfoOutline, MdDeleteOutline, MdSearch } from 'react-icons/md';
import toast from 'react-hot-toast';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import DaumPostcode from 'react-daum-postcode';
import { formatDaumAddress, type DaumPostcodeData } from '@/utils/daumAddress';

const REGIONS = [
  "서울", "인천", "대전", "대구", "광주", "부산", "울산", "세종",
  "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
];

const CROPS = [
  "감자", "고추", "참깨", "파", "배추", "콩", "양배추", "오이", "옥수수", "팥", "토마토", "벼"
];

const PESTS = [
  "해충없음", "벼룩잎벌레", "비단노린재", "이십팔점박이무당벌레", "참외덩굴무늬벌레",
  "배추흰나비", "먹노린재", "배추좀나방", "톱다리개미허리노린재", "파밤나방",
  "담배가루이", "담배거세미나방", "복숭아혹진딧물", "무잎벌", "목화바둑명나방",
  "꽃노랑총채벌레", "검거세미밤나방", "도둑나방"
];

const API_BASE = 'http://localhost:8000/api/v1/diagnosis';

const TIPS = [
  "작물의 잎 이면까지 꼼꼼히 촬영하면 더 정확한 해충 진단이 가능합니다.",
  "해충 발견 즉시 사진을 찍어 진단하면 피해를 최소화할 수 있습니다.",
  "바람이 부는 날에는 농약 살포를 피하는 것이 좋습니다.",
  "서로 다른 약제를 혼용할 때는 반드시 제품 라벨의 혼용 가이드를 확인하세요.",
  "비가 온 직후에는 병해가 확산될 수 있으니 작물을 꼼꼼히 살피세요.",
  "농약은 권장 희석 배수를 정확히 지켜야 작물 약해를 예방할 수 있습니다.",
  "해충 방제는 예찰을 통한 초기 대응이 가장 효과적입니다.",
  "수확을 앞둔 작물은 잔류 농약 안전 기준을 위해 사용 가능 시기를 꼭 확인하세요.",
  "노린재류는 주로 아침, 저녁 시간에 잎 뒷면에 숨어 활동합니다.",
  "시설 하우스에서는 주기적인 환기로 습도를 낮춰 곰팡이병을 예방하세요.",
  "NCPMS 방제 지침은 국가 공인 데이터를 기반으로 작성됩니다.",
  "기상청 데이터 연동을 통해 현재 날씨에 맞는 최적의 살포 시기를 추천합니다."
];

const LOADING_MESSAGES = [
  "진단 이미지 특징점 전처리 중...",
  "AI 모델 기반 해충 탐지 수행 중...",
  "해충 데이터베이스와 대조 중...",
  "NCPMS 방제 지침 데이터 연동 중...",
  "농약 처방 데이터베이스 대조 중...",
  "기상청 데이터 기반 방제 적합도 분석 중...",
  "최적의 농약 정보 검색 중...",
  "최종 진단 리포트 생성 중..."
];

export default function DiagnosisPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [selectedRegion, setSelectedRegion] = useState("");
  const [selectedCrop, setSelectedCrop] = useState("");
  const [testPest, setTestPest] = useState(PESTS[1]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [randomTip, setRandomTip] = useState(TIPS[0]);
  const [loadingMessage, setLoadingMessage] = useState(LOADING_MESSAGES[0]);
  const [history, setHistory] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  
  const [isPostcodeOpen, setIsPostcodeOpen] = useState(false);
  const postcodeCloseButtonRef = useRef<HTMLButtonElement | null>(null);
  
  const handleCompletePostcode = (data: DaumPostcodeData) => {
    setSelectedRegion(formatDaumAddress(data));
    setIsPostcodeOpen(false);
  };
  
  const abortControllerRef = useRef<AbortController | null>(null);

  const cancelDiagnosis = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsAnalyzing(false);
  };

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (isAnalyzing) {
      interval = setInterval(() => {
        setLoadingMessage(prev => {
          let nextIndex = Math.floor(Math.random() * LOADING_MESSAGES.length);
          while (LOADING_MESSAGES[nextIndex] === prev) {
            nextIndex = Math.floor(Math.random() * LOADING_MESSAGES.length);
          }
          return LOADING_MESSAGES[nextIndex];
        });
      }, 2500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isAnalyzing]);

  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_BASE}/history`, { credentials: 'include' });
      if (!response.ok) throw new Error('Failed to fetch');
      const data = await response.json();
      setHistory(data);
    } catch (error) {
      console.error("Failed to fetch history:", error);
    }
  };

  useEffect(() => {
    if (user) {
      // 프론트엔드의 user 객체에는 실제 DB의 location 필드가 포함되어 있습니다.
      // 짧게 변환된 location_category 대신, 상세 주소가 포함된 원본 location을 사용하여
      // 카카오 지오코딩 및 기상청 연동에 필요한 전체 좌표 정보를 얻습니다.
      const displayRegion = user.location || "";
      setSelectedRegion(displayRegion);
      setSelectedCrop(user.main_crop || "배추");
      fetchHistory();
    }
  }, [user]);

  const toggleSelect = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === history.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(history.map(h => h.id));
    }
  };

  const deleteSelected = async () => {
    if (selectedIds.length === 0) return;
    
    try {
      await Promise.all(
        selectedIds.map(id => 
          fetch(`${API_BASE}/history/${id}`, {
            method: 'DELETE',
            credentials: 'include',
          })
        )
      );
      setHistory(prev => prev.filter(h => !selectedIds.includes(h.id)));
      setSelectedIds([]);
    } catch (error) {
      console.error("Delete failed:", error);
    }
  };

  const deleteOne = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const response = await fetch(`${API_BASE}/history/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Delete failed');
      setHistory(prev => prev.filter(h => h.id !== id));
      setSelectedIds(prev => prev.filter(i => i !== id));
    } catch (error) {
      console.error("Delete failed:", error);
    }
  };

  const startDiagnosis = async (isTest = false) => {
    if (!selectedRegion && !isTest) {
      toast.error('정확한 기상청 데이터 연동을 위해 주소를 입력해주세요.');
      setIsPostcodeOpen(true);
      return;
    }

    setIsAnalyzing(true);
    setRandomTip(TIPS[Math.floor(Math.random() * TIPS.length)]);
    setLoadingMessage(LOADING_MESSAGES[Math.floor(Math.random() * LOADING_MESSAGES.length)]);

    // 기존 진행 중인 요청 캔슬 및 새 AbortController 할당
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (!isTest) {
      toast('현재 이미지 자동 판독(VLM) 연동 전입니다. 선택된 해충으로 임시 진단합니다.', {
        icon: '⚠️'
      });
    }

    const payload = {
      pest: testPest,
      crop: selectedCrop || "배추",
      region: selectedRegion || "서울"
    };

    // 일반 POST 응답 처리
    try {
      const res = await fetch(`${API_BASE}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      if (!res.ok) {
        throw new Error('서버 응답 오류가 발생했습니다.');
      }

      const responseData = await res.json();
      const savedData = responseData.data || responseData;

      if (!savedData || !savedData.id) {
        throw new Error('진단 데이터를 생성하지 못했습니다.');
      }

      // 목록을 갱신하되, 이동을 차단하지 않도록 비동기로 처리하거나 생략 가능 (채팅에서 돌아올 때 다시 부름)
      fetchHistory();
      
      navigate('/diagnosis/chat', { state: { diagnosisContext: savedData } });
      
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log("Diagnosis aborted by user");
        return;
      }
      console.error("Save error:", err);
      toast.error(err.message || 'AI 진단 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      setIsAnalyzing(false);
    } finally {
      // 최신 요청의 종료에서만 로딩 상태를 내린다.
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        // 성공 시에는 navigate로 인해 컴포넌트가 언마운트되므로 
        // finally에서 명시적으로 false 처리를 하지 않아도 무방하나 안전을 위해 에러 시에만 수행하도록 catch로 이동하거나 유지
        setIsAnalyzing(false);
      }
    }
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

  const onDrop = useCallback(() => {
    startDiagnosis(false);
  }, [selectedCrop, selectedRegion, testPest]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpg', '.jpeg', '.png'] },
    maxFiles: 1,
  });

  const isAutoFilled = user?.location_category && user?.main_crop;

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      <div className="card bg-white border border-gray-100 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <MdInfoOutline className="text-primary" />
            진단 환경 설정
          </h2>
          {isAutoFilled && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-50 text-green-600 text-xs font-bold rounded-full border border-green-100">
              <MdCheckCircle className="text-sm" />
              내 농장 정보 적용됨
            </span>
          )}
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5 flex flex-col">
            <label className="text-xs font-bold text-gray-400 ml-1">지역/상세주소 (기상청 연동)</label>
            <div className="flex gap-2">
              <input 
                type="text"
                readOnly
                placeholder="주소를 검색하세요"
                value={selectedRegion}
                onClick={() => setIsPostcodeOpen(true)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setIsPostcodeOpen(true);
                  }
                }}
                tabIndex={0}
                className="w-full p-3 rounded-xl border border-gray-200 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-primary/20 transition-all outline-none cursor-pointer"
              />
              <button 
                type="button"
                onClick={() => setIsPostcodeOpen(true)}
                className="bg-primary text-white p-3 rounded-xl font-bold flex items-center justify-center shadow hover:bg-primary/90 transition-colors"
                title="주소 찾기"
                aria-label="주소 찾기"
              >
                <MdSearch className="text-xl" />
              </button>
            </div>
            
            {isPostcodeOpen && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
                role="presentation"
                onClick={() => setIsPostcodeOpen(false)}
              >
                <div
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="diagnosis-postcode-modal-title"
                  className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden flex flex-col"
                  onClick={(event) => event.stopPropagation()}
                >
                  <div className="flex justify-between items-center p-4 border-b border-gray-100">
                    <h3 id="diagnosis-postcode-modal-title" className="font-bold text-gray-800 text-lg">주소 검색</h3>
                    <button 
                      type="button"
                      ref={postcodeCloseButtonRef}
                      aria-label="주소 검색 닫기"
                      onClick={() => setIsPostcodeOpen(false)}
                      className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      ✕ 닫기
                    </button>
                  </div>
                  <div className="w-full h-[400px]">
                    <DaumPostcode onComplete={handleCompletePostcode} style={{ height: '100%' }} />
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-gray-400 ml-1">작물 (농약 안전정보 연동)</label>
            <select 
              value={selectedCrop} 
              onChange={(e) => setSelectedCrop(e.target.value)}
              className="w-full p-3 rounded-xl border border-gray-200 bg-gray-50 focus:bg-white focus:ring-2 focus:ring-primary/20 transition-all outline-none cursor-pointer"
            >
              <option value="" disabled>작물 선택</option>
              {CROPS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div
        {...getRootProps()}
        className={`card border-2 border-dashed cursor-pointer transition-all text-center py-16 ${
          isDragActive ? 'border-primary bg-primary/5' : 'border-gray-200 hover:border-primary/40 hover:bg-gray-50/50'
        }`}
      >
        <input {...getInputProps()} />
        <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <MdCameraAlt className="text-4xl text-primary" />
        </div>
        <p className="text-xl font-bold text-gray-800">
          {isDragActive ? '여기에 사진을 놓으세요!' : '해충 사진을 업로드하세요'}
        </p>
        <p className="text-sm text-gray-400 mt-2 max-w-xs mx-auto">
          작물의 특징이나 해충이 잘 보이도록 근접 촬영한 사진일수록 정확합니다
        </p>
        <div className="flex justify-center">
          <button className="btn-primary mt-6 !px-8">
            사진 선택하기
          </button>
        </div>
      </div>

      <div className="card bg-amber-50/50 border border-amber-100 border-dashed">
        <div className="flex items-center gap-2 mb-4 text-amber-700 font-bold text-sm">
          <span className="px-2 py-0.5 bg-amber-200 rounded-md text-[10px]">FIXED</span>
          임시 VLM 진단 테스트 (해충 강제 지정)
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <select 
            value={testPest} 
            onChange={(e) => setTestPest(e.target.value)}
            className="flex-1 p-3 rounded-xl border border-amber-200 bg-white focus:ring-2 focus:ring-amber-200 outline-none cursor-pointer"
          >
            {PESTS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button 
            onClick={() => startDiagnosis(true)}
            className="bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 px-6 rounded-xl transition-all shadow-sm shadow-amber-200 flex items-center justify-center gap-2 cursor-pointer"
          >
            <MdChat /> 테스트 진단 시작
          </button>
        </div>
      </div>

      <div className="card border border-gray-100">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-gray-100 rounded-lg">
              <MdHistory className="text-xl text-gray-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-800">최근 진단 기록</h3>
          </div>
          
          {history.length > 0 && (
            <div className="flex items-center gap-3">
              <button 
                onClick={toggleSelectAll}
                className="text-xs font-bold text-gray-400 hover:text-primary transition-colors cursor-pointer"
              >
                {selectedIds.length === history.length ? "전체 해제" : "전체 선택"}
              </button>
              {selectedIds.length > 0 && (
                <button 
                  onClick={deleteSelected}
                  className="px-3 py-1.5 bg-red-50 text-red-600 text-xs font-bold rounded-lg border border-red-100 hover:bg-red-100 transition-all flex items-center gap-1"
                >
                  <MdDeleteOutline className="text-sm" />
                  {selectedIds.length}개 삭제
                </button>
              )}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3">
          {history.length === 0 ? (
            <div className="py-20 text-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-200">
              <p className="text-gray-400 text-sm">최근 진단 내역이 없습니다.</p>
            </div>
          ) : history.map(record => (
            <div
              key={record.id}
              className={`group relative w-full text-left p-4 rounded-2xl border transition-all cursor-default flex items-center justify-between shadow-sm
                ${selectedIds.includes(record.id) 
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/20' 
                  : 'border-primary/20 bg-white'
                }`}
            >
              <div className="flex items-center gap-4 flex-1">
                <div 
                  onClick={(e) => toggleSelect(e, record.id)}
                  className={`w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all flex-shrink-0 cursor-pointer
                    ${selectedIds.includes(record.id) 
                      ? 'bg-primary border-primary text-white scale-110' 
                      : 'bg-white border-primary/40'
                    }`}
                >
                  {selectedIds.includes(record.id) && <MdCheckCircle className="text-lg" />}
                </div>

                <div 
                  className="flex-1 space-y-1 cursor-pointer group/content"
                  onClick={() => navigate('/diagnosis/chat', { 
                    state: { 
                      diagnosisContext: record,
                      fromHistory: true 
                    } 
                  })}
                >
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-primary text-white transition-colors">
                      {record.crop}
                    </span>
                    <span className="font-bold text-primary transition-colors">
                      {record.pest}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {record.region} · {record.date ? record.date : new Date(record.created_at).toLocaleDateString()} 
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button 
                  onClick={(e) => deleteOne(e, record.id)}
                  className="w-9 h-9 rounded-xl flex items-center justify-center text-red-500 bg-red-50 border border-red-100 transition-all cursor-pointer hover:border-red-500"
                  title="기록 삭제"
                >
                  <MdDeleteOutline className="text-xl" />
                </button>
                
                <div 
                  className="flex items-center justify-center w-10 h-10 rounded-full transition-all shadow-sm bg-green-50 text-primary cursor-pointer border border-green-100 hover:border-primary"
                  onClick={() => navigate('/diagnosis/chat', { 
                    state: { 
                      diagnosisContext: record,
                      fromHistory: true 
                    } 
                  })}
                  title="진단 상세 채팅"
                >
                  <MdChat className="text-xl" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <AnimatePresence>
        {isAnalyzing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-sm"
          >
            <div className="text-center space-y-8 max-w-sm px-6">
              <div className="relative w-32 h-32 mx-auto">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
                  className="absolute inset-0 border-4 border-primary/10 border-t-primary rounded-full"
                />
                <motion.div
                  animate={{ rotate: -360 }}
                  transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
                  className="absolute inset-4 border-4 border-primary-light/10 border-b-primary-light rounded-full"
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-4xl animate-bounce">🌱</span>
                </div>
              </div>

              <div className="space-y-4">
                <h2 className="text-2xl font-bold text-gray-800">AI 분석 진행 중</h2>
                <p className="text-primary font-medium animate-pulse">
                  {loadingMessage}
                </p>
              </div>

              <div className="p-4 bg-primary/5 rounded-2xl border border-primary/10">
                <p className="text-xs text-gray-500 leading-relaxed">
                  <span className="font-bold text-primary block mb-1">💡 알고 계셨나요?</span>
                  {randomTip}
                </p>
              </div>

              <div className="pt-4">
                <button
                  onClick={cancelDiagnosis}
                  className="px-6 py-2.5 bg-white text-gray-500 font-bold rounded-xl border border-gray-200 shadow-sm hover:bg-gray-50 hover:text-red-500 transition-all"
                >
                  진단 취소 및 돌아가기
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
