const colorMap: Record<string, string> = {
  registered: 'bg-gray-100 text-gray-700',
  picked_up: 'bg-blue-100 text-blue-700',
  in_transit: 'bg-purple-100 text-purple-700',
  delivered: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  paid: 'bg-blue-100 text-blue-700',
  shipping: 'bg-purple-100 text-purple-700',
};

const labelMap: Record<string, string> = {
  registered: '등록',
  picked_up: '집화',
  in_transit: '배송중',
  delivered: '배송완료',
  pending: '대기',
  paid: '결제완료',
  shipping: '배송중',
};

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colors = colorMap[status] ?? 'bg-gray-100 text-gray-700';
  const label = labelMap[status] ?? status;

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors}`}>
      {label}
    </span>
  );
}
