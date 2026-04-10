// Design Ref: §6.1 — AnalysisSettingsModal
import { useState } from 'react';
import { MdClose, MdSettings } from 'react-icons/md';
import type { AnalysisSettings } from '@/types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  settings: AnalysisSettings;
  onSave: (update: Partial<AnalysisSettings>) => Promise<AnalysisSettings | null>;
}

export default function AnalysisSettingsModal({ isOpen, onClose, settings, onSave }: Props) {
  const [form, setForm] = useState<AnalysisSettings>(settings);
  const [saving, setSaving] = useState(false);

  if (!isOpen) return null;

  const handleSave = async () => {
    setSaving(true);
    await onSave(form);
    setSaving(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <MdSettings className="text-xl text-primary" />
            <h3 className="text-lg font-semibold">분석 설정</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100">
            <MdClose className="text-xl text-gray-500" />
          </button>
        </div>

        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">자동 배치 분석</p>
              <p className="text-xs text-gray-500">리뷰가 N건 누적되면 자동 분석</p>
            </div>
            <button
              onClick={() => setForm({ ...form, auto_batch_enabled: !form.auto_batch_enabled })}
              className={`relative w-11 h-6 rounded-full transition-colors ${form.auto_batch_enabled ? 'bg-primary' : 'bg-gray-300'}`}
            >
              <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${form.auto_batch_enabled ? 'left-5.5' : 'left-0.5'}`} />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">자동 실행 기준 (리뷰 수)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={form.batch_trigger_count}
              onChange={e => setForm({ ...form, batch_trigger_count: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
              disabled={!form.auto_batch_enabled}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">스케줄 (Cron)</label>
            <select
              value={form.batch_schedule || ''}
              onChange={e => setForm({ ...form, batch_schedule: e.target.value || null })}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
              disabled={!form.auto_batch_enabled}
            >
              <option value="">수동 (트리거 기준만)</option>
              <option value="0 9 * * 1">매주 월요일 09:00</option>
              <option value="0 9 * * *">매일 09:00</option>
              <option value="0 18 * * 5">매주 금요일 18:00</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">자동 분석 실행 주기</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">기본 배치 크기</label>
            <select
              value={form.default_batch_size}
              onChange={e => setForm({ ...form, default_batch_size: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
            >
              <option value={10}>10개씩</option>
              <option value={20}>20개씩 (권장)</option>
              <option value={30}>30개씩</option>
              <option value={50}>50개씩</option>
            </select>
            <p className="text-xs text-gray-400 mt-1">LLM 1회 호출당 분석할 리뷰 수</p>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
