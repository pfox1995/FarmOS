import { useSearchParams } from 'react-router-dom';
import { useSearchProducts } from '@/hooks/useProducts';
import ProductGrid from '@/components/product/ProductGrid';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const q = searchParams.get('q') || '';
  const { data, isLoading } = useSearchProducts(q);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold mb-4">
        검색 결과: <span className="text-[#03C75A]">"{q}"</span>
        {data && <span className="text-gray-400 text-sm font-normal ml-2">({data.total}건)</span>}
      </h1>
      {isLoading ? (
        <p className="text-center py-20 text-gray-400">검색 중...</p>
      ) : data?.items.length ? (
        <ProductGrid products={data.items} />
      ) : (
        <p className="text-center py-20 text-gray-400">검색 결과가 없습니다.</p>
      )}
    </div>
  );
}
