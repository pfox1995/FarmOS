import { useState, useEffect, useRef } from "react";
import {
  MdAdd,
  MdEdit,
  MdDelete,
  MdFileDownload,
  MdClose,
} from "react-icons/md";
import toast from "react-hot-toast";
import { useJournalData } from "@/hooks/useJournalData";
import JournalEntryForm from "./JournalEntryForm";
import STTInput, { type STTInputHandle } from "./STTInput";
import MissingFieldsAlert from "./MissingFieldsAlert";
import DailySummaryCard from "./DailySummaryCard";
import type { JournalEntryAPI, STTParseResult } from "@/types";

const STAGE_COLORS: Record<string, string> = {
  사전준비: "bg-gray-100 text-gray-700",
  경운: "bg-amber-100 text-amber-700",
  파종: "bg-green-100 text-green-700",
  정식: "bg-emerald-100 text-emerald-700",
  작물관리: "bg-blue-100 text-blue-700",
  수확: "bg-orange-100 text-orange-700",
};

const FILTER_STAGES = [
  "all",
  "사전준비",
  "경운",
  "파종",
  "정식",
  "작물관리",
  "수확",
];

export default function JournalPage() {
  const {
    entries,
    total,
    loading,
    fetchEntries,
    createEntry,
    updateEntry,
    deleteEntry,
    parseSTT,
    fetchDailySummary,
    fetchMissingFields,
  } = useJournalData();
  const [filter, setFilter] = useState<string>("all");
  const [showForm, setShowForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState<JournalEntryAPI | null>(
    null,
  );
  const [sttPrefill, setSttPrefill] = useState<Record<string, unknown> | null>(
    null,
  );
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const sttRef = useRef<STTInputHandle>(null);

  const handleRequestRecord = () => {
    setShowForm(false);
    setEditingEntry(null);
    setSttPrefill(null);
    setTimeout(() => sttRef.current?.start(), 0);
  };

  useEffect(() => {
    fetchEntries(filter === "all" ? {} : { workStage: filter });
  }, [filter, fetchEntries]);

  const handleCreate = async (data: Record<string, unknown>) => {
    const result = await createEntry(data);
    if (result) {
      toast.success("영농일지가 저장되었습니다.");
      setShowForm(false);
      setSttPrefill(null);
      fetchEntries(filter === "all" ? {} : { workStage: filter });
    } else {
      toast.error("저장에 실패했습니다.");
    }
  };

  const handleUpdate = async (data: Record<string, unknown>) => {
    if (!editingEntry) return;
    const result = await updateEntry(editingEntry.id, data);
    if (result) {
      toast.success("영농일지가 수정되었습니다.");
      setEditingEntry(null);
      fetchEntries(filter === "all" ? {} : { workStage: filter });
    } else {
      toast.error("수정에 실패했습니다.");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("이 영농일지를 삭제하시겠습니까?")) return;
    const ok = await deleteEntry(id);
    if (ok) {
      toast.success("삭제되었습니다.");
      fetchEntries(filter === "all" ? {} : { workStage: filter });
    } else {
      toast.error("삭제에 실패했습니다.");
    }
  };

  const handleSTTParsed = (result: STTParseResult) => {
    toast.success("음성이 분석되었습니다. 확인 후 저장하세요.");
    setSttPrefill(result.parsed as Record<string, unknown>);
    setEditingEntry(null);
    setShowForm(true);
  };

  const handleExportPDF = () => {
    const today = new Date().toISOString().slice(0, 10);
    window.open(
      `http://localhost:8000/api/v1/journal/export-pdf?date_from=2026-01-01&date_to=${today}`,
      "_blank",
    );
  };

  // 날짜별 그룹핑
  const grouped = entries.reduce<Record<string, JournalEntryAPI[]>>(
    (acc, entry) => {
      const d = entry.work_date;
      if (!acc[d]) acc[d] = [];
      acc[d].push(entry);
      return acc;
    },
    {},
  );
  const sortedDates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  // STT prefill을 JournalEntryAPI 형태로 변환
  const prefillAsEntry = sttPrefill
    ? ({
        ...({} as JournalEntryAPI),
        work_date:
          (sttPrefill.work_date as string) ||
          new Date().toISOString().slice(0, 10),
        field_name: (sttPrefill.field_name as string) || "",
        crop: (sttPrefill.crop as string) || "",
        work_stage:
          (sttPrefill.work_stage as JournalEntryAPI["work_stage"]) ||
          "작물관리",
        weather: (sttPrefill.weather as string) || null,
        usage_pesticide_product:
          (sttPrefill.usage_pesticide_product as string) || null,
        usage_pesticide_amount:
          (sttPrefill.usage_pesticide_amount as string) || null,
        usage_fertilizer_product:
          (sttPrefill.usage_fertilizer_product as string) || null,
        usage_fertilizer_amount:
          (sttPrefill.usage_fertilizer_amount as string) || null,
        detail: (sttPrefill.detail as string) || null,
      } as JournalEntryAPI)
    : null;

  return (
    <div className="space-y-6">
      {/* 액션 바 */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">총 {total}건</p>
        <div className="flex gap-2">
          <button onClick={handleExportPDF} className="btn-outline text-sm">
            <MdFileDownload /> PDF 내보내기
          </button>
          <button
            onClick={() => {
              setShowForm(true);
              setSttPrefill(null);
              setEditingEntry(null);
            }}
            className="btn-primary text-sm"
          >
            <MdAdd /> 새 일지
          </button>
        </div>
      </div>

      {/* 누락 경고 */}
      <MissingFieldsAlert
        fetchMissingFields={fetchMissingFields}
        onEditEntry={(entryId) => {
          const entry = entries.find((e) => e.id === entryId);
          if (entry) setEditingEntry(entry);
        }}
      />

      {/* 음성 입력 FAB (항상 렌더링) */}
      <STTInput ref={sttRef} onParsed={handleSTTParsed} parseSTT={parseSTT} />

      {/* 폼 모달 (생성/수정 공용) */}
      {(showForm || editingEntry) && (
        <div className="fixed inset-0 z-40 flex items-center justify-center">
          <div
            onClick={() => {
              setShowForm(false);
              setSttPrefill(null);
              setEditingEntry(null);
            }}
            className="absolute inset-0 bg-black/30"
          />
          <div className="relative bg-white rounded-2xl shadow-xl w-[90vw] max-w-lg max-h-[85vh] overflow-y-auto">
            <div className="sticky top-0 bg-white rounded-t-2xl z-10 border-b border-gray-100">
              <div className="flex items-center justify-between px-5 py-4">
                <h3 className="text-base font-semibold text-gray-900">
                  {editingEntry ? "영농일지 수정" : "새 영농일지 작성"}
                </h3>
                <button
                  onClick={() => {
                    setShowForm(false);
                    setSttPrefill(null);
                    setEditingEntry(null);
                  }}
                  className="p-1 text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <MdClose className="text-xl" />
                </button>
              </div>
            </div>
            <div className="px-5 pb-6 pt-4">
              <JournalEntryForm
                initialData={editingEntry || prefillAsEntry}
                isEdit={!!editingEntry}
                onSubmit={editingEntry ? handleUpdate : handleCreate}
                onCancel={() => {
                  setShowForm(false);
                  setSttPrefill(null);
                  setEditingEntry(null);
                }}
                onRequestRecord={handleRequestRecord}
              />
            </div>
          </div>
        </div>
      )}

      {/* 필터 */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_STAGES.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap cursor-pointer transition-colors ${
              filter === f
                ? "bg-primary text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            {f === "all" ? "전체" : f}
          </button>
        ))}
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="text-center py-10 text-gray-400">불러오는 중...</div>
      )}

      {/* 빈 상태 */}
      {!loading && entries.length === 0 && (
        <div className="text-center py-10">
          <p className="text-gray-400">기록된 영농일지가 없습니다.</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-3 text-primary text-sm font-medium cursor-pointer hover:underline"
          >
            첫 영농일지를 작성해보세요
          </button>
        </div>
      )}

      {/* 타임라인 */}
      <div className="space-y-0">
        {sortedDates.map((dateStr) => (
          <div key={dateStr}>
            <div className="flex items-center gap-3 py-2">
              <span className="text-sm font-bold text-gray-400">
                {new Date(dateStr).toLocaleDateString("ko-KR", {
                  month: "long",
                  day: "numeric",
                })}
              </span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>

            {grouped[dateStr].map((entry, i) => (
              <div key={entry.id} className="flex gap-4 relative">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-3 h-3 rounded-full ${entry.source === "stt" ? "bg-red-400" : "bg-primary"} z-10`}
                  />
                  {i < grouped[dateStr].length - 1 && (
                    <div className="w-0.5 flex-1 bg-gray-200" />
                  )}
                </div>

                <div className="flex-1 pb-4">
                  {/* 카드 (클릭으로 펼치기) */}
                  <div
                    onClick={() =>
                      setExpandedId(expandedId === entry.id ? null : entry.id)
                    }
                    className="p-4 rounded-xl bg-white border border-gray-100 hover:shadow-sm transition-shadow cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`badge text-xs ${STAGE_COLORS[entry.work_stage] || "bg-gray-100 text-gray-600"}`}
                        >
                          {entry.work_stage}
                        </span>
                        <span className="text-xs text-gray-400">
                          {entry.crop}
                        </span>
                        <span className="text-xs text-gray-300">
                          {entry.field_name}
                        </span>
                        {entry.weather && (
                          <span className="text-xs text-cyan-500">
                            {entry.weather}
                          </span>
                        )}
                      </div>
                      <div
                        className="flex gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => setEditingEntry(entry)}
                          className="p-1 text-gray-400 hover:text-primary cursor-pointer"
                        >
                          <MdEdit className="text-sm" />
                        </button>
                        <button
                          onClick={() => handleDelete(entry.id)}
                          className="p-1 text-gray-400 hover:text-red-500 cursor-pointer"
                        >
                          <MdDelete className="text-sm" />
                        </button>
                      </div>
                    </div>

                    {entry.detail && (
                      <p className="text-sm text-gray-600 mt-2">
                        {entry.detail}
                      </p>
                    )}
                  </div>

                  {/* 펼쳐진 상세 정보 */}
                  {expandedId === entry.id && editingEntry?.id !== entry.id && (
                    <div className="mt-2 p-4 rounded-xl border border-gray-200 bg-gray-50/50">
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="text-xs font-medium text-gray-400">
                            작업일
                          </span>
                          <p className="text-gray-700">{entry.work_date}</p>
                        </div>
                        <div>
                          <span className="text-xs font-medium text-gray-400">
                            필지
                          </span>
                          <p className="text-gray-700">{entry.field_name}</p>
                        </div>
                        <div>
                          <span className="text-xs font-medium text-gray-400">
                            작목
                          </span>
                          <p className="text-gray-700">{entry.crop}</p>
                        </div>
                        <div>
                          <span className="text-xs font-medium text-gray-400">
                            작업단계
                          </span>
                          <p className="text-gray-700">{entry.work_stage}</p>
                        </div>
                        {entry.weather && (
                          <div>
                            <span className="text-xs font-medium text-gray-400">
                              날씨
                            </span>
                            <p className="text-gray-700">{entry.weather}</p>
                          </div>
                        )}
                        {entry.usage_pesticide_product && (
                          <div>
                            <span className="text-xs font-medium text-gray-400">
                              농약 사용
                            </span>
                            <p className="text-gray-700">
                              {entry.usage_pesticide_product}{" "}
                              {entry.usage_pesticide_amount || ""}
                            </p>
                          </div>
                        )}
                        {entry.usage_fertilizer_product && (
                          <div>
                            <span className="text-xs font-medium text-gray-400">
                              비료 사용
                            </span>
                            <p className="text-gray-700">
                              {entry.usage_fertilizer_product}{" "}
                              {entry.usage_fertilizer_amount || ""}
                            </p>
                          </div>
                        )}
                        {entry.detail && (
                          <div className="col-span-2">
                            <span className="text-xs font-medium text-gray-400">
                              세부작업내용
                            </span>
                            <p className="text-gray-700">{entry.detail}</p>
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-300 mt-3">
                        {entry.source === "stt" ? "음성 입력" : "직접 입력"} |{" "}
                        {new Date(entry.created_at).toLocaleString("ko-KR")}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
