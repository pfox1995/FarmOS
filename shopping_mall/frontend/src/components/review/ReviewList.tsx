import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ReviewListResponse } from '@/types/review';
import StarRating from './StarRating';
import { formatDate } from '@/lib/utils';

export default function ReviewList({ productId }: { productId: number }) {
  const { data } = useQuery({
    queryKey: ['reviews', 'product', productId],
    queryFn: async () => {
      const { data } = await api.get<ReviewListResponse>(`/api/reviews/product/${productId}`);
      return data;
    },
  });

  const items = data?.items ?? [];
  if (!items.length) return <p className="text-gray-500 text-sm py-4">아직 리뷰가 없습니다.</p>;

  return (
    <div className="space-y-4">
      {items.map((r) => (
        <div key={r.id} className="border-b pb-4">
          <div className="flex items-center gap-2 mb-1">
            <StarRating rating={r.rating} size="sm" />
            <span className="text-sm text-gray-600">{r.user.name}</span>
            <span className="text-xs text-gray-400">{formatDate(r.createdAt)}</span>
          </div>
          {r.content && <p className="text-sm">{r.content}</p>}
          {(r.images ?? []).length > 0 && (
            <div className="flex gap-2 mt-2">
              {(r.images ?? []).map((img, i) => (
                <img key={i} src={img} alt="" className="w-16 h-16 rounded object-cover" />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
