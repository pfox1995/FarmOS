import type { CartItem as CartItemType } from '@/types/cart';
import { formatPrice, getDiscountedPrice } from '@/lib/utils';
import QuantitySelector from '@/components/common/QuantitySelector';

interface Props {
  item: CartItemType;
  selected: boolean;
  onToggle: () => void;
  onQuantityChange: (q: number) => void;
  onRemove: () => void;
}

export default function CartItemRow({ item, selected, onToggle, onQuantityChange, onRemove }: Props) {
  const p = item.product;
  const finalPrice = p.discountRate > 0 ? getDiscountedPrice(p.price, p.discountRate) : p.price;

  return (
    <div className="flex items-start gap-4 p-4 bg-white rounded-lg border">
      <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1 w-4 h-4 accent-[#03C75A]" />
      <img src={p.thumbnail || `https://picsum.photos/seed/p${p.id}/100/100`} alt={p.name} className="w-20 h-20 rounded object-cover" />
      <div className="flex-1">
        <h3 className="text-sm font-medium">{p.name}</h3>
        {item.selectedOption && typeof item.selectedOption === 'object' && (
          <p className="text-xs text-gray-500 mt-1">
            {Object.entries(item.selectedOption).map(([k, v]) => `${k}: ${v}`).join(', ')}
          </p>
        )}
        <p className="font-bold mt-1">{formatPrice(finalPrice * item.quantity)}</p>
        <div className="flex items-center gap-4 mt-2">
          <QuantitySelector quantity={item.quantity} onChange={onQuantityChange} max={p.stock} />
          <button onClick={onRemove} className="text-xs text-gray-400 hover:text-red-500">삭제</button>
        </div>
      </div>
    </div>
  );
}
