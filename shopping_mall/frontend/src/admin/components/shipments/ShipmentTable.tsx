import DataTable from '@/admin/components/common/DataTable';
import StatusBadge from '@/admin/components/common/StatusBadge';
import { formatDate } from '@/lib/utils';
import type { Shipment } from '@/admin/types/shipment';

interface ShipmentTableProps {
  data: Shipment[];
}

export default function ShipmentTable({ data }: ShipmentTableProps) {
  const columns = [
    {
      key: 'order_id',
      header: '주문번호',
      render: (row: Shipment) => <span className="font-mono">#{row.order_id}</span>,
    },
    {
      key: 'carrier',
      header: '택배사',
      render: (row: Shipment) => <span>{row.carrier}</span>,
    },
    {
      key: 'tracking_number',
      header: '운송장번호',
      render: (row: Shipment) => <span className="font-mono">{row.tracking_number}</span>,
    },
    {
      key: 'status',
      header: '상태',
      render: (row: Shipment) => <StatusBadge status={row.status} />,
    },
    {
      key: 'last_checked',
      header: '마지막 확인',
      render: (row: Shipment) => (
        <span className="text-gray-500">{row.last_checked ? formatDate(row.last_checked) : '-'}</span>
      ),
    },
    {
      key: 'delivered_at',
      header: '배송완료일',
      render: (row: Shipment) => (
        <span className="text-gray-500">
          {row.delivered_at ? formatDate(row.delivered_at, 'yyyy-MM-dd') : '-'}
        </span>
      ),
    },
  ];

  return <DataTable columns={columns} data={data} rowKey={(row) => row.id} />;
}
