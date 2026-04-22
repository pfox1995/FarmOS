import { useState, useEffect, useMemo, memo, useCallback } from 'react';
import { MdWaterDrop, MdThermostat, MdOpacity, MdWbSunny, MdWarning, MdWifiOff, MdClose } from 'react-icons/md';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell } from 'recharts';
import { useSensorData } from '@/hooks/useSensorData';
import AIAgentPanel from './AIAgentPanel';
import ManualControlPanel from './ManualControlPanel';
import DateRangeFilter, {
  type DateRangeValue,
} from '@/components/DateRangeFilter';

// 날짜 범위로 timestamp 기반 배열 필터. since/until 둘 다 null 이면 원본 반환.
function filterByDateRange<T>(
  items: T[],
  getTimestamp: (item: T) => string,
  since: Date | null,
  until: Date | null,
): T[] {
  if (!since && !until) return items;
  return items.filter((item) => {
    const ts = new Date(getTimestamp(item)).getTime();
    if (since && ts < since.getTime()) return false;
    if (until && ts > until.getTime()) return false;
    return true;
  });
}

function SensorCard({ icon: Icon, label, value, unit, color, threshold, warning, disabled }: {
  icon: React.ElementType; label: string; value: number | null; unit: string;
  color: string; threshold?: number; warning?: boolean; disabled?: boolean;
}) {
  return (
    <div className={`card !p-4 sm:!p-6 ${
      disabled ? 'opacity-50 grayscale' :
      warning ? 'ring-2 ring-warning/60 bg-yellow-50/30' : ''
    }`}>
      <div className="flex items-center justify-between">
        <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center ${disabled ? 'bg-gray-300' : color}`}>
          <Icon className="text-xl sm:text-2xl text-white" />
        </div>
        {!disabled && warning && (
          <span className="flex items-center gap-1 text-warning text-xs sm:text-sm font-semibold">
            <MdWarning className="text-base sm:text-lg" /> 주의
          </span>
        )}
        {disabled && (
          <span className="flex items-center gap-1 text-gray-400 text-xs font-semibold">
            <MdWifiOff className="text-base" /> 비활성
          </span>
        )}
      </div>
      <p className={`text-sm sm:text-base mt-2 sm:mt-3 font-medium ${disabled ? 'text-gray-400' : 'text-gray-600'}`}>{label}</p>
      <p className={`text-2xl sm:text-4xl font-bold mt-1 tracking-tight ${disabled ? 'text-gray-300' : 'text-gray-900'}`}>
        {value !== null ? value.toFixed(1) : '--.-'}
        <span className="text-base sm:text-xl text-gray-400 ml-0.5">{unit}</span>
      </p>
      {threshold && !disabled && value !== null && (
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${value < threshold ? 'bg-warning' : 'bg-success'}`}
              style={{ width: `${Math.min(100, (value / 100) * 100)}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">기준 {threshold}{unit}</span>
        </div>
      )}
      {threshold && disabled && (
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden" />
          <span className="text-xs text-gray-300 whitespace-nowrap">기준 {threshold}{unit}</span>
        </div>
      )}
    </div>
  );
}

type ChartData = { time: string; soilMoisture: number; temperature: number; humidity: number }[];
const IoTCharts = memo(function IoTCharts({ chartData }: { chartData: ChartData }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (chartData.length === 0) {
    return (
      <div className="card !p-8 text-center text-gray-400">
        <p className="text-lg">센서 데이터가 아직 없습니다</p>
        <p className="text-sm mt-1">ESP8266에서 데이터를 전송하면 차트가 표시됩니다</p>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <h3 className="section-title mb-4">토양 습도 추이</h3>
        {mounted && (
          <div className="h-[200px] sm:h-[280px] overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <ReferenceLine y={55} stroke="#EAB308" strokeDasharray="5 5" label="임계값 55%" />
                <Line type="monotone" dataKey="soilMoisture" stroke="#3B82F6" strokeWidth={2} dot={false} name="토양 습도 (%)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="card">
        <h3 className="section-title mb-4">온도 · 습도 추이</h3>
        {mounted && (
          <div className="h-[200px] sm:h-[250px] overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="temperature" stroke="#EF4444" strokeWidth={2} dot={false} name="온도 (°C)" />
                <Line type="monotone" dataKey="humidity" stroke="#14B8A6" strokeWidth={2} dot={false} name="습도 (%)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </>
  );
});

interface IrrigationEvent {
  id: string;
  triggeredAt: string;
  reason: string;
  valveAction: '열림' | '닫힘';
  duration: number;
  autoTriggered: boolean;
}

interface IrrigationModalProps {
  irrigations: IrrigationEvent[];
  onClose: () => void;
}

function IrrigationModal({ irrigations, onClose }: IrrigationModalProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // ESC 키로 닫기
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 모달 열릴 때 스크롤 방지
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const chartData = irrigations.map((e) => ({
    label: new Date(e.triggeredAt).toLocaleString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
    duration: e.duration > 0 ? e.duration : 1,
    valveAction: e.valveAction,
    reason: e.reason,
  }));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">관수 이력 상세</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            aria-label="닫기"
          >
            <MdClose className="text-xl" />
          </button>
        </div>

        {/* 그래프 영역 */}
        <div className="px-6 pt-5 pb-2">
          <p className="text-sm font-medium text-gray-600 mb-3">관수 지속 시간 (분)</p>
          {mounted && chartData.length > 0 ? (
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: '#9CA3AF' }}
                    angle={-35}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} allowDecimals={false} />
                  <Tooltip
                    formatter={(value: number, _name: string, props: any) => [
                      `${value}분`,
                      `밸브 ${props.payload.valveAction}`,
                    ]}
                    labelFormatter={(label: string) => label}
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  />
                  <Bar dataKey="duration" radius={[4, 4, 0, 0]} maxBarSize={40}>
                    {chartData.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={entry.valveAction === '열림' ? '#3B82F6' : '#9CA3AF'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gray-300 text-sm">
              데이터 없음
            </div>
          )}
          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-blue-500 inline-block" />
              밸브 열림
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-gray-400 inline-block" />
              밸브 닫힘
            </span>
          </div>
        </div>

        {/* 리스트 영역 (스크롤) */}
        <div className="px-6 pb-6 overflow-y-auto flex-1 mt-2">
          <p className="text-sm font-medium text-gray-600 mb-2">전체 이력 ({irrigations.length}건)</p>
          <div className="space-y-2">
            {irrigations.map((e) => (
              <div key={e.id} className="flex items-center gap-3 p-3 rounded-xl bg-gray-50">
                <span className={`w-3 h-3 rounded-full flex-shrink-0 ${e.valveAction === '열림' ? 'bg-blue-500' : 'bg-gray-400'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{e.reason}</p>
                  <p className="text-xs text-gray-400">
                    {new Date(e.triggeredAt).toLocaleString('ko-KR', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                    {e.duration > 0 && ` · ${e.duration}분`}
                    {e.autoTriggered && <span className="ml-1 text-[#2D5F2D]">· 자동</span>}
                  </p>
                </div>
                <span className={`badge text-xs flex-shrink-0 ${e.valveAction === '열림' ? 'badge-info' : 'badge-success'}`}>
                  밸브 {e.valveAction}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const INITIAL_COUNT = 3;

interface SensorAlertItem {
  id: string;
  timestamp: string;
  severity: string;
  message: string;
  resolved?: boolean;
}

function AlertsModal({
  alerts,
  onClose,
}: {
  alerts: SensorAlertItem[];
  onClose: () => void;
}) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">센서 알림 상세</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            aria-label="닫기"
          >
            <MdClose className="text-xl" />
          </button>
        </div>
        <div className="px-6 py-4 overflow-y-auto flex-1">
          <p className="text-sm font-medium text-gray-600 mb-2">
            전체 알림 ({alerts.length}건)
          </p>
          {alerts.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-8">
              해당 기간에 알림이 없습니다
            </p>
          ) : (
            <div className="space-y-2">
              {alerts.map((a) => (
                <div
                  key={a.id}
                  className={`flex items-center gap-3 p-3 rounded-xl ${
                    a.severity === '위험' || a.severity === '경고'
                      ? 'bg-red-50'
                      : a.severity === '주의'
                      ? 'bg-yellow-50'
                      : 'bg-blue-50'
                  }`}
                >
                  <span
                    className={`badge text-xs flex-shrink-0 ${
                      a.severity === '위험' || a.severity === '경고'
                        ? 'badge-danger'
                        : a.severity === '주의'
                        ? 'badge-warning'
                        : 'badge-info'
                    }`}
                  >
                    {a.severity}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{a.message}</p>
                    <p className="text-xs text-gray-400">
                      {new Date(a.timestamp).toLocaleString('ko-KR', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                  {a.resolved && (
                    <span className="text-xs text-green-600 flex-shrink-0">해결됨</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function IoTDashboardPage() {
  const { latest, history, alerts, irrigations, connected } = useSensorData();
  const hasData = !!latest;
  const inactive = !connected || !hasData;

  const [irrigationModalOpen, setIrrigationModalOpen] = useState(false);
  const [alertsModalOpen, setAlertsModalOpen] = useState(false);

  const handleOpenIrrigationModal = useCallback(() => setIrrigationModalOpen(true), []);
  const handleCloseIrrigationModal = useCallback(() => setIrrigationModalOpen(false), []);
  const handleOpenAlertsModal = useCallback(() => setAlertsModalOpen(true), []);
  const handleCloseAlertsModal = useCallback(() => setAlertsModalOpen(false), []);

  // 관수 이력 · 센서 알림 날짜 범위 필터 (클라이언트 사이드)
  const [irrigationRange, setIrrigationRange] = useState<DateRangeValue>({
    since: null,
    until: null,
    preset: 'all',
  });
  const [alertsRange, setAlertsRange] = useState<DateRangeValue>({
    since: null,
    until: null,
    preset: 'all',
  });

  const filteredIrrigations = useMemo(
    () =>
      filterByDateRange(
        irrigations,
        (e: any) => e.triggeredAt,
        irrigationRange.since,
        irrigationRange.until,
      ),
    [irrigations, irrigationRange.since, irrigationRange.until],
  );

  const filteredAlerts = useMemo(
    () =>
      filterByDateRange(
        alerts,
        (a: any) => a.timestamp,
        alertsRange.since,
        alertsRange.until,
      ),
    [alerts, alertsRange.since, alertsRange.until],
  );

  const chartData = useMemo(() =>
    history.map(r => ({
      time: new Date(r.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }),
      soilMoisture: r.soilMoisture,
      temperature: r.temperature,
      humidity: r.humidity,
    })),
  [history]);

  return (
    <div className="space-y-6">
      {/* Connection status */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        {connected && hasData ? (
          <>
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-success"></span>
            </span>
            <span className="font-medium text-success">연결됨</span>
            <span>
              마지막 수신: {new Date(latest!.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </>
        ) : connected && !hasData ? (
          <>
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-400"></span>
            </span>
            <span className="font-medium text-yellow-600">서버 연결됨 · 센서 데이터 대기 중</span>
          </>
        ) : (
          <>
            <MdWifiOff className="text-lg text-gray-400" />
            <span className="font-medium text-gray-400">백엔드 연결 안 됨</span>
            <span className="text-xs text-gray-300">http://localhost:8000</span>
          </>
        )}
      </div>

      {/* Sensor Cards — always visible, disabled when no data */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SensorCard
          icon={MdWaterDrop} label="토양 습도"
          value={hasData ? latest!.soilMoisture : null} unit="%"
          color="bg-blue-500" threshold={55}
          warning={hasData && latest!.soilMoisture < 55}
          disabled={inactive}
        />
        <SensorCard
          icon={MdThermostat} label="온도"
          value={hasData ? latest!.temperature : null} unit="°C"
          color="bg-red-400"
          disabled={inactive}
        />
        <SensorCard
          icon={MdOpacity} label="대기 습도"
          value={hasData ? latest!.humidity : null} unit="%"
          color="bg-teal-500"
          warning={hasData && latest!.humidity > 90}
          disabled={inactive}
        />
        <SensorCard
          icon={MdWbSunny} label="조도"
          value={hasData ? latest!.lightIntensity : null} unit=" lux"
          color="bg-amber-500"
          disabled={inactive}
        />
      </div>

      <IoTCharts chartData={chartData} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Irrigation Events */}
        <div className={`card ${inactive ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
            <h3 className="section-title !mb-0">관수 이력</h3>
            <DateRangeFilter
              value={irrigationRange}
              onChange={setIrrigationRange}
            />
          </div>
          {filteredIrrigations.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">
              {irrigations.length === 0
                ? '관수 이력이 없습니다'
                : '해당 기간에 관수 이력이 없습니다'}
            </p>
          ) : (
            <>
              <div className="space-y-2">
                {filteredIrrigations.slice(0, INITIAL_COUNT).map((e: any) => (
                  <div key={e.id} className="flex items-center gap-3 p-3 rounded-xl bg-gray-50">
                    <span className={`w-3 h-3 rounded-full ${e.valveAction === '열림' ? 'bg-blue-500' : 'bg-gray-400'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{e.reason}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(e.triggeredAt).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        {e.duration > 0 && ` · ${e.duration}분`}
                      </p>
                    </div>
                    <span className={`badge text-xs ${e.valveAction === '열림' ? 'badge-info' : 'badge-success'}`}>
                      밸브 {e.valveAction}
                    </span>
                  </div>
                ))}
              </div>
              {filteredIrrigations.length > INITIAL_COUNT && (
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleOpenIrrigationModal}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[#2D5F2D] text-[#2D5F2D] hover:bg-[#2D5F2D] hover:text-white transition-colors"
                  >
                    더보기 ({filteredIrrigations.length - INITIAL_COUNT}건 더)
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Alerts */}
        <div className={`card ${inactive ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
            <h3 className="section-title !mb-0">센서 알림</h3>
            <DateRangeFilter value={alertsRange} onChange={setAlertsRange} />
          </div>
          {filteredAlerts.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">
              {alerts.length === 0
                ? '알림이 없습니다'
                : '해당 기간에 알림이 없습니다'}
            </p>
          ) : (
            <>
              <div className="space-y-2">
                {filteredAlerts.slice(0, INITIAL_COUNT).map((a: any) => (
                  <div key={a.id} className={`flex items-center gap-3 p-3 rounded-xl ${
                    a.severity === '위험' || a.severity === '경고' ? 'bg-red-50' :
                    a.severity === '주의' ? 'bg-yellow-50' : 'bg-blue-50'
                  }`}>
                    <span className={`badge text-xs ${
                      a.severity === '위험' || a.severity === '경고' ? 'badge-danger' :
                      a.severity === '주의' ? 'badge-warning' : 'badge-info'
                    }`}>
                      {a.severity}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800">{a.message}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(a.timestamp).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                    {a.resolved && <span className="text-xs text-green-600">해결됨</span>}
                  </div>
                ))}
              </div>
              {filteredAlerts.length > INITIAL_COUNT && (
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={handleOpenAlertsModal}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[#2D5F2D] text-[#2D5F2D] hover:bg-[#2D5F2D] hover:text-white transition-colors"
                  >
                    더보기 ({filteredAlerts.length - INITIAL_COUNT}건 더)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* 수동 제어 패널 */}
      <ManualControlPanel />

      {/* AI Agent 제어 패널 */}
      <AIAgentPanel />

      {irrigationModalOpen && (
        <IrrigationModal
          irrigations={filteredIrrigations as IrrigationEvent[]}
          onClose={handleCloseIrrigationModal}
        />
      )}
      {alertsModalOpen && (
        <AlertsModal
          alerts={filteredAlerts as SensorAlertItem[]}
          onClose={handleCloseAlertsModal}
        />
      )}
    </div>
  );
}
