import { useState, useCallback } from "react";
import type {
  JournalEntryAPI,
  JournalListResponse,
  STTParseResult,
  DailySummaryAPI,
  MissingFieldAlert,
} from "@/types";

const API_BASE = "http://localhost:8000/api/v1";
const opts: RequestInit = { credentials: "include" };

interface JournalFilters {
  page?: number;
  pageSize?: number;
  dateFrom?: string;
  dateTo?: string;
  workStage?: string;
  crop?: string;
}

interface JournalData {
  entries: JournalEntryAPI[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
}

export function useJournalData() {
  const [data, setData] = useState<JournalData>({
    entries: [],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
    error: null,
  });

  const fetchEntries = useCallback(async (filters: JournalFilters = {}) => {
    setData((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const params = new URLSearchParams();
      if (filters.page) params.set("page", String(filters.page));
      if (filters.pageSize) params.set("page_size", String(filters.pageSize));
      if (filters.dateFrom) params.set("date_from", filters.dateFrom);
      if (filters.dateTo) params.set("date_to", filters.dateTo);
      if (filters.workStage) params.set("work_stage", filters.workStage);
      if (filters.crop) params.set("crop", filters.crop);

      const res = await fetch(`${API_BASE}/journal?${params}`, opts);
      if (!res.ok) throw new Error("목록 조회 실패");
      const json: JournalListResponse = await res.json();

      setData({
        entries: json.items,
        total: json.total,
        page: json.page,
        pageSize: json.page_size,
        loading: false,
        error: null,
      });
    } catch (e) {
      setData((prev) => ({
        ...prev,
        loading: false,
        error: (e as Error).message,
      }));
    }
  }, []);

  const createEntry = useCallback(
    async (body: Record<string, unknown>): Promise<JournalEntryAPI | null> => {
      try {
        const res = await fetch(`${API_BASE}/journal`, {
          ...opts,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("생성 실패");
        return await res.json();
      } catch {
        return null;
      }
    },
    [],
  );

  const updateEntry = useCallback(
    async (
      id: number,
      body: Record<string, unknown>,
    ): Promise<JournalEntryAPI | null> => {
      try {
        const res = await fetch(`${API_BASE}/journal/${id}`, {
          ...opts,
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("수정 실패");
        return await res.json();
      } catch {
        return null;
      }
    },
    [],
  );

  const deleteEntry = useCallback(async (id: number): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/journal/${id}`, {
        ...opts,
        method: "DELETE",
      });
      return res.ok;
    } catch {
      return false;
    }
  }, []);

  const transcribeAudio = useCallback(
    async (blob: Blob): Promise<string | null> => {
      try {
        const form = new FormData();
        const ext = blob.type.includes("ogg")
          ? "ogg"
          : blob.type.includes("mp4")
            ? "mp4"
            : "webm";
        form.append("file", blob, `audio.${ext}`);
        const res = await fetch(`${API_BASE}/journal/transcribe`, {
          ...opts,
          method: "POST",
          body: form,
        });
        if (!res.ok) throw new Error("전사 실패");
        const json: { text: string } = await res.json();
        return json.text;
      } catch {
        return null;
      }
    },
    [],
  );

  const parseSTT = useCallback(
    async (rawText: string): Promise<STTParseResult> => {
      try {
        const res = await fetch(`${API_BASE}/journal/parse-stt`, {
          ...opts,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: rawText }),
        });
        if (!res.ok) {
          let detail = `파싱 실패 (${res.status})`;
          try {
            const body = await res.json();
            if (body?.detail) detail = String(body.detail);
          } catch {
            /* ignore */
          }
          return {
            entries: [],
            unparsed_text: rawText,
            rejected: true,
            reject_reason: detail,
          };
        }
        return await res.json();
      } catch (e) {
        return {
          entries: [],
          unparsed_text: rawText,
          rejected: true,
          reject_reason: `네트워크 오류: ${(e as Error).message}`,
        };
      }
    },
    [],
  );

  const fetchDailySummary = useCallback(
    async (date: string): Promise<DailySummaryAPI | null> => {
      try {
        const res = await fetch(
          `${API_BASE}/journal/daily-summary?date=${date}`,
          opts,
        );
        if (!res.ok) throw new Error("요약 조회 실패");
        return await res.json();
      } catch {
        return null;
      }
    },
    [],
  );

  const fetchMissingFields = useCallback(
    async (
      dateFrom: string,
      dateTo: string,
    ): Promise<{
      missing_fields: MissingFieldAlert[];
      total: number;
    } | null> => {
      try {
        const res = await fetch(
          `${API_BASE}/journal/missing-fields?date_from=${dateFrom}&date_to=${dateTo}`,
          opts,
        );
        if (!res.ok) throw new Error("누락 조회 실패");
        return await res.json();
      } catch {
        return null;
      }
    },
    [],
  );

  return {
    ...data,
    fetchEntries,
    createEntry,
    updateEntry,
    deleteEntry,
    parseSTT,
    transcribeAudio,
    fetchDailySummary,
    fetchMissingFields,
  };
}
