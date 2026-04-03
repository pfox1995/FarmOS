import { Link, useSearchParams } from 'react-router-dom';
import { useCategories } from '@/hooks/useCategories';

export default function CategoryNav() {
  const { data: categories } = useCategories();
  const [searchParams] = useSearchParams();
  const activeCategoryId = searchParams.get('categoryId');

  const parents = categories?.filter((c) => !c.parentId) ?? [];

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 flex gap-1 overflow-x-auto py-2">
        <Link
          to="/products"
          className={`px-4 py-2 rounded-full text-sm whitespace-nowrap ${
            !activeCategoryId ? 'bg-[#03C75A] text-white' : 'bg-gray-100 hover:bg-gray-200'
          }`}
        >
          전체
        </Link>
        {parents.map((cat) => (
          <Link
            key={cat.id}
            to={`/products?categoryId=${cat.id}`}
            className={`px-4 py-2 rounded-full text-sm whitespace-nowrap ${
              activeCategoryId === String(cat.id) ? 'bg-[#03C75A] text-white' : 'bg-gray-100 hover:bg-gray-200'
            }`}
          >
            {cat.icon} {cat.name}
          </Link>
        ))}
      </div>
    </nav>
  );
}
