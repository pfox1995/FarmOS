import { useProducts } from '@/hooks/useProducts';
import ProductCard from '@/components/product/ProductCard';

export default function PopularSection() {
  const { data } = useProducts({ sort: 'popular', limit: 8 });

  return (
    <section className="max-w-6xl mx-auto px-4 mt-8">
      <h2 className="text-xl font-bold mb-4">인기 상품 TOP 8</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {data?.items.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>
    </section>
  );
}
