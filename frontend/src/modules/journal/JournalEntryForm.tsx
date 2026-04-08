import { useState, forwardRef, useImperativeHandle } from "react";
import { MdExpandMore, MdExpandLess, MdMic } from "react-icons/md";
import type { JournalEntryAPI } from "@/types";

export interface JournalEntryFormHandle {
  getFormData: () => Record<string, unknown>;
}

const WORK_STAGES = [
  "사전준비",
  "경운",
  "파종",
  "정식",
  "작물관리",
  "수확",
] as const;
const WEATHER_OPTIONS = ["맑음", "흐림", "비", "눈", "바람"];

interface Props {
  initialData?: JournalEntryAPI | null;
  isEdit?: boolean;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  onRequestRecord?: () => void;
  submitLabel?: string;
  headerSlot?: React.ReactNode;
}

const JournalEntryForm = forwardRef<JournalEntryFormHandle, Props>(
  function JournalEntryForm(
    {
      initialData,
      isEdit = false,
      onSubmit,
      onCancel,
      onRequestRecord,
      submitLabel,
      headerSlot,
    },
    ref,
  ) {
    const [workDate, setWorkDate] = useState(
      initialData?.work_date || new Date().toISOString().slice(0, 10),
    );
    const [fieldName, setFieldName] = useState(initialData?.field_name || "");
    const [crop, setCrop] = useState(initialData?.crop || "");
    const [workStage, setWorkStage] = useState(
      initialData?.work_stage || "작물관리",
    );
    const [weather, setWeather] = useState(initialData?.weather || "");
    const [detail, setDetail] = useState(initialData?.detail || "");

    // 농약/비료 사용
    const [usagePesticideProduct, setUsagePesticideProduct] = useState(
      initialData?.usage_pesticide_product || "",
    );
    const [usagePesticideAmount, setUsagePesticideAmount] = useState(
      initialData?.usage_pesticide_amount || "",
    );
    const [usageFertilizerProduct, setUsageFertilizerProduct] = useState(
      initialData?.usage_fertilizer_product || "",
    );
    const [usageFertilizerAmount, setUsageFertilizerAmount] = useState(
      initialData?.usage_fertilizer_amount || "",
    );

    const [showChemicals, setShowChemicals] = useState(
      !!(
        initialData?.usage_pesticide_product ||
        initialData?.usage_fertilizer_product
      ),
    );
    const [submitting, setSubmitting] = useState(false);

    const buildBody = (): Record<string, unknown> => ({
      work_date: workDate,
      field_name: fieldName.trim(),
      crop: crop.trim(),
      work_stage: workStage,
      weather: weather || null,
      usage_pesticide_product: usagePesticideProduct || null,
      usage_pesticide_amount: usagePesticideAmount || null,
      usage_fertilizer_product: usageFertilizerProduct || null,
      usage_fertilizer_amount: usageFertilizerAmount || null,
      detail: detail || null,
      source: "text",
    });

    useImperativeHandle(ref, () => ({ getFormData: buildBody }));

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!fieldName.trim() || !crop.trim()) return;

      setSubmitting(true);
      await onSubmit(buildBody());
      setSubmitting(false);
    };

    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        {headerSlot}
        {/* 필수 필드 */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              작업일 *
            </label>
            <input
              type="date"
              value={workDate}
              onChange={(e) => setWorkDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              필지 *
            </label>
            <input
              type="text"
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              placeholder="예: 1번 필지, 하우스 2호"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              작목 *
            </label>
            <input
              type="text"
              value={crop}
              onChange={(e) => setCrop(e.target.value)}
              placeholder="예: 사과, 고추, 토마토"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              작업단계 *
            </label>
            <select
              value={workStage}
              onChange={(e) => setWorkStage(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {WORK_STAGES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 날씨 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            날씨
          </label>
          <div className="flex gap-2 flex-wrap">
            {WEATHER_OPTIONS.map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setWeather(weather === w ? "" : w)}
                className={`px-3 py-1.5 rounded-full text-sm cursor-pointer transition-colors ${
                  weather === w
                    ? "bg-primary text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {w}
              </button>
            ))}
          </div>
        </div>

        {/* 농약/비료 사용 (접기/펼치기) */}
        <div>
          <button
            type="button"
            onClick={() => setShowChemicals(!showChemicals)}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 cursor-pointer"
          >
            {showChemicals ? <MdExpandLess /> : <MdExpandMore />}
            농약/비료 사용 정보
          </button>

          {showChemicals && (
            <div className="mt-3 grid grid-cols-2 gap-3 p-3 bg-gray-50 rounded-lg">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  농약 제품명
                </label>
                <input
                  type="text"
                  value={usagePesticideProduct}
                  onChange={(e) => setUsagePesticideProduct(e.target.value)}
                  placeholder="예: 프로피네브 수화제"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  농약 사용량
                </label>
                <input
                  type="text"
                  value={usagePesticideAmount}
                  onChange={(e) => setUsagePesticideAmount(e.target.value)}
                  placeholder="예: 500배액"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  비료 제품명
                </label>
                <input
                  type="text"
                  value={usageFertilizerProduct}
                  onChange={(e) => setUsageFertilizerProduct(e.target.value)}
                  placeholder="예: 요소비료"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  비료 사용량
                </label>
                <input
                  type="text"
                  value={usageFertilizerAmount}
                  onChange={(e) => setUsageFertilizerAmount(e.target.value)}
                  placeholder="예: 10kg"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
          )}
        </div>

        {/* 세부작업내용 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            세부작업내용
          </label>
          <textarea
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            rows={3}
            placeholder="작업 내용을 자유롭게 입력하세요"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
          />
        </div>

        {/* 버튼 */}
        <div className="flex gap-3 justify-end items-center">
          {!isEdit && onRequestRecord && (
            <button
              type="button"
              onClick={onRequestRecord}
              className="mr-auto flex items-center gap-2 px-6 py-3 text-base font-medium text-white bg-red-500 rounded-xl shadow-sm hover:bg-red-600 cursor-pointer"
            >
              <MdMic className="text-xl" /> 녹음
            </button>
          )}
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={submitting || !fieldName.trim() || !crop.trim()}
            className="btn-primary disabled:opacity-50"
          >
            {submitting
              ? "저장 중..."
              : submitLabel || (isEdit ? "수정" : "등록")}
          </button>
        </div>
      </form>
    );
  },
);

export default JournalEntryForm;
