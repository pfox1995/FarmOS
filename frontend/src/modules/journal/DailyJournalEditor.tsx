import { useState, useEffect, useRef } from "react";
import {
  MdClose,
  MdAutorenew,
  MdSave,
  MdHistory,
  MdChevronLeft,
} from "react-icons/md";
import toast from "react-hot-toast";
import type { DailyJournalAPI, DailyJournalRevisionAPI } from "@/types";
import { useDailyJournal } from "@/hooks/useDailyJournal";

interface Props {
  dailyJournal: DailyJournalAPI;
  /** 저장/재생성 성공 시 최신 DJ를 부모에 전달. */
  onSaved: (updated: DailyJournalAPI) => void;
  onClose: () => void;
}

const MAX_LEN = 20000;

/**
 * 통합 영농일지 본문 편집 모달 (Step 12).
 *
 * 좌측(데스크톱) / 상단(모바일): 원본 entry 스냅샷 요약 (read-only 참고용).
 * 우측 / 하단: 서술형 본문 textarea + 저장 / LLM 재생성.
 *
 * confirmed 상태의 DJ가 들어오면 편집 UI를 막고 안내한다.
 */
export default function DailyJournalEditor({ dailyJournal, onSaved, onClose }: Props) {
  const dj = useDailyJournal();
  const [narrative, setNarrative] = useState(dailyJournal.narrative);
  const [busy, setBusy] = useState<null | "save" | "regenerate">(null);
  const [revisions, setRevisions] = useState<DailyJournalRevisionAPI[] | null>(
    dailyJournal.revisions ?? null,
  );
  // 모달 내부 뷰 — 편집 본체 / 이전 기록 전체화면.
  const [view, setView] = useState<"edit" | "history">("edit");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const locked = dailyJournal.status === "confirmed";
  const dirty = narrative !== dailyJournal.narrative;

  // 들어올 때 textarea 포커스.
  useEffect(() => {
    if (!locked) {
      const id = setTimeout(() => textareaRef.current?.focus(), 50);
      return () => clearTimeout(id);
    }
  }, [locked]);

  // ESC 닫기.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty]);

  const handleClose = () => {
    if (dirty && !confirm("저장하지 않은 편집 내용이 있습니다. 닫을까요?")) return;
    onClose();
  };

  const handleSave = async () => {
    const trimmed = narrative.trim();
    if (!trimmed) {
      toast.error("본문을 비워둘 수 없습니다.");
      return;
    }
    if (trimmed.length > MAX_LEN) {
      toast.error(`본문이 너무 깁니다. (${trimmed.length}/${MAX_LEN})`);
      return;
    }
    // "manual"만 유지. 나머지(llm, template_fallback, llm_edited)는 편집 후 llm_edited로 수렴.
    const nextSource: "llm_edited" | "manual" =
      dailyJournal.narrative_source === "manual" ? "manual" : "llm_edited";

    setBusy("save");
    const r = await dj.updateNarrative(dailyJournal.id, narrative, nextSource);
    setBusy(null);
    if (r.ok && r.data) {
      toast.success("본문이 저장되었습니다.");
      onSaved(r.data);
      onClose(); // 저장 성공 시 모달 자동 닫기. 다음에 편집 열 때 revisions는 그때 다시 조회.
    } else {
      toast.error(r.error?.message || "저장 실패");
    }
  };

  const handleRegenerate = async () => {
    if (
      dirty &&
      !confirm(
        "편집 중인 내용이 있습니다. 재생성하면 현재 입력이 덮어써집니다. 계속할까요?",
      )
    ) {
      return;
    }
    setBusy("regenerate");
    const r = await dj.regenerate(dailyJournal.id);
    setBusy(null);
    if (r.ok && r.data) {
      setNarrative(r.data.narrative);
      toast.success("재생성되었습니다.");
      onSaved(r.data);
      const rv = await dj.fetchRevisions(dailyJournal.id);
      if (rv.ok && rv.data) setRevisions(rv.data);
    } else {
      toast.error(r.error?.message || "재생성 실패");
    }
  };

  const openHistory = async () => {
    // 이미 캐시된 revisions가 있으면 즉시 전환, 없으면 서버 조회 후 전환.
    if (revisions !== null) {
      setView("history");
      return;
    }
    const r = await dj.fetchRevisions(dailyJournal.id);
    if (r.ok && r.data) {
      setRevisions(r.data);
      setView("history");
    } else {
      toast.error(r.error?.message || "히스토리 조회 실패");
    }
  };

  const restoreFromRevision = (rev: DailyJournalRevisionAPI) => {
    if (locked) return;
    if (dirty && !confirm("현재 편집 내용이 덮어써집니다. 계속할까요?")) return;
    setNarrative(rev.narrative);
    setView("edit"); // 불러온 뒤 편집 뷰로 자동 복귀
    toast.success("히스토리 본문을 불러왔습니다. (아직 저장되지 않음)");
  };

  const snapshot = dailyJournal.entry_snapshot as Array<Record<string, unknown>>;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="daily-journal-editor-title"
    >
      <div onClick={handleClose} className="absolute inset-0 bg-black/40" />

      <div className="relative bg-white rounded-2xl shadow-xl w-[95vw] max-w-5xl h-[90vh] flex flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            {view === "history" && (
              <button
                type="button"
                onClick={() => setView("edit")}
                className="p-1 text-gray-500 hover:text-gray-700 cursor-pointer"
                aria-label="편집 뷰로 돌아가기"
              >
                <MdChevronLeft className="text-xl" />
              </button>
            )}
            <div>
              <h3
                id="daily-journal-editor-title"
                className="text-base font-semibold text-gray-900"
              >
                {view === "edit"
                  ? `통합 영농일지 편집 · ${dailyJournal.work_date}`
                  : `이전 기록 (${revisions?.length ?? 0}건)`}
              </h3>
              {view === "edit" && locked && (
                <p className="text-xs text-red-500 mt-1">
                  확정된 일지는 편집할 수 없습니다. 먼저 확정을 해제하세요.
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {view === "edit" && (
              <button
                type="button"
                onClick={openHistory}
                aria-label="이전 기록"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-indigo-600 hover:bg-indigo-50 cursor-pointer"
              >
                <MdHistory className="text-base" />
                <span className="hidden sm:inline">이전 기록</span>
              </button>
            )}
          <button
            onClick={handleClose}
            className="p-1 text-gray-400 hover:text-gray-600 cursor-pointer"
            aria-label="닫기"
          >
            <MdClose className="text-xl" />
          </button>
          </div>
        </div>

        {/* 본문 영역 — view 상태에 따라 편집 뷰 또는 이전 기록 뷰 */}
        {view === "edit" && (
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* 좌측 원본 참고 — 데스크톱 전용. 모바일은 공간 확보를 위해 숨김. */}
          <aside className="hidden md:flex md:flex-col md:w-72 md:border-r border-gray-100 md:overflow-y-auto md:p-4 bg-gray-50/50">
            <h4 className="text-xs font-semibold text-gray-500 mb-2">
              원본 작업 기록 ({snapshot.length}건)
            </h4>
            <ul className="space-y-2 text-xs">
              {snapshot.map((e, i) => (
                <li
                  key={(e.id as number) ?? i}
                  className="p-2 bg-white border border-gray-100 rounded"
                >
                  <div className="font-medium text-gray-700">
                    {(e.field_name as string) || "-"} ·{" "}
                    <span className="text-gray-500">{(e.crop as string) || "-"}</span>
                  </div>
                  <div className="text-gray-500">
                    {(e.work_stage as string) || ""}
                    {e.usage_pesticide_product
                      ? ` · 농약: ${e.usage_pesticide_product as string}`
                      : ""}
                    {e.usage_fertilizer_product
                      ? ` · 비료: ${e.usage_fertilizer_product as string}`
                      : ""}
                  </div>
                  {e.detail ? (
                    <div className="text-gray-400 mt-1">{e.detail as string}</div>
                  ) : null}
                </li>
              ))}
              {snapshot.length === 0 && (
                <li className="text-gray-400">원본 스냅샷이 없습니다.</li>
              )}
            </ul>
          </aside>

          {/* 우측: 본문 편집 */}
          <div className="flex-1 flex flex-col p-4">
            <textarea
              ref={textareaRef}
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              readOnly={locked}
              spellCheck={false}
              className="flex-1 resize-none border border-gray-200 rounded-lg p-3 font-sans text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:bg-gray-50"
              placeholder="영농일지 본문을 편집하세요..."
            />
            <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
              <span>
                {narrative.length.toLocaleString()} / {MAX_LEN.toLocaleString()}자
                {dirty && <span className="ml-2 text-amber-600">● 저장되지 않음</span>}
              </span>
            </div>
          </div>
        </div>
        )}

        {/* 이전 기록 뷰 — 모달 전체 화면을 revision 카드 리스트로 전환 */}
        {view === "history" && (
          <div className="flex-1 overflow-y-auto px-4 py-4 bg-gray-50/30">
            {revisions && revisions.length === 0 && (
              <div className="text-center py-12 text-sm text-gray-400">
                아직 편집 히스토리가 없습니다.
              </div>
            )}
            {!locked && (
              <p className="text-xs text-gray-500 mb-3 text-center">
                불러올 기록을 선택하세요. 현재 편집 중인 내용은 덮어써집니다.
              </p>
            )}
            <ul className="space-y-3">
              {revisions?.map((rev) => (
                <li key={rev.id}>
                  <button
                    type="button"
                    onClick={() => restoreFromRevision(rev)}
                    disabled={locked}
                    className="w-full text-left p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-indigo-400 hover:shadow-md active:scale-[0.99] transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-gray-200 disabled:hover:shadow-sm disabled:active:scale-100"
                  >
                    <div className="flex items-center gap-2 text-xs mb-2">
                      <span className="text-gray-500">
                        {new Date(rev.created_at).toLocaleString("ko-KR")}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">
                        {rev.narrative_source}
                      </span>
                    </div>
                    <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed line-clamp-6">
                      {rev.narrative}
                    </pre>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 푸터 — 편집 뷰에서만 표시 */}
        {view === "edit" && (
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-gray-100 bg-gray-50/50">
          <button
            onClick={handleClose}
            className="btn-outline text-sm"
            disabled={busy !== null}
          >
            취소
          </button>
          <button
            onClick={handleRegenerate}
            disabled={busy !== null || locked}
            className="btn-outline text-sm disabled:opacity-40"
            title="기존 본문을 히스토리로 보내고 AI가 다시 생성"
          >
            <MdAutorenew className={busy === "regenerate" ? "animate-spin" : ""} />
            {busy === "regenerate" ? "재생성 중..." : "AI 재생성"}
          </button>
          <button
            onClick={handleSave}
            disabled={busy !== null || locked || !dirty}
            className="btn-primary text-sm disabled:opacity-40"
          >
            <MdSave />
            {busy === "save" ? "저장 중..." : "저장"}
          </button>
        </div>
        )}
      </div>
    </div>
  );
}
