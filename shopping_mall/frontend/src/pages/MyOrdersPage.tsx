import { useOrders } from '@/hooks/useOrders';
import { formatPrice, formatDate } from '@/lib/utils';

const statusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '주문접수', color: 'bg-yellow-100 text-yellow-800' },
  paid: { label: '결제완료', color: 'bg-blue-100 text-blue-800' },
  shipping: { label: '배송중', color: 'bg-purple-100 text-purple-800' },
  delivered: { label: '배송완료', color: 'bg-green-100 text-green-800' },
  cancelled: { label: '취소', color: 'bg-red-100 text-red-800' },
};

export default function MyOrdersPage() {
  const { data: orders, isLoading } = useOrders();

  if (isLoading) return <div className="text-center py-20 text-gray-400">로딩 중...</div>;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-6">주문내역</h1>
      {!orders?.length ? (
        <p className="text-center py-20 text-gray-400">주문 내역이 없습니다.</p>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => {
            const status = statusMap[order.status] ?? { label: order.status, color: 'bg-gray-100' };
            return (
              <div key={order.id} className="bg-white rounded-lg border p-4">
                <div className="flex justify-between items-center mb-3">
                  <div>
                    <span className="text-sm text-gray-500">주문번호 #{order.id}</span>
                    <span className="text-xs text-gray-400 ml-2">{formatDate(order.createdAt)}</span>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${status.color}`}>{status.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  {order.items?.slice(0, 3).map((item) => (
                    <img key={item.id} src={item.product?.thumbnail || `https://picsum.photos/seed/p${item.productId}/60/60`} alt="" className="w-12 h-12 rounded" />
                  ))}
                  {(order.items?.length ?? 0) > 3 && <span className="text-sm text-gray-500">+{order.items.length - 3}</span>}
                </div>
                <p className="text-right font-bold mt-2">{formatPrice(order.totalPrice)}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
