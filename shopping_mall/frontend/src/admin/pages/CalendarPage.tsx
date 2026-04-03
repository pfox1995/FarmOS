import { useState, type FormEvent } from 'react';
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  format,
  isSameMonth,
  isToday,
  addMonths,
  subMonths,
} from 'date-fns';
import { ko } from 'date-fns/locale';
import { useHarvestSchedules, useCreateHarvestSchedule } from '@/admin/hooks/useCalendar';
import type { HarvestSchedule } from '@/admin/types/harvest';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export default function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    product_name: '',
    harvest_date: '',
    estimated_quantity: '',
    notes: '',
  });

  const { data: schedules, isLoading } = useHarvestSchedules();
  const createMutation = useCreateHarvestSchedule();

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const getSchedulesForDate = (date: Date): HarvestSchedule[] => {
    if (!schedules) return [];
    const dateStr = format(date, 'yyyy-MM-dd');
    return schedules.filter((s) => s.harvest_date?.startsWith(dateStr));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      {
        product_name: formData.product_name,
        harvest_date: formData.harvest_date,
        estimated_quantity: Number(formData.estimated_quantity),
        notes: formData.notes || undefined,
      },
      {
        onSuccess: () => {
          setShowModal(false);
          setFormData({ product_name: '', harvest_date: '', estimated_quantity: '', notes: '' });
        },
      }
    );
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">판매 캘린더</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-[#03C75A] text-white px-4 py-2 rounded text-sm font-medium hover:bg-[#02b050] transition-colors"
        >
          + 수확 일정 추가
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
            className="px-3 py-1 text-gray-500 hover:bg-gray-100 rounded"
          >
            &lt;
          </button>
          <h3 className="text-lg font-semibold">
            {format(currentMonth, 'yyyy년 M월', { locale: ko })}
          </h3>
          <button
            onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            className="px-3 py-1 text-gray-500 hover:bg-gray-100 rounded"
          >
            &gt;
          </button>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-gray-400">로딩 중...</div>
        ) : (
          <div className="grid grid-cols-7 gap-px bg-gray-200">
            {WEEKDAYS.map((day) => (
              <div key={day} className="bg-gray-50 text-center text-xs font-semibold text-gray-500 py-2">
                {day}
              </div>
            ))}
            {days.map((day) => {
              const daySchedules = getSchedulesForDate(day);
              return (
                <div
                  key={day.toISOString()}
                  className={`bg-white min-h-24 p-1.5 ${
                    !isSameMonth(day, currentMonth) ? 'opacity-30' : ''
                  }`}
                >
                  <div
                    className={`text-xs font-medium mb-1 ${
                      isToday(day)
                        ? 'bg-[#03C75A] text-white w-6 h-6 rounded-full flex items-center justify-center'
                        : 'text-gray-700'
                    }`}
                  >
                    {format(day, 'd')}
                  </div>
                  {daySchedules.map((s) => (
                    <div
                      key={s.id}
                      className="text-xs bg-green-50 text-green-700 rounded px-1 py-0.5 mb-0.5 truncate"
                      title={`${s.product_name} - ${s.estimated_quantity}개`}
                    >
                      {s.product_name} ({s.estimated_quantity})
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
            <h3 className="text-lg font-bold mb-4">수확 일정 추가</h3>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">상품명</label>
                <input
                  type="text"
                  value={formData.product_name}
                  onChange={(e) => setFormData((f) => ({ ...f, product_name: e.target.value }))}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">수확 날짜</label>
                <input
                  type="date"
                  value={formData.harvest_date}
                  onChange={(e) => setFormData((f) => ({ ...f, harvest_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">예상 수량</label>
                <input
                  type="number"
                  value={formData.estimated_quantity}
                  onChange={(e) =>
                    setFormData((f) => ({ ...f, estimated_quantity: e.target.value }))
                  }
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">메모</label>
                <input
                  type="text"
                  value={formData.notes}
                  onChange={(e) => setFormData((f) => ({ ...f, notes: e.target.value }))}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="flex-1 bg-[#03C75A] text-white py-2 rounded text-sm font-medium hover:bg-[#02b050] disabled:opacity-50"
                >
                  {createMutation.isPending ? '저장 중...' : '저장'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 border border-gray-300 py-2 rounded text-sm"
                >
                  취소
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
