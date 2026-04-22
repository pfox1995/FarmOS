export interface FarmerProfile {
  id: string;
  name: string;
  age: number;
  farmName: string;
  region: string;
  crops: CropInfo[];
  registrationDate: string;
  phone: string;
  insuranceId: string;
  avatar: string;
}

export interface CropInfo {
  name: string;
  variety: string;
  areaPyeong: number;
}

// Diagnosis
export interface DiagnosisResult {
  id: string;
  cropName: string;
  pestName: string;
  severity: "경증" | "중증" | "심각";
  affectedArea: string;
  confidence: number;
  imageUrl: string;
  treatmentId: string;
  timestamp: string;
  guardrailTriggered: boolean;
}

export interface TreatmentRecommendation {
  id: string;
  method: string;
  registeredPesticides: PesticideInfo[];
  applicationTiming: string;
  safetyPeriod: string;
  mixingNotes: string;
}

export interface PesticideInfo {
  name: string;
  dosage: string;
  interval: string;
}

// IoT Sensors
export interface SensorReading {
  timestamp: string;
  soilMoisture: number;
  temperature: number;
  humidity: number;
  lightIntensity: number;
}

export interface IrrigationEvent {
  id: string;
  triggeredAt: string;
  reason: string;
  valveAction: "열림" | "닫힘";
  duration: number;
  autoTriggered: boolean;
}

export interface SensorAlert {
  id: string;
  type: "moisture" | "temperature" | "humidity" | "connection";
  severity: "정보" | "주의" | "경고" | "위험";
  message: string;
  timestamp: string;
  resolved: boolean;
}

// Reviews
export interface Review {
  id: string;
  platform: "네이버스마트스토어" | "쿠팡";
  text: string;
  rating: number;
  date: string;
  sentiment: "positive" | "negative" | "neutral";
}

export interface SentimentSummary {
  positive: number;
  negative: number;
  neutral: number;
  total: number;
}

export interface KeywordData {
  word: string;
  count: number;
  sentiment: "positive" | "negative" | "neutral";
}

export interface AIStrategy {
  id: string;
  title: string;
  description: string;
  priority: "높음" | "중간" | "낮음";
}

// Review Analysis API Types
export interface AnalysisResult {
  analysis_id: number;
  analysis_type: string;
  target_scope: string;
  review_count: number;
  sentiment_summary: SentimentSummary;
  keywords: KeywordData[];
  summary: ReviewSummary;
  trends: TrendData[];
  anomalies: AnomalyAlert[];
  processing_time_ms: number;
  llm_provider: string;
  llm_model: string;
  created_at: string | null;
}

export interface ReviewSummary {
  overall: string;
  positives: string[];
  negatives: string[];
  suggestions: string[];
}

export interface TrendData {
  week: string;
  positive: number;
  negative: number;
  neutral: number;
  total: number;
  positive_ratio: number;
  negative_ratio: number;
  neutral_ratio: number;
}

export interface AnomalyAlert {
  week: string;
  type: string;
  value: number;
  expected: number;
  deviation: number;
  message: string;
}

