import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Product } from '@/types/product';
import ProductGrid from '@/components/product/ProductGrid';

export default function WishlistPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['wishlists'],
    queryFn: async () => {
      const { data } = await api.get<{ id: number; product: Product }[]>('/api/wishlists');
      return data;
    },
  });

  const products = data?.map((w) => w.product).filter(Boolean) ?? [];

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-6">찜 목록 ({products.length})</h1>
      {isLoading ? (
        <p className="text-center py-20 text-gray-400">로딩 중...</p>
      ) : products.length > 0 ? (
        <ProductGrid products={products} />
      ) : (
        <p className="text-center py-20 text-gray-400">찜한 상품이 없습니다.</p>
      )}
    </div>
  );
}
