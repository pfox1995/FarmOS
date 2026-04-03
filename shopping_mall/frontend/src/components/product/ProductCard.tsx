import { Link } from 'react-router-dom';
import type { Product } from '@/types/product';
import { formatPrice, getDiscountedPrice } from '@/lib/utils';
import StarRating from '@/components/review/StarRating';

export default function ProductCard({ product: p }: { product: Product }) {
  const discounted = p.discountRate > 0;
  const finalPrice = discounted ? getDiscountedPrice(p.price, p.discountRate) : p.price;

  return (
    <Link
      to={`/products/${p.id}`}
      className="bg-white rounded-lg overflow-hidden border border-gray-200 hover:shadow-lg transition-shadow"
    >
      <div className="aspect-square bg-gray-100">
        <img
          src={p.thumbnail || `https://picsum.photos/seed/p${p.id}/400/400`}
          alt={p.name}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="p-3">
        {p.storeName && <p className="text-xs text-gray-500 mb-1">{p.storeName}</p>}
        <h3 className="text-sm font-medium line-clamp-2 mb-2">{p.name}</h3>
        <div className="flex items-baseline gap-1">
          {discounted && <span className="text-red-500 text-sm font-bold">{p.discountRate}%</span>}
          <span className="font-bold">{formatPrice(finalPrice)}</span>
        </div>
        {discounted && <p className="text-xs text-gray-400 line-through">{formatPrice(p.price)}</p>}
        <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
          <StarRating rating={p.rating} size="sm" />
          <span>({p.reviewCount})</span>
        </div>
      </div>
    </Link>
  );
}