export interface SearchResult {
  id: string;
  text: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

export interface AnalysisSettings {
  auto_batch_enabled: boolean;
  batch_trigger_count: number;
  batch_schedule: string | null;
  default_batch_size: number;
}

// Documents
export interface DocumentTemplate {
  id: string;
  name: string;
  description: string;
  requiredFields: DocumentField[];
}

export interface DocumentField {
  fieldName: string;
  fieldType: "text" | "number" | "date" | "select";
  label: string;
  isAvailableFromProfile: boolean;
  value?: string;
}

export interface SubsidyMatch {
  id: string;
  name: string;
  eligibilityScore: number;
  deadline: string;
  amount: string;
  requirements: string[];
  matchedCriteria: string[];
  status: "신청가능" | "마감임박" | "마감";
}

export interface GeneratedDocument {
  id: string;
  templateId: string;
  title: string;
  generatedAt: string;
  fields: Record<string, string>;
  completeness: number;
  missingFields: string[];
}

// Weather
export interface WeatherForecast {
  date: string;
  condition: "맑음" | "구름많음" | "흐림" | "비" | "소나기" | "눈";
  tempHigh: number;
  tempLow: number;
  precipitation: number;
  humidity: number;
  windSpeed: number;
  icon: string;
}

export interface WeatherAlert {
  id: string;
  type: "폭우" | "폭설" | "한파" | "폭염" | "강풍";
  severity: "주의보" | "경보";
  message: string;
  startDate: string;
  endDate: string;
}

export interface FarmTask {
  id: string;
  date: string;
  title: string;
  description: string;
  type: "방제" | "관수" | "수확" | "시비" | "전정" | "관찰" | "기타";
  weatherDependent: boolean;
  recommended: boolean;
  blocked: boolean;
  blockReason?: string;
}

// Harvest
export interface GrowthData {
  date: string;
  fruitSize: number;
  colorIndex: number;
  sugarContent: number;
}

export interface YieldPrediction {
  predictedYield: number;
  unit: string;
  confidence: number;
  comparisonText: string;
  factors: string[];
}

export interface MarketPrice {
  date: string;
  price: number;
  volume: number;
}

export interface ShipTiming {
  optimalDate: string;
  expectedPrice: number;
  reasoning: string;
  alternativeDates: { date: string; price: number }[];
}

// Journal
export interface JournalEntry {
  id: string;
  date: string;
  type: "진단" | "관수" | "방제" | "수확" | "관찰" | "행정" | "기상";
  title: string;
  description: string;
  sourceModule?: string;
  photos: string[];
  sensorSnapshot?: Partial<SensorReading>;
  isAutoGenerated: boolean;
}

export interface MonthlySummary {
  month: string;
  totalIrrigations: number;
  totalDiagnoses: number;
  weatherAlertsHandled: number;
  documentsGenerated: number;
  journalEntries: number;
  highlights: string[];
}

// Scenario
export interface ScenarioEvent {
  day: number;
  module:
    | "iot"
    | "diagnosis"
    | "weather"
    | "reviews"
    | "documents"
    | "harvest"
    | "journal";
  title: string;
  description: string;
  route: string;
}

// Notification
export interface AppNotification {
  id: string;
  type: "info" | "warning" | "danger" | "success";
  title: string;
  message: string;
  timestamp: string;
  module: string;
  read: boolean;
}

// Journal API types (농업ON format)
export interface JournalEntryAPI {
  id: number;
  user_id: string;
  work_date: string;
  field_name: string;
  crop: string;
  work_stage: "사전준비" | "경운" | "파종" | "정식" | "작물관리" | "수확";
  weather: string | null;
  purchase_pesticide_type: string | null;
  purchase_pesticide_product: string | null;
  purchase_pesticide_amount: string | null;
  purchase_fertilizer_type: string | null;
  purchase_fertilizer_product: string | null;
  purchase_fertilizer_amount: string | null;
  usage_pesticide_type: string | null;
  usage_pesticide_product: string | null;
  usage_pesticide_amount: string | null;
  usage_fertilizer_type: string | null;
  usage_fertilizer_product: string | null;
  usage_fertilizer_amount: string | null;
  detail: string | null;
  raw_stt_text: string | null;
  source: "stt" | "text" | "auto";
  created_at: string;
  updated_at: string;
}

export interface JournalListResponse {
  items: JournalEntryAPI[];
  total: number;
  page: number;
  page_size: number;
}

export interface STTParseEntry {
  parsed: Partial<JournalEntryAPI>;
  confidence: Record<string, number>;
  pesticide_match?: Record<string, unknown> | null;
}

export interface STTParseResult {
  entries: STTParseEntry[];
  unparsed_text: string;
  rejected: boolean;
  reject_reason?: string | null;
}

export interface DailySummaryAPI {
  date: string;
  entry_count: number;
  stages_worked: string[];
  crops: string[];
  weather: string | null;
  missing_fields: MissingFieldAlert[];
  summary_text: string;
}

export interface MissingFieldAlert {
  entry_id: number;
  field_name: string;
  message: string;
  work_date: string | null;
  crop: string | null;
  created_at: string | null;
}

// Market (KAMIS dailySalesList)
export interface KamisItemPrice {
  product_cls_code: string; // 01:소매, 02:도매
  product_cls_name: string;
  category_code: string;
  category_name: string;
  productno: string;
  lastest_day: string;
  productName: string;
  item_name: string;
  unit: string;
  day1: string; // 당일 라벨
  dpr1: string; // 당일 가격
  day2: string; // 1일전 라벨
  dpr2: string; // 1일전 가격
  day3: string; // 1주일전 라벨
  dpr3: string; // 1주일전 가격
  day4: string; // 1개월전 라벨
  dpr4: string; // 1개월전 가격
  direction: string; // 1:상승, 2:하락, 0:변동없음
  value: string; // 등락율
}

export interface ImportantChange {
  item_name: string;
  productno: string;
  category_name: string;
  unit: string;
  currentPrice: number;
  previousPrice: number;
  changePercent: number;
  direction: "up" | "down";
}

// Manual Control (IoT 수동 제어)
export interface ControlItemState {
  active: boolean;
  led_on: boolean;
  locked: boolean;
  source: "manual" | "button" | "ai" | "rule" | "tool";
  updated_at: string | null;
}

export interface VentilationState extends ControlItemState {
  window_open_pct: number;
  fan_speed: number;
  on: boolean; // Design Ref: §3.1 — 마스터 스위치 (ESP8266 active와 별개)
}

export interface IrrigationControlState extends ControlItemState {
  valve_open: boolean;
  daily_total_L: number;
  last_watered: string | null;
  nutrient: { N: number; P: number; K: number };
}

export interface LightingState extends ControlItemState {
  on: boolean;
  brightness_pct: number;
}

export interface ShadingState extends ControlItemState {
  shade_pct: number;
  insulation_pct: number;
  on: boolean; // Design Ref: §3.1 — 마스터 스위치
}

export interface ManualControlState {
  ventilation: VentilationState;
  irrigation: IrrigationControlState;
  lighting: LightingState;
  shading: ShadingState;
}

export interface ControlCommand {
  control_type: "ventilation" | "irrigation" | "lighting" | "shading";
  action: Record<string, unknown>;
  source: "manual" | "button";
}

export interface ControlEvent {
  control_type: string;
  state: Record<string, unknown>;
  source: string;
  timestamp: string;
}

// AI Agent
export interface AIControlState {
  ventilation: { window_open_pct: number; fan_speed: number };
  irrigation: {
    valve_open: boolean;
    daily_total_L: number;
    last_watered: string | null;
    nutrient: { N: number; P: number; K: number };
  };
  lighting: { on: boolean; brightness_pct: number };
  shading: { shade_pct: number; insulation_pct: number };
}

export interface ToolCallTrace {
  tool: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
}

// turn 단위 판단 흐름 — LLM 의 reasoning + 그 turn 에서 호출한 tool 묶음.
// is_summary=true 는 루프 종료 후 강제 생성된 종합 요약 turn (tool_calls 비어 있음).
export interface ReasoningTurn {
  turn: number;
  reasoning: string;
  tool_calls: ToolCallTrace[];
  is_summary?: boolean;
}

export interface AIDecision {
  id: string;
  timestamp: string;
  control_type: string;
  action: Record<string, unknown>;
  reason: string;
  priority: string;
  source: "rule" | "llm" | "manual" | "tool";
  // 과거 레코드는 ToolCallTrace[] 평탄형, 현재는 ReasoningTurn[] turn형.
  // DB 리셋 전까지 두 shape 이 섞일 수 있음 — 모달에서 분기 렌더링.
  tool_calls?: Array<ToolCallTrace | ReasoningTurn>;
  // Design Ref §3.1 — agent-action-history 확장 (Bridge 적재 시 채워짐)
  sensor_snapshot?: {
    temperature?: number;
    humidity?: number;
    light_intensity?: number;
    soil_moisture?: number;
    timestamp?: string;
    [k: string]: unknown;
  };
  duration_ms?: number;
  created_at?: string;
}

// Design Ref §3.1, §4.1 — 요약 응답
export interface ActivitySummary {
  range: "today" | "7d" | "30d";
  total: number;
  by_control_type: Record<string, number>;
  by_source: Record<string, number>;
  by_priority: Record<string, number>;
  avg_duration_ms: number | null;
  latest_at: string | null;
  generated_at: string;
}

// Design Ref §4.2 — 목록 + (timestamp, id) 복합 keyset pagination 응답
export interface DecisionListResponse {
  items: AIDecision[];
  next_cursor: string | null;
  next_cursor_id: string | null;
  has_more: boolean;
}

export interface CropProfile {
  name: string;
  growth_stage: string;
  optimal_temp: [number, number];
  optimal_humidity: [number, number];
  optimal_light_hours: number;
  nutrient_ratio: { N: number; P: number; K: number };
}

export interface AIAgentStatus {
  enabled: boolean;
  control_state: AIControlState;
  crop_profile: CropProfile;
  latest_decision: AIDecision | null;
  total_decisions: number;
}
