import { Link } from 'react-router-dom';

export default function OrderCompletePage() {
  return (
    <div className="max-w-lg mx-auto px-4 py-20 text-center">
      <div className="text-6xl mb-4">&#10004;</div>
      <h1 className="text-2xl font-bold mb-2">주문이 완료되었습니다!</h1>
      <p className="text-gray-500 mb-8">주문해 주셔서 감사합니다. 빠르게 배송해 드리겠습니다.</p>
      <div className="flex gap-3 justify-center">
        <Link to="/mypage/orders" className="px-6 py-3 border-2 border-[#03C75A] text-[#03C75A] rounded-lg font-bold hover:bg-green-50">
          주문내역 보기
        </Link>
        <Link to="/" className="px-6 py-3 bg-[#03C75A] text-white rounded-lg font-bold hover:bg-green-600">
          쇼핑 계속하기
        </Link>
      </div>
    </div>
  );
}
