import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Store } from '@/types/store';
import type { ProductListResponse } from '@/types/product';
import ProductGrid from '@/components/product/ProductGrid';
import StarRating from '@/components/review/StarRating';

export default function StorePage() {
  const { id } = useParams();
  const { data: store } = useQuery({
    queryKey: ['stores', 'detail', id],
    queryFn: async () => { const { data } = await api.get<Store>(`/api/stores/${id}`); return data; },
    enabled: !!id,
  });
  const { data: products } = useQuery({
    queryKey: ['stores', 'products', id],
    queryFn: async () => { const { data } = await api.get<ProductListResponse>(`/api/stores/${id}/products`); return data; },
    enabled: !!id,
  });

  if (!store) return <div className="text-center py-20 text-gray-400">로딩 중...</div>;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="bg-white rounded-lg border p-6 mb-6">
        <h1 className="text-2xl font-bold">{store.name}</h1>
        {store.description && <p className="text-gray-500 mt-2">{store.description}</p>}
        <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
          <StarRating rating={store.rating} /> <span>{store.rating.toFixed(1)}</span>
          <span>|</span> <span>상품 {store.productCount}개</span>
        </div>
      </div>
      {products?.items && <ProductGrid products={products.items} />}
    </div>
  );
}
