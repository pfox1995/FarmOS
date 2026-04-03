import { Link } from 'react-router-dom';
import { useCart, useUpdateCartItem, useRemoveCartItem } from '@/hooks/useCart';
import { useCartStore } from '@/stores/cartStore';
import { getDiscountedPrice } from '@/lib/utils';
import CartItemRow from '@/components/cart/CartItem';
import CartSummary from '@/components/cart/CartSummary';

export default function CartPage() {
  const { data: cart, isLoading } = useCart();
  const updateItem = useUpdateCartItem();
  const removeItem = useRemoveCartItem();
  const { selectedIds, toggleSelect, selectAll, deselectAll } = useCartStore();

  if (isLoading) return <div className="text-center py-20 text-gray-400">로딩 중...</div>;

  const items = cart?.items ?? [];
  const allSelected = items.length > 0 && items.every((i) => selectedIds.has(i.id));

  const selectedTotal = items
    .filter((i) => selectedIds.has(i.id))
    .reduce((sum, i) => {
      const price = i.product.discountRate > 0 ? getDiscountedPrice(i.product.price, i.product.discountRate) : i.product.price;
      return sum + price * i.quantity;
    }, 0);

  if (items.length === 0) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 text-center">
        <p className="text-gray-400 text-lg mb-4">장바구니가 비어있습니다.</p>
        <Link to="/" className="text-[#03C75A] hover:underline">쇼핑하러 가기</Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">장바구니 ({items.length})</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={() => allSelected ? deselectAll() : selectAll(items.map((i) => i.id))}
              className="w-4 h-4 accent-[#03C75A]"
            />
            전체선택 ({selectedIds.size}/{items.length})
          </label>
          {items.map((item) => (
            <CartItemRow
              key={item.id}
              item={item}
              selected={selectedIds.has(item.id)}
              onToggle={() => toggleSelect(item.id)}
              onQuantityChange={(q) => updateItem.mutate({ id: item.id, quantity: q })}
              onRemove={() => removeItem.mutate(item.id)}
            />
          ))}
        </div>
        <div>
          <CartSummary totalPrice={selectedTotal} itemCount={selectedIds.size} />
        </div>
      </div>
    </div>
  );
}
