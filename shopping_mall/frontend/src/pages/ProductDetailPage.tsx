import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProduct } from '@/hooks/useProducts';
import { useAddToCart } from '@/hooks/useCart';
import { formatPrice, getDiscountedPrice } from '@/lib/utils';
import ImageGallery from '@/components/product/ImageGallery';
import OptionSelector from '@/components/product/OptionSelector';
import StarRating from '@/components/review/StarRating';
import ReviewList from '@/components/review/ReviewList';

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: product, isLoading } = useProduct(Number(id));
  const addToCart = useAddToCart();
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({});
  const [quantity, setQuantity] = useState(1);
  const [activeTab, setActiveTab] = useState<'info' | 'review'>('info');

  if (isLoading) return <div className="text-center py-20 text-gray-400">로딩 중...</div>;
  if (!product) return <div className="text-center py-20 text-gray-400">상품을 찾을 수 없습니다.</div>;

  const finalPrice = product.discountRate > 0 ? getDiscountedPrice(product.price, product.discountRate) : product.price;

  const handleAddToCart = () => {
    addToCart.mutate(
      { productId: product.id, quantity, selectedOption: Object.keys(selectedOptions).length > 0 ? selectedOptions : undefined },
      { onSuccess: () => { if (confirm('장바구니에 담았습니다. 장바구니로 이동하시겠습니까?')) navigate('/cart'); } }
    );
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <ImageGallery images={product.images ?? []} name={product.name} />
        <div>
          {product.store && <p className="text-sm text-gray-500 mb-1">{product.store.name}</p>}
          <h1 className="text-2xl font-bold mb-2">{product.name}</h1>
          <div className="flex items-center gap-2 mb-4">
            <StarRating rating={product.rating} />
            <span className="text-sm text-gray-500">리뷰 {product.reviewCount}개</span>
          </div>
          <div className="mb-6">
            {product.discountRate > 0 && (
              <div className="flex items-center gap-2 mb-1">
                <span className="text-red-500 text-xl font-bold">{product.discountRate}%</span>
                <span className="text-gray-400 line-through">{formatPrice(product.price)}</span>
              </div>
            )}
            <p className="text-3xl font-bold">{formatPrice(finalPrice)}</p>
          </div>
          <hr className="mb-4" />
          <OptionSelector
            options={product.options ?? []}
            selectedOptions={selectedOptions}
            onOptionChange={(name, value) => setSelectedOptions((p) => ({ ...p, [name]: value }))}
            quantity={quantity}
            onQuantityChange={setQuantity}
            stock={product.stock}
          />
          <div className="flex gap-3 mt-6">
            <button onClick={handleAddToCart} className="flex-1 py-3 border-2 border-[#03C75A] text-[#03C75A] rounded-lg font-bold hover:bg-green-50">
              장바구니
            </button>
            <button onClick={() => { handleAddToCart(); navigate('/order'); }} className="flex-1 py-3 bg-[#03C75A] text-white rounded-lg font-bold hover:bg-green-600">
              바로구매
            </button>
          </div>
        </div>
      </div>

      <div className="mt-12 border-t">
        <div className="flex border-b">
          <button onClick={() => setActiveTab('info')} className={`px-6 py-3 text-sm font-medium ${activeTab === 'info' ? 'border-b-2 border-[#03C75A] text-[#03C75A]' : 'text-gray-500'}`}>
            상품정보
          </button>
          <button onClick={() => setActiveTab('review')} className={`px-6 py-3 text-sm font-medium ${activeTab === 'review' ? 'border-b-2 border-[#03C75A] text-[#03C75A]' : 'text-gray-500'}`}>
            리뷰 ({product.reviewCount})
          </button>
        </div>
        <div className="py-6">
          {activeTab === 'info' ? (
            <div className="prose max-w-none text-sm">
              {product.description || '상품 상세 설명이 없습니다.'}
            </div>
          ) : (
            <ReviewList productId={product.id} />
          )}
        </div>
      </div>
    </div>
  );
}
