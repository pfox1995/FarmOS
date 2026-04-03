import { useProducts } from '@/hooks/useProducts';
import ProductCard from '@/components/product/ProductCard';

export default function RecommendSection() {
  const { data } = useProducts({ sort: 'rating', limit: 4 });

  return (
    <section className="max-w-6xl mx-auto px-4 mt-8">
      <h2 className="text-xl font-bold mb-4">오늘의 추천 상품</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {data?.items.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>
    </section>
  );
}
