import { useState, type FormEvent } from 'react';
import { useCreateShipment } from '@/admin/hooks/useShipments';

const CARRIERS = ['CJ대한통운', '한진', '로젠'];

export default function ShipmentForm() {
  const [orderId, setOrderId] = useState('');
  const [carrier, setCarrier] = useState(CARRIERS[0]);
  const [trackingNumber, setTrackingNumber] = useState('');
  const mutation = useCreateShipment();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!orderId || !trackingNumber) return;
    mutation.mutate(
      {
        order_id: Number(orderId),
        carrier,
        tracking_number: trackingNumber,
      },
      {
        onSuccess: () => {
          setOrderId('');
          setTrackingNumber('');
        },
      }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-5 mb-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">배송 등록</h3>
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">주문번호</label>
          <input
            type="number"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm w-32"
            placeholder="주문 ID"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">택배사</label>
          <select
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm"
          >
            {CARRIERS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">운송장번호</label>
          <input
            type="text"
            value={trackingNumber}
            onChange={(e) => setTrackingNumber(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm w-48"
            placeholder="운송장번호"
            required
          />
        </div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="bg-[#03C75A] text-white px-5 py-2 rounded text-sm font-medium hover:bg-[#02b050] disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? '등록 중...' : '등록'}
        </button>
      </div>
      {mutation.isError && (
        <p className="text-red-500 text-sm mt-2">등록 실패. 다시 시도해주세요.</p>
      )}
    </form>
  );
}
