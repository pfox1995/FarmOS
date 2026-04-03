import { Link } from 'react-router-dom';
import { formatPrice } from '@/lib/utils';

interface Props {
  totalPrice: number;
  itemCount: number;
}

export default function CartSummary({ totalPrice, itemCount }: Props) {
  return (
    <div className="bg-white rounded-lg border p-6 sticky top-20">
      <h3 className="font-bold text-lg mb-4">주문 요약</h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between"><span>상품금액</span><span>{formatPrice(totalPrice)}</span></div>
        <div className="flex justify-between"><span>배송비</span><span className="text-[#03C75A]">무료</span></div>
        <hr className="my-2" />
        <div className="flex justify-between font-bold text-lg">
          <span>총 금액</span><span className="text-[#03C75A]">{formatPrice(totalPrice)}</span>
        </div>
      </div>
      <Link
        to="/order"
        className={`mt-4 block w-full text-center py-3 rounded-lg font-bold text-white ${itemCount > 0 ? 'bg-[#03C75A] hover:bg-green-600' : 'bg-gray-300 pointer-events-none'}`}
      >
        주문하기 ({itemCount})
      </Link>
    </div>
  );
}
