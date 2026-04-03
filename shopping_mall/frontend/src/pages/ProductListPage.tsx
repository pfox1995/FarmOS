import { useSearchParams } from 'react-router-dom';
import { useProducts } from '@/hooks/useProducts';
import CategoryNav from '@/components/common/CategoryNav';
import ProductGrid from '@/components/product/ProductGrid';
import Pagination from '@/components/common/Pagination';

const sortOptions = [
  { value: 'latest', label: '최신순' },
  { value: 'popular', label: '인기순' },
  { value: 'price_asc', label: '가격 낮은순' },
  { value: 'price_desc', label: '가격 높은순' },
  { value: 'rating', label: '평점순' },
];

export default function ProductListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get('page') || '1');
  const sort = searchParams.get('sort') || 'latest';
  const categoryId = searchParams.get('categoryId');

  const params: Record<string, unknown> = { page, sort, limit: 20 };
  if (categoryId) params.category_id = Number(categoryId);

  const { data, isLoading } = useProducts(params);

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    if (key !== 'page') next.set('page', '1');
    setSearchParams(next);
  };

  return (
    <div>
      <CategoryNav />
      <div className="max-w-6xl mx-auto px-4 mt-6">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-xl font-bold">상품 목록 {data && `(${data.total})`}</h1>
          <select
            value={sort}
            onChange={(e) => updateParam('sort', e.target.value)}
            className="border rounded px-3 py-1 text-sm"
          >
            {sortOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {isLoading ? (
          <p className="text-center py-20 text-gray-400">로딩 중...</p>
        ) : data?.items.length ? (
          <>
            <ProductGrid products={data.items} />
            <Pagination currentPage={page} totalPages={data.totalPages} onPageChange={(p) => updateParam('page', String(p))} />
          </>
        ) : (
          <p className="text-center py-20 text-gray-400">상품이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
