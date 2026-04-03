import { useState } from 'react';
import { useShipments } from '@/admin/hooks/useShipments';
import ShipmentForm from '@/admin/components/shipments/ShipmentForm';
import ShipmentTable from '@/admin/components/shipments/ShipmentTable';

const STATUSES = [
  { value: '', label: '전체' },
  { value: 'registered', label: '등록' },
  { value: 'picked_up', label: '집화' },
  { value: 'in_transit', label: '배송중' },
  { value: 'delivered', label: '배송완료' },
];

export default function ShipmentsPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const { data: shipments, isLoading } = useShipments(statusFilter || undefined);

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-bold text-gray-900">배송 관리</h2>

      <ShipmentForm />

      <div className="flex items-center gap-2 mb-2">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            onClick={() => setStatusFilter(s.value)}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              statusFilter === s.value
                ? 'bg-[#03C75A] text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400">로딩 중...</div>
        ) : (
          <ShipmentTable data={shipments ?? []} />
        )}
      </div>
    </div>
  );
}
