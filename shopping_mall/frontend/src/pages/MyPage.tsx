import { Link } from 'react-router-dom';
import { useUserStore } from '@/stores/userStore';
import { useOrders } from '@/hooks/useOrders';

export default function MyPage() {
  const { user } = useUserStore();
  const { data: orders } = useOrders();

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-6">마이페이지</h1>
      <div className="bg-white rounded-lg border p-6 mb-6">
        <h2 className="font-bold text-lg">{user.name}님 안녕하세요!</h2>
        <p className="text-sm text-gray-500 mt-1">{user.email}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Link to="/mypage/orders" className="bg-white rounded-lg border p-6 hover:shadow-md transition-shadow">
          <h3 className="font-bold">주문내역</h3>
          <p className="text-2xl font-bold text-[#03C75A] mt-2">{orders?.length ?? 0}건</p>
        </Link>
        <Link to="/mypage/wishlist" className="bg-white rounded-lg border p-6 hover:shadow-md transition-shadow">
          <h3 className="font-bold">찜 목록</h3>
          <p className="text-sm text-gray-500 mt-2">내가 찜한 상품</p>
        </Link>
      </div>
    </div>
  );
}
